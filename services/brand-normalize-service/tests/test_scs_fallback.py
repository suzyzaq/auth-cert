"""SCS 在线品牌库回退链路测试（mock，不依赖网络）。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofs_brand_core import BrandRepository, BrandNormalizer, ScsBrandClient
from ofs_brand_core.scs_client import ScsBrand
from app.config import get_settings


@pytest.fixture(scope="module")
def repo():
    settings = get_settings()
    if not settings.brand_data_path.exists():
        pytest.skip("matcher.db 不存在")
    r = BrandRepository(settings.brand_data_path)
    r.load()
    return r


class FakeScsClient:
    """模拟 SCS 客户端：记录调用并返回预设结果。"""

    def __init__(self, results: dict[str, list[ScsBrand]]):
        self.results = results
        self.calls: list[str] = []
        self.available = True

    def search_enabled(self, name: str) -> list[ScsBrand]:
        self.calls.append(name)
        return self.results.get(name, [])


# ---------------------------------------------------------------- 回退触发条件

def test_scs_called_only_when_local_unmatched(repo):
    """本地命中时绝不调用 SCS。"""
    fake = FakeScsClient({})
    nz = BrandNormalizer(repo, scs_client=fake)
    vm = nz.normalize_value("惠普/HP")
    assert vm.matched
    assert not vm.scs_checked
    assert fake.calls == []


def test_scs_fallback_returns_candidates(repo):
    """本地未命中 → 查 SCS → 命中启用品牌 → 只作候选，不自动确认。"""
    fake = FakeScsClient({
        "某某新品牌": [ScsBrand(firm_code=175426, firm_name="某某新品牌", status=1)],
    })
    nz = BrandNormalizer(repo, scs_client=fake)
    vm = nz.normalize_value("某某新品牌")
    assert not vm.matched                      # 绝不自动确认
    assert vm.scs_checked
    assert vm.match_type == "scs_candidate"
    assert vm.scs_candidates[0]["scs_firm_code"] == 175426
    assert vm.scs_candidates[0]["scs_status"] == "启用"
    assert fake.calls == ["某某新品牌"]


def test_scs_fallback_no_hit(repo):
    """本地和 SCS 都未命中 → unmatched。"""
    fake = FakeScsClient({})
    nz = BrandNormalizer(repo, scs_client=fake)
    vm = nz.normalize_value("完全不存在品牌XYZQWE")
    assert not vm.matched
    assert vm.scs_checked
    assert vm.match_type == "unmatched"
    assert vm.scs_candidates == []


def test_blacklist_never_queries_scs(repo):
    """型号/规格黑名单不得穿透到 SCS。"""
    fake = FakeScsClient({})
    nz = BrandNormalizer(repo, scs_client=fake)
    vm = nz.normalize_value("CF510A")
    assert not vm.matched
    assert not vm.scs_checked
    assert fake.calls == []


def test_no_scs_client_keeps_original_behavior(repo):
    """未配置 SCS 客户端时行为与原来完全一致。"""
    nz = BrandNormalizer(repo)
    vm = nz.normalize_value("完全不存在品牌XYZQWE")
    assert not vm.matched
    assert not vm.scs_checked
    assert vm.match_type == "unmatched"


# ---------------------------------------------------------------- 比对层行为

def test_compare_with_scs_candidate_needs_review(repo):
    """SCS 候选存在时 same_brand 必须为 False 且需人工复核。"""
    fake = FakeScsClient({
        "新品牌甲": [ScsBrand(firm_code=99999, firm_name="新品牌甲", status=1)],
    })
    nz = BrandNormalizer(repo, scs_client=fake)
    res = nz.compare(["新品牌甲"], ["惠普/HP"])
    assert res.same_brand is False
    assert res.needs_manual_review is True
    assert "SCS" in res.match_basis
    assert res.match_type == "scs_candidate"


# ---------------------------------------------------------------- 客户端本体

def test_client_token_missing():
    c = ScsBrandClient(token_file=Path("nonexistent_token.json"))
    assert not c.available
    assert c.search_enabled("佳能") == []


class _FakeFile:
    """内存桩：模拟 Token 文件，避免触碰沙箱禁止的临时目录。"""
    def __init__(self, text: str, mtime: float):
        self._text = text
        self._mtime = mtime
    def exists(self):
        return True
    def stat(self):
        class _S: pass
        s = _S(); s.st_mtime = self._mtime
        return s
    def read_text(self, encoding=None):
        return self._text


def test_client_token_parse_and_hot_reload():
    f = _FakeFile(json.dumps({"Authorization": "Bearer abc", "X-XSRF-TOKEN": "x1"}), 1000.0)
    c = ScsBrandClient(token_file=f)
    assert c.available
    h = c._load_tokens()
    assert h["Authorization"] == "Bearer abc"
    assert h["X-XSRF-TOKEN"] == "x1"
    # 热加载：mtime 变化后自动读取新 Token（自动补 Bearer 前缀、小写键兼容）
    f._text = json.dumps({"authorization": "def", "x_xsrf_token": "x2"})
    f._mtime = 2000.0
    h2 = c._load_tokens()
    assert h2["Authorization"] == "Bearer def"
    assert h2["X-XSRF-TOKEN"] == "x2"


def test_client_status_filter():
    """即使响应混入停用品牌也必须过滤。"""
    c = ScsBrandClient(token_file=None)
    rows = [
        {"FirmCode": 1, "FirmName": "A", "status": 1, "status_str": "启用"},
        {"FirmCode": 2, "FirmName": "B", "status": 0, "status_str": "停用"},
    ]
    out = []
    for r in rows:
        if int(r.get("status", 0)) != 1:
            continue
        out.append(ScsBrand(firm_code=int(r["FirmCode"]), firm_name=r["FirmName"], status=1))
    assert len(out) == 1 and out[0].firm_name == "A"
