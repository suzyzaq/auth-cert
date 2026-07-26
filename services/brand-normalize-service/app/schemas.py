"""请求 / 响应模型（Pydantic）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NormalizeRequest(BaseModel):
    """POST /api/brand/normalize 请求体。

    attachment_values / source_values / candidate_values 兼容:
    数组、单字符串、JSON 字符串数组、逗号/顿号分隔字符串 —— 统一在核心层解包。
    """
    task_type: str = Field(default="brand_standardization")
    authorization_code: str = Field(default="")
    authorization_name: str = Field(default="")
    attachment_values: Any = Field(default_factory=list)
    source_values: Any = Field(default_factory=list)
    candidate_values: Any = Field(default_factory=list)
    requirements: Any = Field(default_factory=list)


class ValueDetail(BaseModel):
    raw_value: str
    matched: bool
    standard_brand: str = ""
    standard_brand_id: str = ""
    match_type: str = "unmatched"
    confidence: float = 0.0
    reason: str = ""
    fuzzy_candidates: list[dict] = Field(default_factory=list)
    scs_checked: bool = False
    scs_candidates: list[dict] = Field(default_factory=list)


class NormalizeResponse(BaseModel):
    success: bool
    authorization_code: str = ""
    attachment_standard_brands: list[str] = Field(default_factory=list)
    source_standard_brands: list[str] = Field(default_factory=list)
    attachment_standard_brand_ids: list[str] = Field(default_factory=list)
    source_standard_brand_ids: list[str] = Field(default_factory=list)
    matched_standard_brand: str = ""
    matched_standard_brand_id: str = ""
    same_brand: bool = False
    attachment_unmatched_values: list[str] = Field(default_factory=list)
    source_unmatched_values: list[str] = Field(default_factory=list)
    attachment_extra_brands: list[str] = Field(default_factory=list)
    source_extra_brands: list[str] = Field(default_factory=list)
    match_type: str = "unmatched"
    confidence: float = 0.0
    match_basis: str = ""
    needs_manual_review: bool = False
    error_code: str = ""
    message: str = ""
    # 明细（Dify 可选消费；不影响主字段）
    attachment_details: list[ValueDetail] = Field(default_factory=list)
    source_details: list[ValueDetail] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    brand_count: int
    alias_count: int
    data_version: str
    scs_enabled: bool = False
    # 品类侧（与品牌隔离）
    category_enabled: bool = False
    category_rule_count: int = 0
    category_fallback_count: int = 0
    category_data_version: str = ""


class ReloadResponse(BaseModel):
    success: bool
    reloaded: bool
    brand_count: int
    data_version: str
    message: str


# ===========================================================================
# 品类标准化（POST /api/category/normalize）—— 与品牌接口隔离
# ===========================================================================

class CategoryNormalizeRequest(BaseModel):
    """POST /api/category/normalize 请求体。

    product_name / client_category 兼容: 字符串、数组、JSON 字符串数组。
    品类映射本质是「一个 (商品名, 甲方类目) -> 一个欧菲斯三级品类」，
    批量时按首个非空元素一一配对（见响应 details）。
    """
    task_type: str = Field(default="category_standardization")
    authorization_code: str = Field(default="")
    authorization_name: str = Field(default="")
    product_name: Any = Field(default_factory=str)
    client_category: Any = Field(default_factory=str)
    requirements: Any = Field(default_factory=list)


class CategoryDetail(BaseModel):
    """单条 (product_name, client_category) 的品类匹配明细。"""
    product_name: str = ""
    client_category: str = ""
    kind1: str = ""
    kind2: str = ""
    kind3: str = ""
    category_matched: bool = False
    category_source: str = ""
    category_match_kind: str = ""
    confidence: float = 0.0
    matched_term: str = ""
    status: str = ""
    suggestion: str = ""


class CategoryNormalizeResponse(BaseModel):
    success: bool
    authorization_code: str = ""
    authorization_name: str = ""
    # 主结果（取首个配对；批量请读 details）
    kind1: str = ""
    kind2: str = ""
    kind3: str = ""
    category_matched: bool = False
    category_source: str = ""
    category_match_kind: str = ""
    confidence: float = 0.0
    matched_term: str = ""
    status: str = "unmatched"
    suggestion: str = ""
    needs_manual_review: bool = False
    error_code: str = ""
    message: str = ""
    # 批量明细（Dify 可选消费）
    details: list[CategoryDetail] = Field(default_factory=list)


class CategoryReloadResponse(BaseModel):
    success: bool
    reloaded: bool
    rule_count: int
    fallback_count: int
    data_version: str
    message: str
