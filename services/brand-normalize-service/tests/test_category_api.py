"""品类标准化接口测试 —— TestClient 全链路。

验证 POST /api/category/normalize 与品牌接口隔离、鉴权、兜底命中、未匹配、批量。
兜底案例（client_category -> 欧菲斯小类）确定性高，不依赖 rules 表随机内容。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRAND_API_TOKEN", "test-token-123")
os.environ["SCS_ENABLED"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

AUTH = {"Authorization": "Bearer test-token-123"}
URL = "/api/category/normalize"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _post(client, product_name="", client_category="", **extra):
    body = {
        "task_type": "category_standardization",
        "authorization_code": "26060345263220",
        "product_name": product_name,
        "client_category": client_category,
        "requirements": ["附件类目与欧菲斯品类主数据映射"],
    }
    body.update(extra)
    return client.post(URL, json=body, headers=AUTH)


# ---------------------------------------------------------------- 隔离 / 鉴权

def test_category_in_health(client):
    d = client.get("/health").json()
    assert d["category_enabled"] is True
    assert d["category_rule_count"] > 1000
    assert d["category_fallback_count"] > 0

def test_category_no_token_rejected(client):
    r = client.post(URL, json={"product_name": "", "client_category": "茶杯"})
    assert r.status_code == 401
    d = r.json()
    assert d["success"] is False and d["error_code"] == "HTTP_401"
    # 错误响应也应为品类形（含 kind3），不得混入品牌形字段 same_brand
    assert "kind3" in d and "same_brand" not in d

def test_category_wrong_token_rejected(client):
    r = client.post(URL, json={}, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

def test_category_reload_requires_auth(client):
    assert client.post("/api/category/reload").status_code == 401
    r = client.post("/api/category/reload", headers=AUTH)
    assert r.status_code == 200 and r.json()["success"] is True
    assert r.json()["rule_count"] > 1000

def test_category_invalid_task_type(client):
    d = _post(client, client_category="茶杯", task_type="other_task").json()
    assert d["success"] is False and d["error_code"] == "INVALID_TASK_TYPE"


# ---------------------------------------------------------------- 兜底命中（确定性）

def test_fallback_tea_cup(client):
    d = _post(client, client_category="茶杯").json()
    assert d["success"] is True
    assert d["kind3"] == "陶瓷杯"
    assert d["category_source"] == "fallback"
    assert d["category_matched"] is True
    assert d["confidence"] == 1.0
    assert d["needs_manual_review"] is False

def test_fallback_wok(client):
    """炒锅 -> 锅碗瓢盆及配件（兜底规则挂靠）。"""
    d = _post(client, client_category="炒锅").json()
    assert d["kind3"] == "锅碗瓢盆及配件"
    assert d["category_source"] == "fallback"

def test_fallback_ink_cartridge(client):
    """墨盒 -> 兼容墨盒。"""
    d = _post(client, client_category="墨盒").json()
    assert d["kind3"] == "兼容墨盒"
    assert d["category_source"] == "fallback"

def test_fallback_health_therapy(client):
    """热敷肩颈 + 健康护理电器 -> 理疗仪（双源 all 命中）。"""
    d = _post(client, product_name="热敷肩颈按摩仪", client_category="健康护理电器").json()
    assert d["kind3"] == "理疗仪"
    assert d["category_source"] == "fallback"


# ---------------------------------------------------------------- 未匹配 / 脏输入

def test_unmatched(client):
    d = _post(client, product_name="某完全无关的商品名称xyz", client_category="某完全无关的类目xyz").json()
    assert d["success"] is True
    assert d["category_matched"] is False
    assert d["status"] == "unmatched"
    assert d["kind3"] == ""
    assert d["needs_manual_review"] is True
    assert d["suggestion"]

def test_empty_inputs(client):
    d = _post(client).json()
    assert d["success"] is True
    assert d["category_matched"] is False
    assert d["needs_manual_review"] is True

def test_single_string_input(client):
    """与品牌接口一致：字符串输入可直接传入。"""
    d = _post(client, client_category="茶杯").json()
    assert d["kind3"] == "陶瓷杯"

def test_json_string_array_input(client):
    """JSON 字符串数组输入。"""
    d = _post(client, client_category='["茶杯"]').json()
    assert d["kind3"] == "陶瓷杯"


# ---------------------------------------------------------------- 批量

def test_batch_details(client):
    """批量：client_category 数组 -> details 数组一一对应。"""
    d = _post(client, client_category=["茶杯", "炒锅", "墨盒"]).json()
    assert d["success"] is True
    assert len(d["details"]) == 3
    assert [x["kind3"] for x in d["details"]] == ["陶瓷杯", "锅碗瓢盆及配件", "兼容墨盒"]
    # 主结果取首个
    assert d["kind3"] == "陶瓷杯"


# ---------------------------------------------------------------- 隔离性

def test_category_endpoint_independent_of_brand(client):
    """品类接口与品牌接口字段互不包含，证明结构隔离。"""
    d = _post(client, client_category="茶杯").json()
    assert "same_brand" not in d
    assert "attachment_standard_brands" not in d
    assert "kind3" in d and "category_source" in d
