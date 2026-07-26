#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCS 候选回流 Webhook 接收器（宿主机常驻，Dify 复核节点触发）。

为什么需要它：
  brand-normalize-service 容器内 matcher.db 是 :ro 只读挂载，不能在容器内写库；
  且云端 Dify 无法直接 exec 宿主机脚本。因此回流写库必须在【宿主机】执行，
  本接收器就跑在宿主机，由 Dify「请求」节点 POST 确认清单过来触发。

职责：
  1. Bearer 鉴权（复用 BRAND_API_TOKEN）
  2. 接收确认清单（与 scs_backfill.py 输入同 schema）
  3. 落盘留痕（.scs_backfill_log/<ts>.json）便于追溯
  4. 调用 scs_backfill.py --apply 写 matcher.db（宿主机真实路径，可写）
  5. 调容器 /api/brand/reload 热重载内存索引（写后必须 reload 才生效）

用法：
  # 默认仅本机可达（Dify 经内网穿透/同网访问）
  python scripts/backfill_webhook.py
  # 指定监听与覆盖配置
  python scripts/backfill_webhook.py --host 0.0.0.0 --port 8900 \
      --db C:/.../matcher.db --token <BRAND_API_TOKEN>

请求示例（Dify「请求」节点 Body，JSON）：
  [{"firm_code":182805,"firm_name":"洁佳人","standard_brand":"洁佳人"},
   {"firm_code":7563,"firm_name":"惠普企业版","standard_brand":"惠普/HP"}]
  或包一层：{"items":[...],"dry_run":false,"reload":true}

响应：
  {"ok":true,"applied":2,"skipped":0,"dry_run":false,
   "reload_done":true,"reload_ok":true,"log_file":"...","detail":"..."}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
SCS_SCRIPT = PROJECT_ROOT / "scripts" / "scs_backfill.py"
LOG_DIR = PROJECT_ROOT / ".scs_backfill_log"
DEFAULT_RELOAD_URL = "http://localhost:8000/api/brand/reload"


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


def run_backfill(db: str, items: list, dry_run: bool, log_path: Path) -> dict:
    """落盘确认清单并调用 scs_backfill.py，返回结构化结果。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps({"at": _now_iso(), "db": db, "dry_run": dry_run, "items": items},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp = log_path.with_suffix(".input.json")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [sys.executable, str(SCS_SCRIPT), "--db", db, "--input", str(tmp)]
    if not dry_run:
        cmd.append("--apply")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=300)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "scs_backfill 超时(>300s)", "log_file": str(log_path)}
    out = (proc.stdout or "") + (proc.stderr or "")
    applied = skipped = 0
    m = re.search(r"已写入\s*(\d+)\s*条", out)
    if m:
        applied = int(m.group(1))
    m = re.search(r"跳过\s*(\d+)\s*条", out)
    if m:
        skipped = int(m.group(1))
    return {
        "ok": proc.returncode == 0,
        "applied": applied,
        "skipped": skipped,
        "returncode": proc.returncode,
        "stdout_tail": out.strip()[-800:],
        "log_file": str(log_path),
    }


def do_reload(reload_url: str, token: str) -> dict:
    req = urllib.request.Request(
        reload_url, data=b"{}", method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(body.get("success")), "response": body}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


class Handler(BaseHTTPRequestHandler):
    token = ""
    db = ""
    reload_url = ""

    def _send(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _auth_ok(self) -> bool:
        ah = self.headers.get("Authorization", "")
        if not ah.startswith("Bearer "):
            return False
        return ah[len("Bearer "):].strip() == Handler.token

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") in ("", "/health"):
            self._send(200, {
                "status": "ok",
                "service": "backfill-webhook",
                "db": Handler.db,
                "token_set": bool(Handler.token),
                "reload_url": Handler.reload_url,
            })
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path.rstrip("/") != "/backfill":
            self._send(404, {"error": "only POST /backfill supported"})
            return
        if not self._auth_ok():
            self._send(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            # 兼容各种编码（UTF-8 / BOM / 代理透传）：utf-8-sig 优先，latin-1 兜底永不失败
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            body = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            self._send(400, {"error": f"invalid json: {exc}"})
            return

        # 兼容两种 Body：直接数组，或 {"items":[...], "dry_run":bool, "reload":bool}
        if isinstance(body, list):
            items = body
            dry_run = False
            do_reload_flag = True
        elif isinstance(body, dict):
            items = body.get("items", [])
            dry_run = bool(body.get("dry_run", False))
            do_reload_flag = bool(body.get("reload", True))
        else:
            self._send(400, {"error": "body must be array or object"})
            return

        if not isinstance(items, list) or not items:
            self._send(400, {"error": "items 为空或非数组"})
            return
        for it in items:
            if not isinstance(it, dict) or not str(it.get("firm_name", "")).strip():
                self._send(400, {"error": "每条需含非空 firm_name", "bad_item": it})
                return

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path = LOG_DIR / f"backfill-{ts}.json"
        res = run_backfill(Handler.db, items, dry_run, log_path)

        reload_res = None
        if res["ok"] and not dry_run and do_reload_flag:
            reload_res = do_reload(Handler.reload_url, Handler.token)

        payload = {
            "ok": res["ok"],
            "applied": res.get("applied", 0),
            "skipped": res.get("skipped", 0),
            "dry_run": dry_run,
            "log_file": res.get("log_file"),
            "detail": res.get("stdout_tail", ""),
        }
        if reload_res is not None:
            payload["reload_done"] = True
            payload["reload_ok"] = reload_res.get("ok")
            payload["reload_detail"] = reload_res
        code = 200 if (res["ok"] and (dry_run or reload_res is None or reload_res.get("ok"))) else 207
        self._send(code, payload)

    def log_message(self, fmt, *args):  # 静音默认访问日志
        return


def main() -> int:
    env = _load_env()
    ap = argparse.ArgumentParser(description="SCS 回流 Webhook 接收器（宿主机）")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址（Dify 经穿透/同网访问用 0.0.0.0）")
    ap.add_argument("--port", type=int, default=8900)
    ap.add_argument("--db", default=env.get("BRAND_DB_PATH", ""), help="宿主机 matcher.db 真实路径（可写）")
    ap.add_argument("--token", default=env.get("BRAND_API_TOKEN", ""), help="Bearer 鉴权 Token")
    ap.add_argument("--reload-url", default=DEFAULT_RELOAD_URL, help="容器内 /api/brand/reload 地址")
    args = ap.parse_args()

    if not args.db:
        print("[错误] 未指定 --db 且 .env 无 BRAND_DB_PATH", file=sys.stderr)
        return 2
    if not args.token:
        print("[错误] 未指定 --token 且 .env 无 BRAND_API_TOKEN", file=sys.stderr)
        return 2
    if not Path(args.db).exists():
        print(f"[错误] 品牌库不存在: {args.db}", file=sys.stderr)
        return 2

    Handler.token = args.token
    Handler.db = args.db
    Handler.reload_url = args.reload_url

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[+] backfill-webhook 监听 http://{args.host}:{args.port}")
    print(f"    POST /backfill  (Bearer 鉴权) -> 写库 {args.db}")
    print(f"    reload -> {args.reload_url}")
    print(f"    GET  /health   (免鉴权)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] 已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
