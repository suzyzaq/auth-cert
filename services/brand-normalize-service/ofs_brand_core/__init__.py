"""
ofs_brand_core — 欧菲斯品牌标准化核心模块（确定性逻辑，无 LLM 依赖）

提取自:
  - brand-matcher Skill: app/matching/normalize.py 的 NFKC 归一化 / comparison_key
  - brand-recognition Skill: scripts/retriever.py 的黑名单防护 / 别名索引 / 模糊召回

供 Skill / CLI / HTTP API 共同调用。
"""
from .normalize import normalized_text, comparison_key, split_aliases, split_multi_values
from .repository import BrandRepository, StandardBrand
from .matcher import BrandNormalizer, ValueMatch, CompareResult
from .scs_client import ScsBrandClient, ScsBrand
from .category_core import (
    CategoryMatch, CategoryIndex, CategoryMapper,
    CategoryRepository, CategoryNormalizer,
)

__all__ = [
    "normalized_text", "comparison_key", "split_aliases", "split_multi_values",
    "BrandRepository", "StandardBrand",
    "BrandNormalizer", "ValueMatch", "CompareResult",
    "ScsBrandClient", "ScsBrand",
    "CategoryMatch", "CategoryIndex", "CategoryMapper",
    "CategoryRepository", "CategoryNormalizer",
]
