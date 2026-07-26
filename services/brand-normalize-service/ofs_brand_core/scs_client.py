"""
SCS 在线品牌库客户端 —— 本地品牌库未命中时的远程回退查询。

接口契约（浏览器逆向确认，2026-07-23）:
  POST https://scs.officemate.cn/scs-purchase-api/brand/getBrandSapList
  Headers: Authorization: Bearer <JWT>, X-XSRF-TOKEN: <token>
  Body:    {"page":1, "pageSize":20, "FirmName":"<品牌名>", "status":1}
           status=1 仅启用品牌（业务要求：仅启用状态的品牌可用）
  Response: {"code":200, "data":{"list":[{"FirmCode","FirmName","status","status_str"}], "total"}}

凭证供给（每周刷新，无需绑定会话）:
  Token 保存在 JSON 文件（SCS_TOKEN_FILE），键为 Authorization / X-XSRF-TOKEN。
  由 scripts/refresh_scs_token.py 每周通过浏览器登录 SCS 抓取更新。
  客户端按文件 mtime 自动热加载最新 Token，服务无需重启。

安全边界:
  - SCS 命中结果只作为候选（scs_candidate），绝不自动确认同品牌；
  - SCS 不可用 / Token 过期 / 网络异常时静默降级，不影响本地匹配主流程；
  - 查询结果带 TTL 内存缓存，避免高频请求穿透到 SCS。
"""
from __future__ import annotations

import json
import logging
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("brand-normalize.scs")

_DEFAULT_ENDPOINT = "https://scs.officemate.cn/scs-purchase-api/brand/getBrandSapList"


@dataclass
class ScsBrand:
    """SCS 品牌库记录（仅启用状态）"""
    firm_code: int
    firm_name: str
    status: int
    status_str: str = "启用"

    def as_candidate(self) -> dict:
        return {
            "source": "scs",
            "scs_firm_code": self.firm_code,
            "scs_firm_name": self.firm_name,
            "scs_status": self.status_str,
        }


class ScsBrandClient:
    """SCS 品牌库查询客户端。所有失败均降级为空结果，绝不抛异常到调用方。"""

    def __init__(
        self,
        token_file: str | Path,
        endpoint: str = _DEFAULT_ENDPOINT,
        timeout: float = 5.0,
        cache_ttl: float = 3600.0,
        page_size: int = 20,
    ):
        # str 转 Path；其他对象（Path 或具备 exists()/stat()/read_text() 的桩对象）原样保留
        self.token_file = Path(token_file) if isinstance(token_file, str) else token_file
        self.endpoint = endpoint
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.page_size = page_size
        self._lock = threading.RLock()
        self._headers: dict[str, str] = {}
        self._token_mtime: float = 0.0
        # 查询缓存: name -> (expire_ts, list[ScsBrand])；空结果也缓存，防穿透
        self._cache: dict[str, tuple[float, list[ScsBrand]]] = {}
        self._degraded_until: float = 0.0   # 连续失败后的熔断窗口

    # ------------------------------------------------------------ token

    @property
    def available(self) -> bool:
        """Token 文件存在且可解析时视为可用。"""
        return bool(self._load_tokens())

    def _load_tokens(self) -> dict[str, str]:
        """读取 Token 文件；mtime 变化时热加载（每周刷新脚本更新文件即可生效）。"""
        if not self.token_file or not self.token_file.exists():
            return {}
        try:
            mtime = self.token_file.stat().st_mtime
            with self._lock:
                if mtime != self._token_mtime or not self._headers:
                    raw = json.loads(self.token_file.read_text(encoding="utf-8"))
                    # 兼容大小写/下划线键名
                    norm = {str(k).replace("_", "-").lower(): str(v) for k, v in raw.items()}
                    auth = norm.get("authorization", "")
                    xsrf = norm.get("x-xsrf-token", "")
                    if auth and not auth.lower().startswith("bearer "):
                        auth = f"Bearer {auth}"
                    if not auth:
                        return {}
                    self._headers = {
                        "Authorization": auth,
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/plain, */*",
                    }
                    if xsrf:
                        self._headers["X-XSRF-TOKEN"] = xsrf
                    self._token_mtime = mtime
                    # Token 更新后清缓存并解除熔断
                    self._cache.clear()
                    self._degraded_until = 0.0
                    logger.info("SCS Token 已加载/热更新 (mtime=%s)", mtime)
                return dict(self._headers)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("SCS Token 文件读取失败: %s", exc)
            return {}

    # ------------------------------------------------------------ query

    def search_enabled(self, name: str) -> list[ScsBrand]:
        """按品牌名查询 SCS 品牌库，仅返回启用状态（status=1）的品牌。

        任何异常（网络 / 鉴权失效 / 响应异常）均返回空列表并记录日志。
        """
        name = (name or "").strip()
        if not name:
            return []
        now = time.time()
        if now < self._degraded_until:
            return []          # 熔断窗口内不再请求
        with self._lock:
            hit = self._cache.get(name)
            if hit and hit[0] > now:
                return list(hit[1])

        headers = self._load_tokens()
        if not headers:
            return []

        body = json.dumps({
            "page": 1, "pageSize": self.page_size,
            "FirmName": name, "status": 1,        # 1 = 仅启用
        }).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.warning("SCS 查询失败（降级为本地结果）: %s", exc)
            self._degraded_until = now + 300      # 5 分钟熔断
            return []

        if not isinstance(payload, dict) or payload.get("code") != 200:
            # 401/Token 过期通常也走 code!=200 分支
            logger.warning("SCS 返回异常 code=%s msg=%s（可能 Token 过期，需运行每周刷新脚本）",
                           payload.get("code"), payload.get("msg") or payload.get("message"))
            self._degraded_until = now + 300
            return []

        rows = (payload.get("data") or {}).get("list") or []
        out: list[ScsBrand] = []
        for r in rows:
            try:
                # 双重校验：即使请求了 status=1，仍逐行确认启用状态
                if int(r.get("status", 0)) != 1:
                    continue
                out.append(ScsBrand(
                    firm_code=int(r.get("FirmCode", 0)),
                    firm_name=str(r.get("FirmName", "")).strip(),
                    status=1,
                    status_str=str(r.get("status_str", "启用")),
                ))
            except (ValueError, TypeError):
                continue

        with self._lock:
            self._cache[name] = (now + self.cache_ttl, list(out))
        return out
