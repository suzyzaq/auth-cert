"""Validate the deployed read-only Dify normalization tool without logging secrets."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def evaluate_results(
    health: dict[str, Any],
    brand: dict[str, Any],
    category: dict[str, Any],
    unauthorized_status: int,
) -> dict[str, Any]:
    checks = {
        "health": health.get("status") == "ok"
        and int(health.get("brand_count", 0)) > 0
        and health.get("category_enabled") is True,
        "brand": brand.get("success") is True
        and brand.get("same_brand") is True
        and bool(brand.get("matched_standard_brand_id")),
        "category": category.get("success") is True
        and category.get("category_matched") is True
        and category.get("kind3") == "陶瓷杯",
        "authentication": unauthorized_status == 401,
    }
    return {
        "status": "ok" if all(checks.values()) else "failed",
        "checks": checks,
    }


def request_json(
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json"}
    data = None
    method = "GET"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        method = "POST"
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8")
        return error.code, json.loads(payload) if payload else {}


def main() -> int:
    base_url = os.environ.get("DIFY_TOOL_BASE_URL", "").strip()
    token = os.environ.get("BRAND_API_TOKEN", "").strip()
    if not base_url or not token:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "checks": {},
                    "error": "DIFY_TOOL_BASE_URL and BRAND_API_TOKEN are required",
                }
            )
        )
        return 1

    _, health = request_json(base_url, "/health")
    _, brand = request_json(
        base_url,
        "/api/brand/normalize",
        token=token,
        body={
            "task_type": "brand_standardization",
            "authorization_code": "DIFY-SMOKE-001",
            "authorization_name": "Dify验收",
            "attachment_values": ["惠普 HP"],
            "source_values": ["惠普/HP"],
            "candidate_values": [],
            "requirements": ["分别标准化附件品牌和数据库品牌"],
        },
    )
    _, category = request_json(
        base_url,
        "/api/category/normalize",
        token=token,
        body={
            "task_type": "category_standardization",
            "authorization_code": "DIFY-SMOKE-001",
            "authorization_name": "Dify验收",
            "product_name": [],
            "client_category": ["茶杯"],
            "requirements": ["映射到欧菲斯三级品类"],
        },
    )
    unauthorized_status, _ = request_json(
        base_url,
        "/api/brand/normalize",
        body={
            "attachment_values": ["惠普 HP"],
            "source_values": ["惠普/HP"],
        },
    )
    result = evaluate_results(health, brand, category, unauthorized_status)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
