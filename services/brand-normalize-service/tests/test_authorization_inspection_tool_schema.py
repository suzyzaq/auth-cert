import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "dify" / "authorization-inspection-tool.openapi.json"


def test_inspection_schema_exposes_only_read_only_operations():
    document = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert document["openapi"] == "3.0.3"
    assert document["servers"][0]["url"] == "http://brand-normalize-service:8000"
    assert set(document["paths"]) == {
        "/health",
        "/api/brand/normalize",
        "/api/category/normalize",
    }
    operation_ids = {
        operation["operationId"]
        for path in document["paths"].values()
        for operation in path.values()
    }
    assert operation_ids == {
        "brandServiceHealth",
        "normalizeBrand",
        "normalizeCategory",
    }
    assert "bearerAuth" in document["components"]["securitySchemes"]


def test_normalize_operations_require_expected_arrays():
    document = json.loads(SCHEMA.read_text(encoding="utf-8"))
    brand = document["paths"]["/api/brand/normalize"]["post"]
    category = document["paths"]["/api/category/normalize"]["post"]
    brand_schema = brand["requestBody"]["content"]["application/json"]["schema"]
    category_schema = category["requestBody"]["content"]["application/json"]["schema"]
    assert set(brand_schema["required"]) == {"attachment_values", "source_values"}
    assert set(category_schema["required"]) == {"product_name", "client_category"}
