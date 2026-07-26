"""
欧菲斯品牌标准化服务 —— FastAPI 入口。

端点:
  POST /api/brand/normalize    品牌标准化 + 同品牌判定（Bearer 鉴权）
  POST /api/brand/reload       品牌库热更新（Bearer 鉴权）
  POST /api/category/normalize 品类标准化（Bearer 鉴权，与品牌接口完全隔离）
  POST /api/category/reload    品类库热更新（Bearer 鉴权）
  GET  /health                 健康检查（免鉴权，不泄露路径/密钥）

品牌库 / 品类库在服务启动时各自独立加载一次（lifespan），请求期间只读内存索引。
两者内存索引、锁、reload、异常边界互不影响：一个加载失败不拖累另一个。
"""
from __future__ import annotations

import json
import logging
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.schemas import (
    NormalizeRequest, NormalizeResponse, ValueDetail,
    HealthResponse, ReloadResponse,
    CategoryNormalizeRequest, CategoryNormalizeResponse, CategoryDetail,
    CategoryReloadResponse,
)
from ofs_brand_core import (
    BrandRepository, BrandNormalizer, ScsBrandClient,
    CategoryRepository, CategoryNormalizer, normalized_text,
)

logger = logging.getLogger("brand-normalize")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_repo: BrandRepository | None = None
_normalizer: BrandNormalizer | None = None
_cat_repo: CategoryRepository | None = None
_cat_normalizer: CategoryNormalizer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _repo, _normalizer, _cat_repo, _cat_normalizer
    settings = get_settings()

    # ---- 品牌库（独立加载；失败不影响品类）----
    _repo = BrandRepository(settings.brand_data_path)
    try:
        _repo.load()
        scs_client = None
        if settings.scs_enabled and settings.scs_token_file.exists():
            scs_client = ScsBrandClient(
                token_file=settings.scs_token_file,
                endpoint=settings.scs_endpoint,
                timeout=settings.scs_timeout,
                cache_ttl=settings.scs_cache_ttl,
            )
            logger.info("SCS 在线品牌库回退已启用 (token_file=%s, available=%s)",
                        settings.scs_token_file, scs_client.available)
        elif settings.scs_enabled:
            logger.warning("SCS 已启用但 Token 文件不存在: %s（每周刷新脚本未运行？）",
                           settings.scs_token_file)
        _normalizer = BrandNormalizer(_repo, scs_client=scs_client)
        logger.info(
            "品牌库加载完成: %s 个标准品牌, %s 条别名, 版本 %s",
            _repo.brand_count, _repo.alias_count, _repo.data_version,
        )
    except Exception:  # noqa: BLE001
        logger.exception("品牌库加载失败（品类接口不受影响）")

    # ---- 品类库（独立加载；失败不影响品牌）----
    _cat_repo = CategoryRepository(
        settings.brand_data_path, fallback_path=settings.category_fallback_path
    )
    try:
        _cat_repo.load()
        _cat_normalizer = CategoryNormalizer(_cat_repo)
        logger.info(
            "品类库加载完成: %s 条品类规则, %s 条兜底规则, 版本 %s",
            _cat_repo.rule_count, _cat_repo.fallback_count, _cat_repo.data_version,
        )
    except Exception:  # noqa: BLE001
        logger.exception("品类库加载失败（品牌接口不受影响）")

    yield


app = FastAPI(title="OFS Brand Normalize Service", version="1.0.0", lifespan=lifespan)

_bearer = HTTPBearer(auto_error=False)


def require_token(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    """Bearer Token 鉴权。BRAND_API_TOKEN 未配置时拒绝所有业务请求（fail-closed）。"""
    settings = get_settings()
    if not settings.brand_api_token:
        raise HTTPException(status_code=503, detail="服务未配置 BRAND_API_TOKEN，业务接口不可用")
    if credentials is None or credentials.credentials != settings.brand_api_token:
        raise HTTPException(status_code=401, detail="鉴权失败")


# ------------------------------------------------------------------ 统一错误结构

def _error_response(status_code: int, error_code: str, message: str,
                    authorization_code: str = "", request: Request | None = None) -> JSONResponse:
    # 按端点选择响应结构：品类接口返回品类形，品牌接口返回品牌形（字段隔离）
    if request is not None and request.url.path.startswith("/api/category"):
        body = CategoryNormalizeResponse(
            success=False, authorization_code=authorization_code,
            category_matched=False, needs_manual_review=True,
            status="unmatched", error_code=error_code, message=message,
            suggestion=f"服务异常: {message}",
        ).model_dump()
    else:
        body = NormalizeResponse(
            success=False, authorization_code=authorization_code,
            same_brand=False, needs_manual_review=True,
            match_type="unmatched", confidence=0.0,
            error_code=error_code, message=message,
            match_basis=f"服务异常: {message}",
        ).model_dump()
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    return _error_response(exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail), request=request)


from fastapi.exceptions import RequestValidationError  # noqa: E402


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    return _error_response(422, "INVALID_REQUEST", "请求体格式错误，无法解析 JSON 或字段类型不符", request=request)


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
    logger.exception("未处理异常")
    return _error_response(500, "INTERNAL_ERROR", "服务内部错误，请稍后重试", request=request)


# ------------------------------------------------------------------ 业务端点

@app.post("/api/brand/normalize", response_model=NormalizeResponse,
          dependencies=[Depends(require_token)])
def normalize_brands(req: NormalizeRequest) -> NormalizeResponse:
    if _normalizer is None:
        raise HTTPException(status_code=503, detail="品牌库尚未加载完成")
    if req.task_type and req.task_type != "brand_standardization":
        return NormalizeResponse(
            success=False, authorization_code=req.authorization_code,
            same_brand=False, needs_manual_review=True,
            error_code="INVALID_TASK_TYPE",
            message=f"不支持的 task_type: {req.task_type}",
            match_basis="task_type 必须为 brand_standardization",
        )

    result = _normalizer.compare(req.attachment_values, req.source_values)

    def _details(matches) -> list[ValueDetail]:
        return [ValueDetail(
            raw_value=m.raw_value, matched=m.matched,
            standard_brand=m.standard_brand, standard_brand_id=m.standard_id,
            match_type=m.match_type, confidence=m.confidence, reason=m.reason,
            fuzzy_candidates=m.fuzzy_candidates,
            scs_checked=m.scs_checked, scs_candidates=m.scs_candidates,
        ) for m in matches]

    att_matched = [m for m in result.attachment_matches if m.matched]
    src_matched = [m for m in result.source_matches if m.matched]

    return NormalizeResponse(
        success=True,
        authorization_code=req.authorization_code,
        attachment_standard_brands=sorted({m.standard_brand for m in att_matched}),
        source_standard_brands=sorted({m.standard_brand for m in src_matched}),
        attachment_standard_brand_ids=sorted({m.standard_id for m in att_matched}),
        source_standard_brand_ids=sorted({m.standard_id for m in src_matched}),
        matched_standard_brand=result.matched_standard_brand,
        matched_standard_brand_id=result.matched_standard_brand_id,
        same_brand=result.same_brand,
        attachment_unmatched_values=[m.raw_value for m in result.attachment_matches if not m.matched],
        source_unmatched_values=[m.raw_value for m in result.source_matches if not m.matched],
        attachment_extra_brands=result.attachment_extra_brands,
        source_extra_brands=result.source_extra_brands,
        match_type=result.match_type,
        confidence=round(result.confidence, 4),
        match_basis=result.match_basis,
        needs_manual_review=result.needs_manual_review,
        error_code="",
        message="品牌标准化完成",
        attachment_details=_details(result.attachment_matches),
        source_details=_details(result.source_matches),
    )


@app.post("/api/brand/reload", response_model=ReloadResponse,
          dependencies=[Depends(require_token)])
def reload_brands() -> ReloadResponse:
    if _repo is None:
        raise HTTPException(status_code=503, detail="品牌库尚未初始化")
    reloaded = _repo.reload_if_changed()
    if not reloaded:
        _repo.load()  # 强制重载（管理员显式调用 reload 的语义）
        reloaded = True
    return ReloadResponse(
        success=True, reloaded=reloaded,
        brand_count=_repo.brand_count, data_version=_repo.data_version,
        message="品牌库已重新加载",
    )


# ------------------------------------------------------------------ 品类标准化（与品牌接口隔离）

def _expand_values(value: Any) -> list[str]:
    """product_name / client_category 多形态输入 -> 干净字符串列表。

    兼容: 单字符串、逗号/顿号/分号分隔字符串、JSON 字符串数组、Python 数组。
    """
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                arr = json.loads(text)
                if isinstance(arr, list):
                    return [normalized_text(x) for x in arr if normalized_text(x)]
            except (json.JSONDecodeError, TypeError):
                pass
        return [p.strip() for p in re.split(r"[,，、;；\n\r]+", text) if p.strip()]
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for v in value:
            out.extend(_expand_values(v))
        return out
    return [normalized_text(value)]


def _category_error(status_code: int, error_code: str, message: str) -> JSONResponse:
    body = CategoryNormalizeResponse(
        success=False,
        category_matched=False,
        needs_manual_review=True,
        status="unmatched",
        error_code=error_code,
        message=message,
        suggestion=f"服务异常: {message}",
    ).model_dump()
    return JSONResponse(status_code=status_code, content=body)


@app.post("/api/category/normalize", response_model=CategoryNormalizeResponse,
          dependencies=[Depends(require_token)])
def normalize_category(req: CategoryNormalizeRequest) -> CategoryNormalizeResponse:
    if _cat_normalizer is None:
        raise HTTPException(status_code=503, detail="品类库尚未加载完成")
    if req.task_type and req.task_type != "category_standardization":
        return CategoryNormalizeResponse(
            success=False,
            authorization_code=req.authorization_code,
            category_matched=False, needs_manual_review=True,
            error_code="INVALID_TASK_TYPE",
            message=f"不支持的 task_type: {req.task_type}",
            status="unmatched",
            suggestion="task_type 必须为 category_standardization",
        )

    product_values = _expand_values(req.product_name)
    client_values = _expand_values(req.client_category)
    n = max(len(product_values), len(client_values)) or 1
    pairs = [
        (product_values[i] if i < len(product_values) else "",
         client_values[i] if i < len(client_values) else "")
        for i in range(n)
    ]

    details: list[CategoryDetail] = []
    for p, c in pairs:
        m = _cat_normalizer.normalize(p, c)
        details.append(CategoryDetail(
            product_name=p, client_category=c,
            kind1=m.kind1, kind2=m.kind2, kind3=m.kind3,
            category_matched=(m.status == "matched" and bool(m.kind3)),
            category_source=m.source, category_match_kind=m.match_kind,
            confidence=round(m.confidence, 4),
            matched_term=m.matched_term, status=m.status,
            suggestion=m.suggestion,
        ))

    primary = details[0]
    return CategoryNormalizeResponse(
        success=True,
        authorization_code=req.authorization_code,
        authorization_name=req.authorization_name,
        kind1=primary.kind1, kind2=primary.kind2, kind3=primary.kind3,
        category_matched=primary.category_matched,
        category_source=primary.category_source,
        category_match_kind=primary.category_match_kind,
        confidence=primary.confidence,
        matched_term=primary.matched_term,
        status=primary.status,
        suggestion=primary.suggestion,
        needs_manual_review=(primary.status != "matched" or not primary.kind3),
        error_code="",
        message="品类标准化完成",
        details=details,
    )


@app.post("/api/category/reload", response_model=CategoryReloadResponse,
          dependencies=[Depends(require_token)])
def reload_categories() -> CategoryReloadResponse:
    global _cat_normalizer
    if _cat_repo is None:
        raise HTTPException(status_code=503, detail="品类库尚未初始化")
    reloaded = _cat_repo.reload_if_changed()
    if not reloaded:
        _cat_repo.load()  # 强制重载（管理员显式调用 reload 的语义）
        reloaded = True
    _cat_normalizer = CategoryNormalizer(_cat_repo)
    return CategoryReloadResponse(
        success=True, reloaded=reloaded,
        rule_count=_cat_repo.rule_count, fallback_count=_cat_repo.fallback_count,
        data_version=_cat_repo.data_version, message="品类库已重新加载",
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    if _repo is None:
        return HealthResponse(status="loading", brand_count=0, alias_count=0,
                              data_version="", scs_enabled=False)
    scs_ok = bool(_normalizer and _normalizer.scs_client and _normalizer.scs_client.available)
    cat_ok = bool(_cat_repo and _cat_repo.ready)
    return HealthResponse(
        status="ok",
        brand_count=_repo.brand_count,
        alias_count=_repo.alias_count,
        data_version=_repo.data_version,
        scs_enabled=scs_ok,
        category_enabled=cat_ok,
        category_rule_count=_cat_repo.rule_count if cat_ok else 0,
        category_fallback_count=_cat_repo.fallback_count if cat_ok else 0,
        category_data_version=_cat_repo.data_version if cat_ok else "",
    )


if __name__ == "__main__":
    import uvicorn
    s = get_settings()
    uvicorn.run("app.main:app", host=s.host, port=s.port)
