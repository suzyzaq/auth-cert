"""
品类标准化核心层 —— 完整复用 brand-matcher Skill 的品类匹配逻辑。

来源（与 brand-matcher 保持一致，仅替换包内 import）:
  - app/matching/category.py      -> CategoryIndex / CategoryMapper
  - app/matching/models.py        -> CategoryMatch
  - app/matching/normalize.py     -> normalized_text / comparison_key（复用本包 .normalize）

数据来源:
  - matcher.db 的 rules 表（active rule_versions 中 kind3_name 非空的行）
    type=1（品类+品牌）/ type=3（品类）均携带品类映射
  - config/fallback_categories.yaml（兜底规则，从 brand-matcher 同步，运行时本地化）

与品牌接口完全隔离:
  - 独立的内存索引（CategoryMapper），独立的 reload，独立的异常边界
  - 不依赖品牌库，不依赖 SCS；一个接口故障不影响另一个

确定性逻辑，无 LLM 依赖。
"""
from __future__ import annotations

import re
import sqlite3
import threading
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml
from rapidfuzz import fuzz, process

from .normalize import comparison_key, normalized_text


# ===========================================================================
# 基础类型
# ===========================================================================

@dataclass(frozen=True, slots=True)
class CategoryMatch:
    """一条品类匹配结果（与 brand-matcher 的 CategoryMatch 一致）。"""
    kind1: str
    kind2: str
    kind3: str
    source: str
    confidence: float
    matched_term: str
    status: str
    suggestion: str
    match_kind: str = ""
    rule_id: str = ""


# ===========================================================================
# 以下 CategoryIndex / CategoryMapper 逐字复用 brand-matcher/app/matching/category.py
# 仅将:
#   from app.matching.models import CategoryMatch
#   from app.matching.normalize import comparison_key, normalized_text
# 替换为上面的本地定义 / from .normalize import ...
# ===========================================================================

DEFAULT_FALLBACK_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "fallback_categories.yaml"
)
DEFAULT_PRIORITY = ("product_name", "client_category", "fallback")
VALID_PRIORITY_SOURCES = frozenset(DEFAULT_PRIORITY)
_TERM_SEPARATOR = re.compile(r"[|,，;；\n\r]+")
_CJK_CHARACTER = re.compile(r"[\u3400-\u9fff]")


def _key(value: object) -> str:
    return comparison_key(value).casefold()


def _terms(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    values = value if isinstance(value, (list, tuple, set)) else _TERM_SEPARATOR.split(normalized_text(value))
    return tuple(text for item in values if (text := normalized_text(item)))


def _parse_priority(
    value: Sequence[str] | str | None,
    *,
    default: Sequence[str] = DEFAULT_PRIORITY,
) -> tuple[str, ...]:
    if value is None:
        items = tuple(default)
    elif isinstance(value, str):
        items = tuple(part.strip() for part in value.split(",") if part.strip())
    else:
        items = tuple(str(part).strip() for part in value if str(part).strip())
    unknown = tuple(item for item in items if item not in VALID_PRIORITY_SOURCES)
    if unknown:
        raise ValueError(f"unknown category priority source: {', '.join(unknown)}")
    if not items:
        raise ValueError("category priority must contain at least one source")
    return items


def _short_term_match(
    source: object,
    term: object,
    *,
    allow_cjk_prefix: bool = False,
) -> bool:
    source_text = normalized_text(source).casefold()
    term_text = normalized_text(term).casefold()
    start = source_text.find(term_text)
    while start >= 0:
        end = start + len(term_text)
        left_ok = (
            allow_cjk_prefix
            or start == 0
            or not _CJK_CHARACTER.match(source_text[start - 1])
        )
        right_ok = (
            end == len(source_text)
            or not _CJK_CHARACTER.match(source_text[end])
        )
        if left_ok and right_ok:
            return True
        start = source_text.find(term_text, start + 1)
    return False


def _load_fallback_rules(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw_rules = payload
    elif isinstance(payload, Mapping) and isinstance(payload.get("rules"), list):
        raw_rules = payload["rules"]
    else:
        raise ValueError("fallback YAML top level must be a list or {rules: [...]}")

    rules: list[dict[str, Any]] = []
    for position, raw_rule in enumerate(raw_rules, start=1):
        if not isinstance(raw_rule, Mapping):
            raise ValueError(f"fallback rule {position} must be a mapping")
        rule = dict(raw_rule)
        if not normalized_text(rule.get("id")):
            raise ValueError(f"fallback rule {position} is missing id")
        try:
            rule["priority"] = int(rule.get("priority", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"fallback rule {position} priority must be numeric"
            ) from exc
        target = rule.get("target")
        if not isinstance(target, Mapping) or not normalized_text(target.get("kind3")):
            raise ValueError(f"fallback rule {position} is missing target.kind3")
        rules.append(rule)
    return rules


@dataclass(frozen=True, slots=True)
class _Category:
    kind1: str
    kind2: str
    kind3: str
    position: int
    priority: int | None


@dataclass(frozen=True, slots=True)
class _TermEntry:
    term: str
    match_kind: str
    category: _Category
    client_category_match_mode: str = "exact"


class CategoryIndex:
    def __init__(
        self,
        categories: tuple[_Category, ...],
        term_index: Mapping[str, tuple[_TermEntry, ...]],
        hierarchy: Mapping[str, Mapping[str, tuple[_Category, ...]]],
    ) -> None:
        self._categories = categories
        self._term_index = MappingProxyType(dict(term_index))
        self._hierarchy = MappingProxyType(
            {
                level: MappingProxyType(dict(values))
                for level, values in hierarchy.items()
            }
        )
        self._fuzzy_choices = tuple(self._term_index)

    @property
    def categories(self) -> tuple[_Category, ...]:
        return self._categories

    @property
    def term_index(self) -> Mapping[str, tuple[_TermEntry, ...]]:
        return self._term_index

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping[str, object]]) -> "CategoryIndex":
        categories: list[_Category] = []
        terms: defaultdict[str, list[_TermEntry]] = defaultdict(list)
        hierarchy: dict[str, defaultdict[str, list[_Category]]] = {
            "l3": defaultdict(list),
            "l2": defaultdict(list),
            "l1": defaultdict(list),
        }

        for position, row in enumerate(rows):
            kind1 = normalized_text(row.get("kind1") or row.get("kind1_name"))
            kind2 = normalized_text(row.get("kind2") or row.get("kind2_name"))
            kind3 = normalized_text(row.get("kind3") or row.get("kind3_name"))
            if not kind3:
                continue
            raw_priority = (
                row.get("category_priority")
                or row.get("category_mapping_priority")
                or row.get("品类映射优先级")
            )
            try:
                priority = int(raw_priority) if raw_priority not in (None, "") else None
            except (TypeError, ValueError):
                priority = None
            category = _Category(kind1, kind2, kind3, position, priority)
            categories.append(category)
            for level, value in (("l3", kind3), ("l2", kind2), ("l1", kind1)):
                if key := _key(value):
                    hierarchy[level][key].append(category)
            keyword_terms = tuple(
                dict.fromkeys(
                    _terms(row.get("keywords"))
                    + _terms(row.get("category_keywords"))
                )
            )
            configured_match_mode = row.get("match_mode") or row.get(
                "category_match_mode"
            )
            if isinstance(configured_match_mode, Mapping):
                client_category_match_mode = str(
                    configured_match_mode.get("client_category", "exact")
                ).casefold()
            else:
                client_category_match_mode = str(
                    configured_match_mode or "exact"
                ).casefold()
            for match_kind, values in (
                ("keyword", keyword_terms),
                ("synonym", _terms(row.get("synonyms"))),
            ):
                for term in values:
                    if key := _key(term):
                        terms[key].append(
                            _TermEntry(
                                term,
                                match_kind,
                                category,
                                client_category_match_mode,
                            )
                        )

        frozen_terms = {
            key: tuple(sorted(entries, key=lambda entry: entry.category.position))
            for key, entries in terms.items()
        }
        frozen_hierarchy = {
            level: {
                key: tuple(sorted(values, key=lambda category: category.position))
                for key, values in index.items()
            }
            for level, index in hierarchy.items()
        }
        return cls(tuple(categories), frozen_terms, frozen_hierarchy)

    def category_for_kind3(self, kind3: object) -> _Category | None:
        values = self._hierarchy["l3"].get(_key(kind3), ())
        return values[0] if values else None

    @staticmethod
    def _resolve_entries(
        entries: Sequence[_TermEntry],
    ) -> tuple[_TermEntry | None, tuple[_TermEntry, ...]]:
        by_kind3: dict[str, _TermEntry] = {}
        for entry in entries:
            by_kind3.setdefault(entry.category.kind3, entry)
        candidates = tuple(
            sorted(by_kind3.values(), key=lambda entry: entry.category.kind3)
        )
        if len(candidates) <= 1:
            return (candidates[0] if candidates else None), ()
        prioritized = [
            entry for entry in candidates if entry.category.priority is not None
        ]
        if prioritized:
            highest = max(entry.category.priority for entry in prioritized)
            winners = [
                entry
                for entry in prioritized
                if entry.category.priority == highest
            ]
            if len(winners) == 1:
                return winners[0], ()
        return None, candidates

    def exact_text_match(
        self, value: object, *, source: str = "product_name"
    ) -> tuple[_TermEntry | None, tuple[_TermEntry, ...], bool]:
        key = _key(value)
        if not key:
            return None, (), False
        matches: list[tuple[int, int, _TermEntry]] = []
        rejected_contains = False
        for term_key, entries in self._term_index.items():
            if term_key and term_key in key:
                for entry in entries:
                    if (
                        source == "client_category"
                        and entry.client_category_match_mode != "contains"
                        and term_key != key
                    ):
                        rejected_contains = True
                        continue
                    if (
                        source == "product_name"
                        and len(term_key) < 2
                        and not _short_term_match(key, term_key)
                    ):
                        rejected_contains = True
                        continue
                    kind_rank = 1 if entry.match_kind == "keyword" else 0
                    matches.append((len(term_key), kind_rank, entry))
        if not matches:
            return None, (), rejected_contains
        best_length = max(item[0] for item in matches)
        best_kind_rank = max(
            item[1] for item in matches if item[0] == best_length
        )
        best_entries = [
            item[2]
            for item in matches
            if item[0] == best_length and item[1] == best_kind_rank
        ]
        entry, ambiguous = self._resolve_entries(best_entries)
        return entry, ambiguous, rejected_contains

    def hierarchy_match(
        self, value: object
    ) -> tuple[_Category | None, str, tuple[_Category, ...]]:
        key = _key(value)
        if not key:
            return None, "", ()
        for level in ("l3", "l2", "l1"):
            candidates = self._hierarchy[level].get(key, ())
            if len(candidates) == 1:
                return candidates[0], f"hierarchy_{level}", candidates
            if len(candidates) > 1:
                return None, f"hierarchy_{level}", candidates
        return None, "", ()

    def fuzzy_match(
        self, value: object
    ) -> tuple[_TermEntry | None, float, str, tuple[_TermEntry, ...]]:
        key = _key(value)
        if not key or not self._fuzzy_choices:
            return None, 0.0, "", ()
        highest_score = -1.0
        matched_keys: list[str] = []
        for choice in self._fuzzy_choices:
            score = fuzz.ratio(key, choice)
            if score > highest_score:
                highest_score = score
                matched_keys = [choice]
            elif score == highest_score:
                matched_keys.append(choice)
        if highest_score < 0:
            return None, 0.0, "", ()
        matched_keys.sort()
        entries = tuple(
            entry
            for matched_key in matched_keys
            for entry in self._term_index[matched_key]
        )
        entry, ambiguous = self._resolve_entries(entries)
        return entry, highest_score / 100.0, " / ".join(matched_keys), ambiguous

    def legacy_category_match(
        self, product_name: object, client_category: object
    ) -> tuple[_Category | None, float, tuple[_Category, ...]]:
        source = normalized_text(client_category)
        haystack = _key(f"{source} {normalized_text(product_name)}")
        source_key = _key(source)
        source_terms = tuple(term for term in re.split(r"[/、,，;；\s]+", source) if term)
        scored: list[tuple[float, _Category]] = []
        for category in self._categories:
            kind3 = category.kind3
            kind3_key = _key(kind3)
            kind3_terms = tuple(term for term in re.split(r"[/、,，;；\s]+", kind3) if term)
            score = fuzz.ratio(source_key, kind3_key) / 100.0 * 0.35
            if source_key and (source_key in kind3_key or kind3_key in source_key):
                score += 0.45
            for term in source_terms:
                term_key = _key(term)
                if len(term_key) >= 2 and any(
                    term_key in _key(item) or _key(item) in term_key
                    for item in kind3_terms
                ):
                    score += 0.28
                if len(term_key) >= 2 and term_key in haystack and any(
                    term_key in _key(item) for item in kind3_terms
                ):
                    score += 0.15
            for term in kind3_terms:
                term_key = _key(term)
                if len(term_key) >= 2 and term_key in haystack:
                    score += 0.42
            if score >= 0.64:
                scored.append((score, category))
        if not scored:
            return None, 0.0, ()
        scored.sort(key=lambda item: (-item[0], item[1].kind3, item[1].position))
        best_score = scored[0][0]
        best = tuple(item[1] for item in scored if item[0] == best_score)
        unique = {item.kind3 for item in best}
        if len(unique) > 1:
            return None, best_score, best
        return best[0], best_score, best


class CategoryMapper:
    def __init__(
        self,
        index: CategoryIndex,
        *,
        fallback_path: Path | str | None = None,
        fallback_rules: Sequence[Mapping[str, Any]] | None = None,
        default_priority: Sequence[str] = DEFAULT_PRIORITY,
        fuzzy_threshold: float = 80,
    ) -> None:
        self.index = index
        self.default_priority = _parse_priority(default_priority)
        self.fuzzy_threshold = (
            fuzzy_threshold / 100.0 if fuzzy_threshold > 1 else fuzzy_threshold
        )
        if fallback_rules is None:
            path = Path(fallback_path) if fallback_path else DEFAULT_FALLBACK_PATH
            fallback_rules = _load_fallback_rules(path)
        else:
            validated_rules = []
            for position, rule in enumerate(fallback_rules, start=1):
                if not isinstance(rule, Mapping):
                    raise ValueError(f"fallback rule {position} must be a mapping")
                copied = dict(rule)
                try:
                    copied["priority"] = int(copied.get("priority", 0))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"fallback rule {position} priority must be numeric"
                    ) from exc
                validated_rules.append(copied)
            fallback_rules = validated_rules
        self.fallback_rules = tuple(
            sorted(
                (dict(rule) for rule in fallback_rules if rule.get("enabled", True)),
                key=lambda rule: (-int(rule.get("priority", 0)), str(rule.get("id", ""))),
            )
        )

    @classmethod
    def from_rules(
        cls,
        rows: Iterable[Mapping[str, object]],
        **kwargs: Any,
    ) -> "CategoryMapper":
        return cls(CategoryIndex.from_rows(rows), **kwargs)

    def map(
        self,
        product_name: object,
        client_category: object,
        *,
        priority: Sequence[str] | None = None,
        category_priority: Sequence[str] | str | None = None,
    ) -> CategoryMatch:
        sources = {
            "product_name": normalized_text(product_name),
            "client_category": normalized_text(client_category),
        }
        best_suggestion: tuple[float, str] = (0.0, "")

        selected_priority = category_priority if category_priority is not None else priority
        for source in _parse_priority(selected_priority, default=self.default_priority):
            if source == "fallback":
                match = self._fallback(sources)
                if match:
                    return match
                continue
            text = sources.get(source, "")
            if not text:
                continue
            if source == "client_category":
                category, match_kind, candidates = self.index.hierarchy_match(text)
                if category:
                    return self._matched(category, source, 1.0, text, match_kind)
                if candidates:
                    names = "、".join(candidate.kind3 for candidate in candidates)
                    best_suggestion = max(
                        best_suggestion,
                        (1.0, f"{text} 对应多个欧菲斯小类：{names}，请补充商品关键词"),
                    )
                    continue
            entry, ambiguous, rejected_contains = self.index.exact_text_match(
                text, source=source
            )
            if ambiguous:
                best_suggestion = max(
                    best_suggestion,
                    (1.0, self._ambiguous_suggestion(text, ambiguous)),
                )
                continue
            if entry:
                return self._matched(entry.category, source, 1.0, entry.term, entry.match_kind)
            if rejected_contains:
                continue
            entry, confidence, matched_key, ambiguous = self.index.fuzzy_match(text)
            if ambiguous and confidence >= self.fuzzy_threshold:
                best_suggestion = max(
                    best_suggestion,
                    (confidence, self._ambiguous_suggestion(matched_key, ambiguous)),
                )
                continue
            if entry and confidence >= self.fuzzy_threshold:
                return self._matched(
                    entry.category,
                    source,
                    confidence,
                    entry.term,
                    "fuzzy",
                )
            if entry and confidence > best_suggestion[0]:
                best_suggestion = (
                    confidence,
                    f"可能接近“{entry.category.kind3}”（相似度 {confidence:.0%}），"
                    "低于阈值，建议补充关键词或兜底规则",
                )

        legacy, confidence, candidates = self.index.legacy_category_match(
            sources["product_name"],
            sources["client_category"],
        )
        if legacy:
            return self._matched(
                legacy,
                "legacy_fallback",
                confidence,
                sources["client_category"],
                "legacy_score",
            )
        if candidates:
            names = "、".join(dict.fromkeys(item.kind3 for item in candidates))
            best_suggestion = max(
                best_suggestion,
                (confidence, f"旧版评分出现并列候选：{names}"),
            )

        suggestion = best_suggestion[1] or "未找到可用品类候选，建议补充品类关键词或兜底规则"
        return CategoryMatch(
            kind1="",
            kind2="",
            kind3="",
            source="",
            confidence=best_suggestion[0],
            matched_term="",
            status="unmatched",
            suggestion=suggestion,
        )

    @staticmethod
    def _ambiguous_suggestion(
        matched_term: str, entries: Sequence[_TermEntry]
    ) -> str:
        names = "、".join(
            dict.fromkeys(entry.category.kind3 for entry in entries)
        )
        return (
            f"“{matched_term}”同时对应多个欧菲斯小类：{names}，"
            "请设置唯一的品类映射优先级"
        )

    def _fallback(self, sources: Mapping[str, str]) -> CategoryMatch | None:
        for rule in self.fallback_rules:
            if not self._fallback_matches(rule, sources):
                continue
            target = rule.get("target") or {}
            category = self.index.category_for_kind3(target.get("kind3"))
            if category is None:
                continue
            matched_terms = []
            for source_name, configured in (rule.get("sources") or {}).items():
                source_key = _key(sources.get(source_name, ""))
                for term in _terms(configured):
                    if self._source_term_matches(
                        rule, source_name, source_key, _key(term)
                    ):
                        matched_terms.append(term)
                        break
            return CategoryMatch(
                kind1=normalized_text(target.get("kind1")) or category.kind1,
                kind2=normalized_text(target.get("kind2")) or category.kind2,
                kind3=category.kind3,
                source="fallback",
                confidence=1.0,
                matched_term=" + ".join(matched_terms),
                status="matched",
                suggestion=normalized_text(rule.get("note")),
                match_kind="fallback",
                rule_id=str(rule.get("id", "")),
            )
        return None

    @staticmethod
    def _fallback_matches(
        rule: Mapping[str, Any], sources: Mapping[str, str]
    ) -> bool:
        groups = []
        for source_name, configured in (rule.get("sources") or {}).items():
            source_key = _key(sources.get(source_name, ""))
            terms = tuple(_key(term) for term in _terms(configured))
            groups.append(
                bool(
                    source_key
                    and any(
                        CategoryMapper._source_term_matches(
                            rule, source_name, source_key, term
                        )
                        for term in terms
                        if term
                    )
                )
            )
        if not groups:
            return False
        return any(groups) if rule.get("source_mode") == "any" else all(groups)

    @staticmethod
    def _source_term_matches(
        rule: Mapping[str, Any],
        source_name: str,
        source_key: str,
        term_key: str,
    ) -> bool:
        configured_mode = rule.get("match_mode")
        if isinstance(configured_mode, Mapping):
            mode = configured_mode.get(source_name)
        else:
            mode = configured_mode
        if not mode:
            mode = "exact" if source_name == "client_category" else "contains"
        if mode == "exact":
            return term_key == source_key
        if mode == "contains_short":
            return _short_term_match(
                source_key,
                term_key,
                allow_cjk_prefix=True,
            )
        if mode != "contains":
            raise ValueError(f"unsupported match_mode for {source_name}: {mode}")
        if source_name == "product_name" and len(term_key) < 2:
            return _short_term_match(source_key, term_key)
        return term_key in source_key

    @staticmethod
    def _matched(
        category: _Category,
        source: str,
        confidence: float,
        matched_term: str,
        match_kind: str,
    ) -> CategoryMatch:
        return CategoryMatch(
            kind1=category.kind1,
            kind2=category.kind2,
            kind3=category.kind3,
            source=source,
            confidence=confidence,
            matched_term=matched_term,
            status="matched",
            suggestion="",
            match_kind=match_kind,
        )


# ===========================================================================
# 数据访问 + 归一化封装（品牌隔离）
# ===========================================================================

_CATEGORY_COLUMNS = (
    "code", "type", "type_name",
    "kind1_name", "kind2_name", "kind3_name",
    "category_keywords", "synonyms", "category_priority",
)


class CategoryRepository:
    """品类库内存索引。从 matcher.db 的 rules 表（active 版本）构建。

    与 BrandRepository 完全独立：独立连接、独立锁、独立 mtime 校验与 reload。
    只读访问 matcher.db，绝不写回。
    """

    def __init__(self, db_path: str | Path, fallback_path: str | Path | None = None):
        self.db_path = Path(db_path)
        self.fallback_path = Path(fallback_path) if fallback_path else DEFAULT_FALLBACK_PATH
        self._lock = threading.RLock()
        self._loaded_mtime: float = 0.0
        self.data_version: str = ""
        self.rule_count: int = 0          # 命中的品类规则数（kind3_name 非空）
        self.fallback_count: int = 0
        self._mapper: CategoryMapper | None = None

    # ------------------------------------------------------------------ load

    def load(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"品类库数据库不存在: {self.db_path}")
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                ver = conn.execute(
                    "SELECT id, version FROM rule_versions WHERE status='active' LIMIT 1"
                ).fetchone()
                if not ver:
                    raise ValueError("品类库中没有 active 规则版本")
                cols = ", ".join(_CATEGORY_COLUMNS)
                raw_rows = conn.execute(
                    f"SELECT {cols} FROM rules "
                    "WHERE version_id=? AND enabled=1 AND kind3_name <> ''",
                    (ver["id"],),
                ).fetchall()
                rows = [
                    {k: r[k] for k in _CATEGORY_COLUMNS}
                    for r in raw_rows
                ]
                self._mapper = CategoryMapper.from_rules(
                    rows, fallback_path=self.fallback_path
                )
                # fallback 规则数（从已加载的 mapper 取，避免二次解析）
                self.fallback_count = len(self._mapper.fallback_rules)
                self.rule_count = len(rows)
                self.data_version = str(ver["version"])
                self._loaded_mtime = self.db_path.stat().st_mtime
            finally:
                conn.close()

    def reload_if_changed(self) -> bool:
        """数据库文件有更新则重新加载。返回是否执行了 reload。"""
        if not self.db_path.exists():
            return False
        if self.db_path.stat().st_mtime > self._loaded_mtime:
            self.load()
            return True
        return False

    @property
    def mapper(self) -> CategoryMapper | None:
        return self._mapper

    @property
    def ready(self) -> bool:
        return self._mapper is not None


class CategoryNormalizer:
    """品类归一化封装：输入 (product_name, client_category) -> CategoryMatch。"""

    def __init__(self, repo: CategoryRepository):
        self.repo = repo

    def normalize(self, product_name: object, client_category: object) -> CategoryMatch:
        if self.repo.mapper is None:
            raise RuntimeError("品类库尚未加载")
        return self.repo.mapper.map(product_name, client_category)
