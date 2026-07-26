"""配置模块 —— 全部通过环境变量注入，不写死任何凭据。"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# brand-matcher Skill 的品牌主库默认位置（与 brand-recognition 的自动发现逻辑一致）
_DEFAULT_DB = Path.home() / ".workbuddy" / "skills" / "brand-matcher" / "data" / "matcher.db"

# SCS Token 文件默认位置（由每周刷新脚本 scripts/refresh_scs_token.py 维护）
_DEFAULT_SCS_TOKEN = Path.home() / ".workbuddy" / "secrets" / "scs-token.json"

# 品类兜底规则（从 brand-matcher 同步，运行时本地化，避免依赖 Skill 内部路径）
_DEFAULT_CATEGORY_FALLBACK = (
    Path(__file__).resolve().parent.parent / "config" / "fallback_categories.yaml"
)


class Settings:
    def __init__(self) -> None:
        self.brand_api_token: str = os.environ.get("BRAND_API_TOKEN", "")
        self.brand_data_path: Path = Path(
            os.environ.get("BRAND_DATA_PATH", str(_DEFAULT_DB))
        )
        # 预留：独立别名库路径（当前正式别名在 matcher.db 的 brand_alias 表内）
        self.brand_alias_data_path: str = os.environ.get("BRAND_ALIAS_DATA_PATH", "")
        self.host: str = os.environ.get("HOST", "0.0.0.0")
        self.port: int = int(os.environ.get("PORT", "8000"))
        # ---- SCS 在线品牌库回退（本地未命中时查询，仅启用品牌，只作候选）----
        self.scs_enabled: bool = os.environ.get("SCS_ENABLED", "1") not in ("0", "false", "False")
        self.scs_token_file: Path = Path(
            os.environ.get("SCS_TOKEN_FILE", str(_DEFAULT_SCS_TOKEN))
        )
        self.scs_endpoint: str = os.environ.get(
            "SCS_ENDPOINT",
            "https://scs.officemate.cn/scs-purchase-api/brand/getBrandSapList",
        )
        self.scs_timeout: float = float(os.environ.get("SCS_TIMEOUT", "5"))
        self.scs_cache_ttl: float = float(os.environ.get("SCS_CACHE_TTL", "3600"))
        # ---- 品类标准化（与品牌接口隔离；复用同库 rules 表的品类映射 + 兜底 yaml）----
        self.category_fallback_path: Path = Path(
            os.environ.get("CATEGORY_FALLBACK_PATH", str(_DEFAULT_CATEGORY_FALLBACK))
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
