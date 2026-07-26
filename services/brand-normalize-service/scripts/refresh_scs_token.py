#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCS 凭证每周刷新脚本（无会话绑定，每周拉取即可）。

原理:
  复用 Kimi WebBridge 控制的「已登录」浏览器会话，打开 SCS 品牌列表页，
  注入 XHR hook 捕获真实 Authorization(JWT) + X-XSRF-TOKEN 请求头，
  写入 Token 文件。brand-normalize-service 按文件 mtime 自动热加载，
  无需重启服务。

前置条件:
  1. Kimi WebBridge 已启动（默认 http://127.0.0.1:10086）。
  2. 浏览器存在 SCS 登录态（officemate SSO 记住了登录，首次可能需人工登录一次）。
  3. WebBridge 会话已创建（默认 scs-brand-api）。

用法:
  python scripts/refresh_scs_token.py
  python scripts/refresh_scs_token.py --out C:/Users/Lenovo/.workbuddy/secrets/scs-token.json
  python scripts/refresh_scs_token.py --session scs-brand-api --webbridge http://127.0.0.1:10086

退出码: 0=成功, 1=WebBridge 不可用, 2=未捕获到 Token(可能需重新登录 SCS)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

WEBBRIDGE_URL = "http://127.0.0.1:10086"
SESSION = "scs-brand-api"
BRAND_LIST_URL = "https://scs.officemate.cn/scspro/#/product/brand-list"
DEFAULT_OUT = Path.home() / ".workbuddy" / "secrets" / "scs-token.json"
HOOK_JS = (
    "(()=>{"
    "if(window.__scsHooked)return true;"
    "const oX=window.XMLHttpRequest.prototype.open;"
    "const oS=window.XMLHttpRequest.prototype.send;"
    "window.__hdrs=null;"
    "window.XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oX.apply(this,arguments);};"
    "window.XMLHttpRequest.prototype.send=function(b){"
    "  const self=this;"
    "  this.addEventListener('readystatechange',function(){"
    "    if(self.readyState===4 && typeof self.__u==='string' && self.__u.indexOf('/scs-purchase-api/')>=0){"
    "      const h=self.getResponseHeader?self.getResponseHeader('X-XSRF-TOKEN'):null;"
    "      const reqH=self.__u; const auth=self.getResponseHeader?self.getResponseHeader('Authorization'):null;"
    "      let reqAuth=self.__getReqHeader?self.__getReqHeader('Authorization'):null;"
    "      const hd={url:self.__u, method:self.__m};"
    "      try{hd.Authorization=auth||reqAuth||self.__reqAuth||(self.__reqHeaders&&self.__reqHeaders['Authorization'])||'';}catch(e){}"
    "      try{hd['X-XSRF-TOKEN']=h||(self.__reqHeaders&&self.__reqHeaders['X-XSRF-TOKEN'])||'';}catch(e){}"
    "      window.__hdrs=hd;"
    "    }"
    "  });"
    "  return oS.apply(this,arguments);"
    "};"
    "window.__scsHooked=true;return true;"
    "})();"
)


def _post(url: str, payload: dict, timeout: float = 60.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ok(r: dict) -> bool:
    if not isinstance(r, dict):
        return False
    if "success" in r:
        return bool(r.get("success"))
    return r.get("code", 200) == 200


def wb(cmd: str, session: str, params: dict | None = None, url: str = WEBBRIDGE_URL) -> dict:
    payload = {"command": cmd, "session": session}
    if params is not None:
        payload["params"] = params
    try:
        res = _post(f"{url}/v1/run", payload, timeout=90.0)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] WebBridge 调用失败: {exc}", file=sys.stderr)
        sys.exit(1)
    if not _ok(res):
        print(f"[错误] WebBridge 返回失败: {json.dumps(res, ensure_ascii=False)[:500]}",
              file=sys.stderr)
        sys.exit(1)
    return res


def capture(scs_url: str, out: Path, session: str, wb_url: str) -> bool:
    # 1) 确保会话存在
    wb("session", session, {"action": "create"}, wb_url)
    # 2) 注入 XHR hook
    wb("evaluate", session, {"code": HOOK_JS}, wb_url)
    # 3) 打开品牌列表页（已登录会话会自动带上 SSO 态，无需再次登录）
    wb("navigate", session, {"url": scs_url}, wb_url)
    # 4) 触发一次真实 XHR（随便搜一个品牌名，status=1）；页面有搜索框就填
    try:
        wb("fill", session, {"selector": "input[placeholder*='品牌']",
                              "value": "佳能"}, wb_url)
    except Exception:
        pass  # 选择器不匹配则依赖页面已有请求
    try:
        wb("click", session, {"selector": "button:contains('搜索')"}, wb_url)
    except Exception:
        pass
    # 5) 读取捕获的 Token
    for _ in range(10):
        data = wb("evaluate", session,
                  {"code": "JSON.stringify(window.__hdrs||null)"}, wb_url)
        val = (data.get("result") or data.get("data") or "")
        if isinstance(val, dict):
            raw = json.dumps(val, ensure_ascii=False)
        else:
            raw = str(val)
        if raw and raw not in ("null", "None", ""):
            try:
                hdrs = json.loads(raw)
            except ValueError:
                hdrs = None
            if hdrs and hdrs.get("Authorization", "").lower().startswith("bearer "):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({
                    "Authorization": hdrs["Authorization"],
                    "X-XSRF-TOKEN": hdrs.get("X-XSRF-TOKEN", ""),
                    "updated_at": __import__("datetime").datetime.now().isoformat(),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[成功] SCS Token 已刷新并写入: {out}")
                return True
    print("[失败] 未捕获到 Authorization 头。可能 SCS 登录态已失效，"
          "请在浏览器中手动登录 SCS 后重试，或在 Kimi WebBridge 中重新登录。",
          file=sys.stderr)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="SCS 凭证每周刷新脚本")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Token 输出文件路径")
    ap.add_argument("--session", default=SESSION)
    ap.add_argument("--webbridge", default=WEBBRIDGE_URL)
    ap.add_argument("--scs-url", default=BRAND_LIST_URL)
    args = ap.parse_args()

    ok = capture(args.scs_url, Path(args.out), args.session, args.webbridge)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
