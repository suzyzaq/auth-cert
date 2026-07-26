"""接口测试 —— TestClient 全链路（含 7 个必过案例、鉴权、异常结构）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRAND_API_TOKEN", "test-token-123")
# 测试环境禁用 SCS 远程回退，避免单测穿透真实网络；SCS 行为由 test_scs_fallback.py 单独覆盖
os.environ["SCS_ENABLED"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

AUTH = {"Authorization": "Bearer test-token-123"}
URL = "/api/brand/normalize"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _post(client, att, src, **extra):
    body = {
        "task_type": "brand_standardization",
        "authorization_code": "26060345263220",
        "authorization_name": "测试授权书",
        "attachment_values": att,
        "source_values": src,
        "candidate_values": [],
        "requirements": ["附件品牌与数据库品牌分别标准化"],
    }
    body.update(extra)
    return client.post(URL, json=body, headers=AUTH)


# ---------------------------------------------------------------- 鉴权

def test_no_token_rejected(client):
    r = client.post(URL, json={"attachment_values": [], "source_values": []})
    assert r.status_code == 401
    data = r.json()
    assert data["success"] is False and data["error_code"] == "HTTP_401"

def test_wrong_token_rejected(client):
    r = client.post(URL, json={}, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

def test_health_no_auth(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["brand_count"] > 100000
    assert set(data.keys()) == {
        "status", "brand_count", "alias_count", "data_version", "scs_enabled",
        "category_enabled", "category_rule_count", "category_fallback_count",
        "category_data_version",
    }
    assert data["scs_enabled"] is False   # 测试环境无 SCS Token 文件
    assert data["category_enabled"] is True
    assert data["category_rule_count"] > 0

def test_reload_requires_auth(client):
    assert client.post("/api/brand/reload").status_code == 401
    r = client.post("/api/brand/reload", headers=AUTH)
    assert r.status_code == 200 and r.json()["success"] is True


# ---------------------------------------------------------------- 7 个必过案例

def test_case1_en_cn(client):
    d = _post(client, ["HP"], ["惠普/HP"]).json()
    assert d["success"] is True
    assert d["same_brand"] is True
    assert d["matched_standard_brand"] == "惠普/HP"
    assert d["needs_manual_review"] is False
    assert isinstance(d["same_brand"], bool) and isinstance(d["success"], bool)
    assert 0 <= d["confidence"] <= 1

def test_case2_lowercase(client):
    d = _post(client, ["hp"], ["惠普/HP"]).json()
    assert d["same_brand"] is True

def test_case3_different_brand(client):
    d = _post(client, ["Canon"], ["惠普/HP"]).json()
    assert d["same_brand"] is False
    assert d["needs_manual_review"] is False
    assert d["match_type"] == "conflict"
    assert "佳能" in d["match_basis"] and "惠普" in d["match_basis"]

def test_case4_extra_brand(client):
    d = _post(client, ["HP", "Canon"], ["惠普/HP"]).json()
    assert d["same_brand"] is False
    assert any("佳能" in b for b in d["attachment_extra_brands"])
    assert d["needs_manual_review"] is True

def test_case5_empty_attachment(client):
    d = _post(client, [], ["惠普/HP"]).json()
    assert d["success"] is True
    assert d["same_brand"] is False
    assert d["needs_manual_review"] is True

def test_case6_unknown_brand(client):
    d = _post(client, ["不存在于欧菲斯品牌库的测试品牌"], ["惠普/HP"]).json()
    assert d["same_brand"] is False
    assert d["needs_manual_review"] is True
    assert "不存在于欧菲斯品牌库的测试品牌" in d["attachment_unmatched_values"]
    # 不得强行挂靠惠普
    assert d["attachment_standard_brands"] == []

def test_case7_both_empty(client):
    r = _post(client, [], [])
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is True
    assert d["same_brand"] is False
    assert d["needs_manual_review"] is True


# ---------------------------------------------------------------- 脏输入兼容

def test_single_string_input(client):
    d = _post(client, "HP", "惠普/HP").json()
    assert d["same_brand"] is True

def test_json_string_array_input(client):
    d = _post(client, '["HP"]', '["惠普/HP"]').json()
    assert d["same_brand"] is True

def test_comma_separated_input(client):
    d = _post(client, ["HP，惠普"], ["惠普/HP"]).json()
    assert d["same_brand"] is True  # HP 和 惠普 都归到同一 ID

def test_duplicates_and_spaces(client):
    d = _post(client, [" HP ", "hp", "HP"], ["惠普/HP"]).json()
    assert d["same_brand"] is True

def test_multi_brand_authorization(client):
    """多品牌授权：两侧集合一致 → same_brand=true"""
    d = _post(client, ["HP", "Canon"], ["惠普/HP", "佳能/CANON"]).json()
    assert d["same_brand"] is True
    assert len(d["attachment_standard_brand_ids"]) == 2

def test_invalid_task_type(client):
    d = _post(client, ["HP"], ["惠普/HP"], task_type="other_task").json()
    assert d["success"] is False and d["error_code"] == "INVALID_TASK_TYPE"

def test_original_values_preserved(client):
    """禁止丢失附件原始品牌值。"""
    d = _post(client, ["某个绝对不存在的品牌ABC"], []).json()
    assert "某个绝对不存在的品牌ABC" in d["attachment_unmatched_values"]

def test_error_is_json_not_html(client):
    r = client.post(
        URL,
        headers=AUTH,
        content=b"not-json",
    )
    assert r.headers["content-type"].startswith("application/json")
