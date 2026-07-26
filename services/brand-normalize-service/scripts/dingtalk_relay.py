#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉 AI 表格中转代理（宿主机常驻轮询）。

为什么需要它：
  brand-normalize-service 跑在【本机 localhost:8000】，云端 Dify（dify.ai）
  无法直接访问本机端口，也没有公网/隧道。
  钉钉 AI 表格作为【云端可达的共享中转台】，把"任务提交"和"结果回收"
  解耦：Dify（或任何云端生产者）只往表里写 pending 行，本代理在本机轮询、
  调用本地服务、回写结果。

闭环：
  云端 Dify / 人工 ──写 pending──▶ 钉钉中转台(Base: 欧菲斯·品牌标准化中转台)
                                              │
       本机 dingtalk_relay.py 轮询 ◀──────────┘
                                              │ 调用本机服务
                                              ▼
                     http://localhost:8000/api/{brand,category}/normalize
                                              │ 回写 result + status
                                              ▼
                              钉钉中转台 ──▶ Dify 轮询/人工读取结果

职责：
  1. 轮询中转表中 status=pending 的行（mcporter 子进程调用钉钉 MCP）
  2. 按 task_type 分派到本地品牌/品类标准化接口（Bearer 鉴权 BRAND_API_TOKEN）
  3. 把标准化结果写回 result 列，status 置 done；异常置 error + error_msg
  4. 落盘日志到 .relay_log/ 便于追溯

字段映射（中转台已建好的表）：
  task_type           C9VE0UU  singleSelect(brand|category)
  status             5MNxSsU  singleSelect(pending|processing|done|error)
  in_attachment_values  vtewR4g  text   (品牌: attachment_values)
  in_source_values      KnJTVAn  text   (品牌: source_values)
  in_product_name      ASaPpI3  text   (品类: product_name)
  in_client_category   mEza2hi  text   (品类: client_category)
  result              WxgsdDw  text   (标准化结果 JSON)
  error_msg           w2HCIiH  text   (异常信息)

用法：
  # 常驻轮询（默认 15s 一轮，需 BRAND_API_TOKEN + DINGTALK_MCP_URL）
  python scripts/dingtalk_relay.py
    # 单次跑完 pending 即退出（验证用）
  python scripts/dingtalk_relay.py --once
  # 指定参数
  python scripts/dingtalk_relay.py --poll-secs 10 --service-url http://127.0.0.1:8000
  # 守护模式：日志落地到文件（被 start_relay.ps1 拉起，不依赖 Start-Process 重定向）
  python scripts/dingtalk_relay.py --log-file logs/relay.log
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
LOG_DIR = PROJECT_ROOT / ".relay_log"

# ── 中转台标识（创建一次后固定，可用 --base-id / --table-id 覆盖）──
DEFAULT_BASE_ID = "YQBnd5ExVEwOpmXnIggdl7kG8yeZqMmz"
DEFAULT_TABLE_ID = "hERWDMS"

# ── 字段 ID（与上面 schema 一一对应）──
F_TASK_TYPE = "C9VE0UU"
F_STATUS = "5MNxSsU"
F_IN_ATT = "vtewR4g"
F_IN_SRC = "KnJTVAn"
F_IN_PNAME = "ASaPpI3"
F_IN_CCAT = "mEza2hi"
F_RESULT = "WxgsdDw"
F_ERROR = "w2HCIiH"

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_ERROR = "error"

# Windows 下裸 mcporter 是 sh 脚本，Win CreateProcess 无法直接执行，
# 必须用同目录的 mcporter.cmd 包装（实测 subprocess 可正常拉起）。
IS_WIN = sys.platform == "win32"
MCPORTER_CANDIDATES = [
    "C:/Users/Lenovo/.workbuddy/binaries/node/versions/22.22.2/mcporter.cmd",
    "C:/Users/Lenovo/.workbuddy/binaries/node/versions/22.22.2/mcporter",
    "C:/Users/Lenovo/.workbuddy/binaries/node/versions/22.22.2/node_modules/.bin/mcporter",
]


# ───────────────────────────── 基础工具 ─────────────────────────────
def _load_env() -> dict:
    cfg: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _find_mcporter(explicit: str | None) -> str:
    if explicit:
        # Windows 下若给的是裸 mcporter（sh 脚本），自动补 .cmd 包装
        if IS_WIN and explicit.endswith("mcporter"):
            cmd_cand = explicit + ".cmd"
            if Path(cmd_cand).exists():
                return cmd_cand
        return explicit
    found = shutil.which("mcporter.cmd" if IS_WIN else "mcporter")
    if found:
        return found
    for cand in MCPORTER_CANDIDATES:
        if Path(cand).exists():
            return cand
    raise FileNotFoundError(
        "找不到 mcporter：请安装 `npm i -g mcporter` 或用 --mcporter 指定路径"
    )


# ───────────────────────────── 钉钉 MCP 封装 ─────────────────────────────
class DingTalkTable:
    def __init__(self, mcporter: str, mcp_url: str, base_id: str, table_id: str):
        self.mcporter = mcporter
        self.mcp_url = mcp_url
        self.base_id = base_id
        self.table_id = table_id

    def _call(self, tool: str, args: dict, timeout: int = 90) -> dict:
        cmd = [self.mcporter, "call", self.mcp_url, tool, "--args", json.dumps(args, ensure_ascii=False)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=timeout)
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"mcporter 调用超时({timeout}s): {tool}")
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 or not out:
            raise RuntimeError(f"mcporter {tool} 失败 rc={proc.returncode}: {(proc.stderr or '').strip()[:400]}")
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"mcporter {tool} 返回非 JSON: {out[:400]} ({exc})")

    def query_pending(self, limit: int = 50) -> list[dict]:
        """返回 status=pending 的记录列表（每条含 recordId + cells）。"""
        out = self._call("query_records", {
            "baseId": self.base_id, "tableId": self.table_id, "limit": limit,
        })
        records = out.get("data", {}).get("records", []) or []
        pending = []
        for rec in records:
            cells = rec.get("cells", {}) or {}
            st = _select_name(cells.get(F_STATUS))
            if st == STATUS_PENDING:
                pending.append({"recordId": rec.get("recordId"), "cells": cells})
        return pending

    def update_status(self, record_id: str, status: str,
                      result: str | None = None, error_msg: str | None = None) -> None:
        cells: dict = {F_STATUS: {"name": status}}
        if result is not None:
            cells[F_RESULT] = result
        if error_msg is not None:
            cells[F_ERROR] = error_msg
        self._call("update_records", {
            "baseId": self.base_id,
            "tableId": self.table_id,
            "records": [{"recordId": record_id, "cells": cells}],
        }, timeout=90)


def _select_name(val) -> str:
    """singleSelect 单元格可能是 {'name':..,'id':..} 或字符串/None。"""
    if isinstance(val, dict):
        return (val.get("name") or "").strip()
    if isinstance(val, str):
        return val.strip()
    return ""


def _text(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        return (val.get("name") or "").strip()
    return str(val).strip()


# ───────────────────────────── 本地服务调用 ─────────────────────────────
def call_local(service_url: str, token: str, task_type: str, cells: dict) -> tuple[bool, dict | str]:
    """
    调用本地标准化服务。
    返回 (ok, payload_or_error_str)。
    ok=False 且 error 以 'TRANSIENT:' 开头表示本机服务不可达（应保留 pending 重试）。
    """
    if task_type == "brand":
        payload = {
            "attachment_values": _text(cells.get(F_IN_ATT)),
            "source_values": _text(cells.get(F_IN_SRC)),
        }
        endpoint = "/api/brand/normalize"
    elif task_type == "category":
        payload = {
            "product_name": _text(cells.get(F_IN_PNAME)),
            "client_category": _text(cells.get(F_IN_CCAT)),
        }
        endpoint = "/api/category/normalize"
    else:
        return False, f"未知 task_type={task_type!r}（应为 brand|category）"

    url = service_url.rstrip("/") + endpoint
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        return False, f"HTTP {exc.code}: {detail}"
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
        # 本机服务不可达 → 标记为瞬态，保留 pending 下一轮重试
        return False, f"TRANSIENT: 本地服务不可达 {url}: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"TRANSIENT: 调用本地服务异常 {url}: {exc}"

    if not body.get("success", False):
        return False, f"服务返回 success=false: {json.dumps(body, ensure_ascii=False)[:300]}"
    return True, body


# ───────────────────────────── 单条处理 ─────────────────────────────
def process_one(dt: DingTalkTable, service_url: str, token: str, rec: dict) -> None:
    rid = rec["recordId"]
    cells = rec["cells"]
    task_type = _select_name(cells.get(F_TASK_TYPE)).lower()

    # 先置 processing，避免同一轮重复处理 / 崩溃重入
    try:
        dt.update_status(rid, STATUS_PROCESSING)
    except Exception as exc:  # noqa: BLE001
        _log(f"  [!] {rid} 置 processing 失败（继续尝试）: {exc}")

    ok, payload = call_local(service_url, token, task_type, cells)
    if ok:
        dt.update_status(rid, STATUS_DONE, result=json.dumps(payload, ensure_ascii=False))
        _log(f"  [✓] {rid} ({task_type}) -> done")
    else:
        err = str(payload)
        if err.startswith("TRANSIENT:"):
            # 本机服务问题 → 复原为 pending，下一轮重试；仅记日志不写 error
            try:
                dt.update_status(rid, STATUS_PENDING)
            except Exception:
                pass
            _log(f"  [~] {rid} 瞬态失败，保留 pending 重试: {err[10:].strip()}")
        else:
            dt.update_status(rid, STATUS_ERROR, error_msg=err[:500])
            _log(f"  [✗] {rid} ({task_type}) -> error: {err[:160]}")


# ───────────────────────────── 主循环 ─────────────────────────────
def run_loop(dt: DingTalkTable, service_url: str, token: str,
             poll_secs: int, batch: int, once: bool) -> int:
    round_no = 0
    while True:
        round_no += 1
        try:
            pending = dt.query_pending(limit=batch)
        except Exception as exc:  # noqa: BLE001
            _log(f"[!] 轮询失败: {exc}")
            pending = []
        if pending:
            _log(f"[*] 第 {round_no} 轮：发现 {len(pending)} 条 pending")
            for rec in pending:
                process_one(dt, service_url, token, rec)
        else:
            _log(f"[*] 第 {round_no} 轮：无 pending 任务")
        if once:
            return 0
        time.sleep(poll_secs)


def main() -> int:
    env = _load_env()
    ap = argparse.ArgumentParser(description="钉钉 AI 表格中转代理（宿主机轮询）")
    ap.add_argument("--once", action="store_true", help="只跑一轮 pending 即退出（验证用）")
    ap.add_argument("--poll-secs", type=int, default=int(env.get("RELARY_POLL_SECS", "15")))
    ap.add_argument("--batch", type=int, default=int(env.get("RELARY_BATCH", "20")))
    ap.add_argument("--service-url", default=env.get("BRAND_SERVICE_URL", "http://localhost:8000"))
    ap.add_argument("--base-id", default=env.get("RELARY_BASE_ID", DEFAULT_BASE_ID))
    ap.add_argument("--table-id", default=env.get("RELARY_TABLE_ID", DEFAULT_TABLE_ID))
    ap.add_argument("--mcporter", default=env.get("MCPORTER_BIN", ""))
    ap.add_argument("--mcp-url", default=env.get("DINGTALK_MCP_URL", ""))
    ap.add_argument("--token", default=env.get("BRAND_API_TOKEN", ""))
    ap.add_argument("--log-file", default="",
                    help="守护模式日志文件；设置后 std/out+err 均写入该文件"
                         "（避免依赖 Start-Process 的 std 重定向，本机环境 Path/PATH "
                         "重复键会导致重定向报错）")
    args = ap.parse_args()

    # 日志落地：守护模式（被 start_relay.ps1 拉起）时把所有输出写入文件，
    # 这样无需依赖 Start-Process 的 std 重定向（该重定向在本机环境会因
    # Path/PATH 重复键抛出“字典中的关键字”异常）。
    if args.log_file:
        try:
            _lf = open(args.log_file, "a", encoding="utf-8")
            sys.stdout = _lf
            sys.stderr = _lf
        except OSError as exc:
            print(f"[警告] 无法打开日志文件 {args.log_file}: {exc}", file=sys.__stderr__)

    # 必填项
    if not args.token:
        print("[错误] 未指定 --token 且 .env 无 BRAND_API_TOKEN", file=sys.stderr)
        return 2
    if not args.mcp_url:
        print("[错误] 未指定 --mcp-url 且 .env 无 DINGTALK_MCP_URL", file=sys.stderr)
        return 2
    try:
        mcporter = _find_mcporter(args.mcporter)
    except FileNotFoundError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    dt = DingTalkTable(mcporter, args.mcp_url, args.base_id, args.table_id)
    _log(f"中转代理启动：base={args.base_id} table={args.table_id}")
    _log(f"  本机服务={args.service_url}  token={'已配置' if args.token else '缺失'}")
    _log(f"  mcporter={mcporter}")
    try:
        return run_loop(dt, args.service_url, args.token, args.poll_secs, args.batch, args.once)
    except KeyboardInterrupt:
        _log("[+] 已停止")
        return 0


if __name__ == "__main__":
    sys.exit(main())
