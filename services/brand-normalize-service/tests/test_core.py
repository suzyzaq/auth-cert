"""ofs_brand_core 单元测试 —— 使用真实品牌库（只读）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from ofs_brand_core import BrandRepository, BrandNormalizer
from ofs_brand_core.normalize import comparison_key, split_multi_values


@pytest.fixture(scope="session")
def normalizer() -> BrandNormalizer:
    repo = BrandRepository(get_settings().brand_data_path)
    repo.load()
    return BrandNormalizer(repo)


# ---------------------------------------------------------------- 归一化

def test_comparison_key_fullwidth():
    assert comparison_key(" ＨＰ ") == "HP"

def test_comparison_key_slash():
    assert comparison_key("惠普/HP") == "惠普HP"

def test_comparison_key_case():
    assert comparison_key("hp") == comparison_key("HP") == comparison_key("Hp")

def test_split_multi_values():
    assert split_multi_values("惠普，佳能、得力,3M") == ["惠普", "佳能", "得力", "3M"]

def test_slash_not_split():
    assert split_multi_values("惠普/HP") == ["惠普/HP"]


# ---------------------------------------------------------------- 输入解包

def test_expand_json_string_array(normalizer):
    assert normalizer.expand_values('["HP", "Canon"]') == ["HP", "Canon"]

def test_expand_single_string(normalizer):
    assert normalizer.expand_values("HP") == ["HP"]

def test_expand_dedup_case(normalizer):
    assert normalizer.expand_values(["HP", "hp", " HP "]) == ["HP"]

def test_expand_none_and_empty(normalizer):
    assert normalizer.expand_values(None) == []
    assert normalizer.expand_values([]) == []
    assert normalizer.expand_values("") == []


# ---------------------------------------------------------------- 单值标准化

def test_normalize_hp_en(normalizer):
    vm = normalizer.normalize_value("HP")
    assert vm.matched and vm.standard_brand == "惠普/HP"

def test_normalize_hp_lower(normalizer):
    vm = normalizer.normalize_value("hp")
    assert vm.matched and vm.standard_brand == "惠普/HP"

def test_normalize_full_standard(normalizer):
    vm = normalizer.normalize_value("惠普/HP")
    assert vm.matched and vm.match_type == "exact"

def test_normalize_cn_only(normalizer):
    vm = normalizer.normalize_value("惠普")
    assert vm.matched and vm.standard_brand == "惠普/HP"

def test_same_standard_id_for_cn_en(normalizer):
    a = normalizer.normalize_value("HP")
    b = normalizer.normalize_value("惠普/HP")
    assert a.standard_id == b.standard_id

def test_canon_not_hp(normalizer):
    vm = normalizer.normalize_value("Canon")
    assert vm.matched and "佳能" in vm.standard_brand
    assert vm.standard_brand != "惠普/HP"

def test_model_not_brand(normalizer):
    """型号不得被识别为品牌（黑名单防护）"""
    vm = normalizer.normalize_value("CF510A")
    assert not vm.matched

def test_unknown_brand_unmatched(normalizer):
    vm = normalizer.normalize_value("不存在于欧菲斯品牌库的测试品牌XYZQWE")
    assert not vm.matched
    assert vm.raw_value == "不存在于欧菲斯品牌库的测试品牌XYZQWE"


# ---------------------------------------------------------------- 双侧比对（7 个必过案例的核心逻辑）

def test_case1_en_cn_same(normalizer):
    r = normalizer.compare(["HP"], ["惠普/HP"])
    assert r.same_brand is True
    assert r.matched_standard_brand == "惠普/HP"
    assert r.needs_manual_review is False

def test_case2_case_insensitive(normalizer):
    r = normalizer.compare(["hp"], ["惠普/HP"])
    assert r.same_brand is True

def test_case3_conflict(normalizer):
    r = normalizer.compare(["Canon"], ["惠普/HP"])
    assert r.same_brand is False
    assert r.needs_manual_review is False
    assert r.match_type == "conflict"
    assert "佳能" in r.match_basis and "惠普" in r.match_basis

def test_case4_attachment_extra(normalizer):
    r = normalizer.compare(["HP", "Canon"], ["惠普/HP"])
    assert r.same_brand is False
    assert any("佳能" in b for b in r.attachment_extra_brands)
    assert r.needs_manual_review is True

def test_case5_empty_attachment(normalizer):
    r = normalizer.compare([], ["惠普/HP"])
    assert r.same_brand is False
    assert r.needs_manual_review is True

def test_case6_unknown_brand(normalizer):
    r = normalizer.compare(["不存在于欧菲斯品牌库的测试品牌"], ["惠普/HP"])
    assert r.same_brand is False
    assert r.needs_manual_review is True
    unmatched = [m.raw_value for m in r.attachment_matches if not m.matched]
    assert "不存在于欧菲斯品牌库的测试品牌" in unmatched

def test_case7_both_empty(normalizer):
    r = normalizer.compare([], [])
    assert r.same_brand is False
    assert r.needs_manual_review is True

def test_fuzzy_never_auto_confirms(normalizer):
    """模糊召回只能作为候选，不得自动认定一致。"""
    r = normalizer.compare(["惠普x"], ["惠普/HP"])
    # 「惠普x」不应精确命中任何品牌名；若只有模糊候选则不能 same_brand
    att_matched = [m for m in r.attachment_matches if m.matched]
    if not att_matched:
        assert r.same_brand is False
        assert r.needs_manual_review is True

def test_source_never_overwrites_attachment(normalizer):
    """禁止：因数据库是惠普就把附件佳能改成惠普。"""
    r = normalizer.compare(["Canon"], ["惠普/HP"])
    att = [m.standard_brand for m in r.attachment_matches if m.matched]
    assert att and all("佳能" in b for b in att)
