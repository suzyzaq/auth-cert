"""
文本归一化 —— 完整复用 brand-matcher Skill 的 normalize.py 逻辑。

来源: ~/.workbuddy/skills/brand-matcher/app/matching/normalize.py
- NFKC 归一化（统一全角/半角）
- comparison_key: 仅保留字母数字/CJK/有意义符号，统一大写
- split_aliases: 别名切分（管道/逗号/顿号/分号）
"""
from __future__ import annotations

import re
import unicodedata

_MEANINGFUL_COMPARISON_SYMBOLS = frozenset("&+#")


def normalized_text(value: object) -> str:
    """NFKC 归一化 + 去首尾空格（统一全角半角）。"""
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def comparison_key(value: object) -> str:
    """标准化比较键：NFKC → 大写 → 仅保留字母数字/CJK/&+# 符号。

    示例: " ＨＰ " -> "HP"; "惠普/HP" -> "惠普HP"; "H.P" -> "HP"
    """
    text = normalized_text(value).upper()
    chars: list[str] = []
    for ch in text:
        if ch.isalnum() or ch in _MEANINGFUL_COMPARISON_SYMBOLS:
            chars.append(ch)
    return "".join(chars)


def split_aliases(value: object) -> tuple[str, ...]:
    """别名字段切分（与 brand-matcher 一致：| , ， ; ； 换行）。"""
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = re.split(r"[|,，;；\n\r]+", normalized_text(value))
    return tuple(t for item in values if (t := normalized_text(item)))


# 输入品牌值切分：中文逗号、英文逗号、顿号、分号、换行。
# 注意: "/" 不作为默认切分符 —— "惠普/HP" 是一个标准品牌名整体。
_VALUE_SPLIT_RE = re.compile(r"[,，、;；\n\r]+")


def split_multi_values(value: object) -> list[str]:
    """把一个输入值按分隔符拆成多个品牌候选值（保留原始形态）。"""
    text = normalized_text(value)
    if not text:
        return []
    parts = [p.strip() for p in _VALUE_SPLIT_RE.split(text)]
    return [p for p in parts if p]


def brand_name_variants(standard_brand: str) -> list[str]:
    """从标准品牌名（如 '惠普/HP'）拆出中/英文变体: ['惠普/HP', '惠普', 'HP']。"""
    variants = [standard_brand]
    if "/" in standard_brand:
        for part in standard_brand.split("/"):
            part = part.strip()
            if part:
                variants.append(part)
    return variants
