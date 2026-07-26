"""
品牌标准化匹配引擎（确定性逻辑，无 LLM）。

处理顺序（与需求一致）:
  1. 清理首尾空格            -> normalized_text (NFKC)
  2. 统一全角半角            -> normalized_text (NFKC)
  3. 英文统一大小写          -> comparison_key (upper)
  4. 处理 / 、 括号等格式差异 -> comparison_key + split_multi_values
  5. 精确匹配标准品牌        -> idx_standard
  6. 匹配标准化名称          -> idx_name (登记 brand_name)
  7. 匹配品牌别名            -> idx_alias
  8. 匹配中英文品牌关系      -> idx_variant (标准名中/英文拆分)
  9. 模糊召回（仅候选）      -> fuzzy_candidates
  10. 必须落到同一标准品牌 ID 才认定同一品牌

黑名单防护复用 brand-recognition/scripts/retriever.py:
  型号/规格/单位/颜色/非品牌词 不进入模糊召回。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import normalized_text, comparison_key, split_multi_values
from .repository import BrandRepository
from .scs_client import ScsBrandClient

# ---- 黑名单（来自 brand-recognition retriever.py，防止型号/规格误识别为品牌） ----

_MODEL_PATTERNS = [
    re.compile(r"^[A-Za-z]{1,4}\d{2,6}[A-Za-z]?$"),   # M410A, CF510A
    re.compile(r"^\d{4,8}$"),                           # 6301
    re.compile(r"^[A-Za-z][-_]\d{2,}$"),                # A-03
    re.compile(r"^[A-Za-z]{1,3}\d+[A-Za-z]+$"),         # DZ47
]
_SPEC_PATTERNS = [
    re.compile(r"^\d{2,4}(mm|cm|m|ml|L|kg|g)$", re.I),
    re.compile(r"^A\d$", re.I),
]
_UNIT_COLOR_WORDS = frozenset({
    "盒", "包", "瓶", "个", "箱", "桶", "卷", "套", "组", "件", "台", "支",
    "蓝色", "黑色", "红色", "白色", "黄色", "绿色", "透明",
})
_NON_BRAND_KEYS = frozenset({"LED", "OT", "USB", "HDMI", "VGA", "GPS", "UPS", "DIY"})


def _is_blacklisted(text: str) -> str:
    """返回黑名单原因；非黑名单返回空串。"""
    t = text.strip()
    for pat in _MODEL_PATTERNS:
        if pat.match(t):
            return "疑似型号"
    for pat in _SPEC_PATTERNS:
        if pat.match(t):
            return "疑似规格"
    if t in _UNIT_COLOR_WORDS:
        return "疑似单位/颜色"
    if t.upper() in _NON_BRAND_KEYS:
        return "非品牌通用词"
    return ""


# ---------------------------------------------------------------- 数据模型

@dataclass
class ValueMatch:
    """单个输入值的标准化结果"""
    raw_value: str
    cleaned_value: str
    matched: bool = False
    standard_id: str = ""
    standard_brand: str = ""
    match_type: str = "unmatched"   # exact/normalized/alias/en_cn/fuzzy_candidate/unmatched/ambiguous
    confidence: float = 0.0
    reason: str = ""
    fuzzy_candidates: list[dict] = field(default_factory=list)
    scs_checked: bool = False          # 是否走了 SCS 远程回退查询
    scs_candidates: list[dict] = field(default_factory=list)


@dataclass
class CompareResult:
    """附件 vs 数据库 品牌比对结果"""
    attachment_matches: list[ValueMatch] = field(default_factory=list)
    source_matches: list[ValueMatch] = field(default_factory=list)
    same_brand: bool = False
    matched_standard_brand: str = ""
    matched_standard_brand_id: str = ""
    match_type: str = "unmatched"
    confidence: float = 0.0
    match_basis: str = ""
    needs_manual_review: bool = False
    attachment_extra_brands: list[str] = field(default_factory=list)
    source_extra_brands: list[str] = field(default_factory=list)


_TYPE_CONFIDENCE = {
    "exact": 1.0, "normalized": 0.98, "alias": 0.95, "en_cn": 0.97,
    "fuzzy_candidate": 0.6, "scs_candidate": 0.5, "unmatched": 0.0, "ambiguous": 0.0,
}


class BrandNormalizer:
    """品牌标准化器：单值标准化 + 双侧比对。

    scs_client（可选）: 本地品牌库未命中时的 SCS 在线品牌库回退查询。
    SCS 结果只作为候选（仅启用状态品牌），绝不自动确认同品牌。
    """

    def __init__(self, repo: BrandRepository, scs_client: ScsBrandClient | None = None):
        self.repo = repo
        self.scs_client = scs_client

    # ------------------------------------------------------------ 单值标准化

    def normalize_value(self, raw: str) -> ValueMatch:
        cleaned = normalized_text(raw)
        vm = ValueMatch(raw_value=str(raw), cleaned_value=cleaned)
        if not cleaned:
            vm.reason = "空值"
            return vm
        key = comparison_key(cleaned)
        if not key:
            vm.reason = "清洗后为空（仅含符号）"
            return vm

        # Step 5: 精确匹配标准品牌全名
        ids = self.repo.lookup_standard(key)
        if len(ids) == 1:
            sid = next(iter(ids))
            std = self.repo.get(sid)
            vm.matched, vm.standard_id, vm.standard_brand = True, sid, std.standard_brand
            vm.match_type = "exact" if cleaned == std.standard_brand else "normalized"
            vm.confidence = _TYPE_CONFIDENCE[vm.match_type]
            vm.reason = f"命中标准品牌名「{std.standard_brand}」"
            return vm

        # Step 6: 匹配登记品牌名称（brand_name）
        if not ids:
            ids = self.repo.lookup_name(key)
            if len(ids) == 1:
                sid = next(iter(ids))
                std = self.repo.get(sid)
                vm.matched, vm.standard_id, vm.standard_brand = True, sid, std.standard_brand
                vm.match_type = "normalized"
                vm.confidence = _TYPE_CONFIDENCE["normalized"]
                vm.reason = f"命中已登记品牌名，归一到「{std.standard_brand}」"
                return vm

        # Step 7: 匹配正式别名
        if not ids:
            ids = self.repo.lookup_alias(key)
            if len(ids) == 1:
                sid = next(iter(ids))
                std = self.repo.get(sid)
                vm.matched, vm.standard_id, vm.standard_brand = True, sid, std.standard_brand
                vm.match_type = "alias"
                vm.confidence = _TYPE_CONFIDENCE["alias"]
                vm.reason = f"命中正式别名，归一到「{std.standard_brand}」"
                return vm

        # Step 8: 匹配中英文品牌关系（标准名的中/英文拆分变体）
        if not ids:
            ids = self.repo.lookup_variant(key)
            if len(ids) == 1:
                sid = next(iter(ids))
                std = self.repo.get(sid)
                vm.matched, vm.standard_id, vm.standard_brand = True, sid, std.standard_brand
                vm.match_type = "en_cn"
                vm.confidence = _TYPE_CONFIDENCE["en_cn"]
                vm.reason = f"命中标准品牌中/英文名，归一到「{std.standard_brand}」"
                return vm

        # 多个标准品牌命中同一键 → 歧义，禁止自动判定
        if len(ids) > 1:
            cands = sorted(ids)[:5]
            vm.match_type = "ambiguous"
            vm.reason = "命中多个标准品牌，存在歧义: " + ", ".join(
                f"{self.repo.get(s).standard_brand}({s})" for s in cands
            )
            vm.fuzzy_candidates = [
                {"standard_id": s, "standard_brand": self.repo.get(s).standard_brand, "score": 100.0}
                for s in cands
            ]
            return vm

        # 黑名单：型号/规格/单位不得进入模糊召回（也禁止查 SCS）
        bl = _is_blacklisted(cleaned)
        if bl:
            vm.reason = f"未命中品牌库，且{bl}，不作模糊召回"
            return vm

        # Step 9: 本地模糊召回（只能作为候选，禁止自动确认）
        fz = self.repo.fuzzy_candidates(cleaned)
        if fz:
            vm.match_type = "fuzzy_candidate"
            vm.confidence = _TYPE_CONFIDENCE["fuzzy_candidate"]
            vm.reason = "仅模糊召回候选，不能自动确认"
            vm.fuzzy_candidates = [
                {"matched_name": n, "standard_id": s,
                 "standard_brand": self.repo.get(s).standard_brand, "score": sc}
                for n, s, sc in fz
            ]
            return vm

        # Step 10: SCS 在线品牌库回退（仅启用品牌，只作候选，绝不自动确认）
        if self.scs_client is not None:
            vm.scs_checked = True
            scs_rows = self.scs_client.search_enabled(cleaned)
            if scs_rows:
                vm.scs_candidates = [r.as_candidate() for r in scs_rows]
                vm.match_type = "scs_candidate"
                vm.confidence = _TYPE_CONFIDENCE["scs_candidate"]
                vm.reason = (
                    f"本地品牌库未命中；SCS品牌库(仅启用)命中 {len(scs_rows)} 条候选，"
                    "需人工复核后判断是否同品牌"
                )
                vm.fuzzy_candidates = vm.scs_candidates
                return vm

        vm.reason = "未命中欧菲斯品牌库"
        return vm

    # ------------------------------------------------------------ 输入解包

    @staticmethod
    def expand_values(values) -> list[str]:
        """兼容: 空/单字符串/JSON字符串数组/中英文逗号顿号分隔/重复值。"""
        import json
        if values is None:
            return []
        if isinstance(values, str):
            s = values.strip()
            if not s:
                return []
            # JSON 字符串数组被错误地整体传入
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        values = parsed
                    else:
                        values = [s]
                except (ValueError, TypeError):
                    values = [s]
            else:
                values = [s]
        if not isinstance(values, (list, tuple)):
            values = [str(values)]

        out: list[str] = []
        seen: set[str] = set()
        for v in values:
            if v is None:
                continue
            for part in split_multi_values(v):
                k = comparison_key(part)
                if not k or k in seen:
                    continue
                seen.add(k)
                out.append(part)
        return out

    # ------------------------------------------------------------ 双侧比对

    def compare(self, attachment_values, source_values) -> CompareResult:
        att_list = self.expand_values(attachment_values)
        src_list = self.expand_values(source_values)

        res = CompareResult(
            attachment_matches=[self.normalize_value(v) for v in att_list],
            source_matches=[self.normalize_value(v) for v in src_list],
        )
        att_ids = {m.standard_id for m in res.attachment_matches if m.matched}
        src_ids = {m.standard_id for m in res.source_matches if m.matched}
        att_unmatched = [m for m in res.attachment_matches if not m.matched]
        src_unmatched = [m for m in res.source_matches if not m.matched]

        def _names(ids: set[str]) -> str:
            return ", ".join(sorted(self.repo.get(i).standard_brand for i in ids)) or "无"

        # ---- 任意一侧为空 ----
        if not att_list or not src_list:
            res.needs_manual_review = True
            res.match_type = "unmatched"
            empty = []
            if not att_list:
                empty.append("附件品牌为空")
            if not src_list:
                empty.append("数据库品牌为空")
            res.match_basis = "；".join(empty) + "，无法自动比对，需人工复核"
            return res

        # ---- 任意一侧全部无法识别 ----
        if not att_ids or not src_ids:
            res.needs_manual_review = True
            res.match_type = "unmatched"
            parts = []
            if not att_ids:
                parts.append(
                    "附件品牌未能命中欧菲斯品牌库: "
                    + ", ".join(m.raw_value for m in att_unmatched)
                )
            if not src_ids:
                parts.append(
                    "数据库品牌未能命中欧菲斯品牌库: "
                    + ", ".join(m.raw_value for m in src_unmatched)
                )
            # 模糊候选 / SCS 候选提示
            if any(m.match_type == "fuzzy_candidate" for m in att_unmatched + src_unmatched):
                parts.append("存在模糊召回候选，但模糊结果不能自动确认")
                res.match_type = "fuzzy_candidate"
            if any(m.match_type == "scs_candidate" for m in att_unmatched + src_unmatched):
                parts.append("SCS在线品牌库(仅启用)存在候选品牌，需人工复核确认后建议同步到本地品牌主库")
                if res.match_type == "unmatched":
                    res.match_type = "scs_candidate"
            res.match_basis = "；".join(parts)
            return res

        # ---- 两侧均有命中 ----
        if att_ids == src_ids and not att_unmatched and not src_unmatched:
            # 标准品牌 ID 集合完全一致 → 同一品牌
            res.same_brand = True
            res.needs_manual_review = False
            only = sorted(att_ids)
            if len(only) == 1:
                sid = only[0]
                res.matched_standard_brand_id = sid
                res.matched_standard_brand = self.repo.get(sid).standard_brand
            all_matches = res.attachment_matches + res.source_matches
            att_keys = {comparison_key(m.cleaned_value) for m in res.attachment_matches}
            src_keys = {comparison_key(m.cleaned_value) for m in res.source_matches}
            if all(m.match_type == "exact" for m in all_matches):
                res.match_type = "exact"
            elif any(m.match_type == "alias" for m in all_matches):
                res.match_type = "alias"
            elif att_keys != src_keys:
                res.match_type = "en_cn"
            else:
                res.match_type = "normalized"
            res.confidence = min(m.confidence for m in all_matches)
            if res.match_type == "en_cn":
                res.confidence = 1.0
            att_raw = ", ".join(m.raw_value for m in res.attachment_matches)
            src_raw = ", ".join(m.raw_value for m in res.source_matches)
            res.match_basis = (
                f"附件{att_raw}与数据库{src_raw}均命中同一个欧菲斯标准品牌ID"
                if len(only) == 1 else
                f"附件与数据库的标准品牌ID集合完全一致: {_names(att_ids)}"
            )
            return res

        # ---- ID 集合不一致 ----
        common = att_ids & src_ids
        att_extra = att_ids - src_ids
        src_extra = src_ids - att_ids
        res.attachment_extra_brands = sorted(self.repo.get(i).standard_brand for i in att_extra)
        res.source_extra_brands = sorted(self.repo.get(i).standard_brand for i in src_extra)

        if not common:
            # 完全冲突：两边命中不同标准品牌
            res.match_type = "conflict"
            res.confidence = 1.0
            res.needs_manual_review = bool(att_unmatched or src_unmatched)
            res.match_basis = (
                f"品牌冲突：附件命中「{_names(att_ids)}」，"
                f"数据库命中「{_names(src_ids)}」，未落到同一个欧菲斯标准品牌ID"
            )
            if res.needs_manual_review:
                res.match_basis += "；且存在未识别品牌值"
            return res

        # 有交集但一侧多出品牌 / 或有未识别值
        # 集合相同但存在未识别值 → unmatched；集合不同 → conflict
        res.match_type = "conflict" if (att_extra or src_extra) else "unmatched"
        res.confidence = 0.8
        res.needs_manual_review = True
        parts = [f"两侧共同命中「{_names(common)}」"]
        if att_extra:
            parts.append(f"附件多出品牌「{_names(att_extra)}」")
        if src_extra:
            parts.append(f"数据库多出品牌「{_names(src_extra)}」")
        if att_unmatched:
            parts.append("附件存在未识别值: " + ", ".join(m.raw_value for m in att_unmatched))
        if src_unmatched:
            parts.append("数据库存在未识别值: " + ", ".join(m.raw_value for m in src_unmatched))
        res.match_basis = "；".join(parts) + "；品牌集合不一致，需人工复核"
        return res
