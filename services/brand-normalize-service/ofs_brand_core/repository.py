"""
品牌数据访问模块 —— 复用 brand-matcher 的 matcher.db（SQLite 品牌主库）。

数据来源（与 brand-recognition/scripts/retriever.py 的 BrandLibrary.from_sqlite 同源）:
  - brands 表          : 活跃版本（brand_versions.status='active'）的启用品牌
  - brand_alias 表     : 正式品牌别名库（brand-matcher 别名沉淀机制产出）
  - brand_versions 表  : 数据版本号

标准品牌 ID 规则:
  同一个 standard_brand 可能对应多条 brands 记录（如 惠普/HP 有 621/7563/25461），
  取其中最小的 brand_code 作为该标准品牌的规范 ID，格式 BRAND_{code:0>6}。
  该 ID 稳定、可追溯回欧菲斯品牌编码。

只读访问，绝不写回/修改原品牌库。
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .normalize import comparison_key, split_aliases, brand_name_variants, normalized_text


@dataclass
class StandardBrand:
    """欧菲斯标准品牌（standard_brand 粒度归并后的实体）"""
    standard_id: str                 # BRAND_000621
    standard_brand: str              # 惠普/HP
    brand_codes: list[str] = field(default_factory=list)   # 归并的欧菲斯品牌编码
    names: set[str] = field(default_factory=set)           # 已登记名称（brand_name 们）
    aliases: set[str] = field(default_factory=set)         # 正式别名
    cn_name: str = ""
    en_name: str = ""


class BrandRepository:
    """品牌库内存索引。服务启动时加载一次；支持 mtime 校验后 reload。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._loaded_mtime: float = 0.0
        self.data_version: str = ""
        self.brand_count: int = 0
        self.alias_count: int = 0
        # 索引（比较键 -> set[standard_id]）
        self._brands: dict[str, StandardBrand] = {}          # standard_id -> StandardBrand
        self._idx_standard: dict[str, set[str]] = {}         # 标准品牌全名键
        self._idx_name: dict[str, set[str]] = {}             # 登记名称键（brand_name）
        self._idx_variant: dict[str, set[str]] = {}          # 标准名中/英文拆分变体键
        self._idx_alias: dict[str, set[str]] = {}            # 正式别名键
        self._fuzzy_choices: dict[str, str] = {}             # 展示名 -> standard_id（模糊召回池）

    # ------------------------------------------------------------------ load

    def load(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"品牌库数据库不存在: {self.db_path}")
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                ver = conn.execute(
                    "SELECT id, version FROM brand_versions WHERE status='active' LIMIT 1"
                ).fetchone()
                if not ver:
                    raise ValueError("品牌库中没有 active 品牌版本")
                rows = conn.execute(
                    "SELECT brand_code, brand_name, standard_brand, aliases "
                    "FROM brands WHERE version_id=? AND status='启用'",
                    (ver["id"],),
                ).fetchall()
                formal_aliases = self._load_formal_aliases(conn)
                self._build_indexes(rows, formal_aliases)
                self.data_version = str(ver["version"])
                self._loaded_mtime = self.db_path.stat().st_mtime
            finally:
                conn.close()

    @staticmethod
    def _load_formal_aliases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
        """brand_alias 正式别名库（status=active 的行）；表可能为空。"""
        try:
            return conn.execute(
                "SELECT alias_name, standard_brand_cn, standard_brand_en, standard_brand_id "
                "FROM brand_alias WHERE status IS NULL OR status IN ('active','正式','formal')"
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    def reload_if_changed(self) -> bool:
        """品牌库文件有更新则重新加载。返回是否执行了 reload。"""
        if not self.db_path.exists():
            return False
        if self.db_path.stat().st_mtime > self._loaded_mtime:
            self.load()
            return True
        return False

    def _build_indexes(self, rows, formal_aliases) -> None:
        # 1) 按 standard_brand 归并
        by_std: dict[str, dict] = {}
        for r in rows:
            std = normalized_text(r["standard_brand"]) or normalized_text(r["brand_name"])
            if not std:
                continue
            g = by_std.setdefault(std, {"codes": [], "names": set(), "aliases": set()})
            code = str(r["brand_code"]).strip()
            if code:
                g["codes"].append(code)
            name = normalized_text(r["brand_name"])
            if name:
                g["names"].add(name)
            for a in split_aliases(r["aliases"]):
                g["aliases"].add(a)

        brands: dict[str, StandardBrand] = {}
        idx_standard: dict[str, set[str]] = {}
        idx_name: dict[str, set[str]] = {}
        idx_variant: dict[str, set[str]] = {}
        idx_alias: dict[str, set[str]] = {}
        fuzzy_choices: dict[str, str] = {}

        def _add(idx: dict[str, set[str]], key: str, sid: str):
            if key:
                idx.setdefault(key, set()).add(sid)

        for std, g in by_std.items():
            codes = sorted(g["codes"], key=lambda c: (len(c), c))
            canonical = codes[0] if codes else "0"
            sid = f"BRAND_{canonical.zfill(6)}"
            variants = brand_name_variants(std)
            cn = next((v for v in variants[1:] if any('\u4e00' <= ch <= '\u9fff' for ch in v)), "")
            en = next((v for v in variants[1:] if v.isascii()), "")
            sb = StandardBrand(
                standard_id=sid, standard_brand=std, brand_codes=codes,
                names=set(g["names"]), aliases=set(g["aliases"]),
                cn_name=cn, en_name=en,
            )
            brands[sid] = sb

            _add(idx_standard, comparison_key(std), sid)
            for name in g["names"]:
                _add(idx_name, comparison_key(name), sid)
                fuzzy_choices.setdefault(name, sid)
            for v in variants[1:]:
                _add(idx_variant, comparison_key(v), sid)
                fuzzy_choices.setdefault(v, sid)
            for a in g["aliases"]:
                _add(idx_alias, comparison_key(a), sid)
                fuzzy_choices.setdefault(a, sid)
            fuzzy_choices.setdefault(std, sid)

        # 2) brand_alias 正式别名库（追加到别名索引）
        alias_rows = 0
        std_by_name = {comparison_key(b.standard_brand): sid for sid, b in brands.items()}
        for r in formal_aliases:
            alias = normalized_text(r["alias_name"])
            if not alias:
                continue
            # 通过 standard_brand_cn/en 反查标准品牌
            target = None
            for cand in (r["standard_brand_cn"], r["standard_brand_en"]):
                k = comparison_key(cand)
                if k and k in std_by_name:
                    target = std_by_name[k]
                    break
                if k and k in idx_standard and len(idx_standard[k]) == 1:
                    target = next(iter(idx_standard[k]))
                    break
            if target:
                _add(idx_alias, comparison_key(alias), target)
                brands[target].aliases.add(alias)
                fuzzy_choices.setdefault(alias, target)
                alias_rows += 1

        with self._lock:
            self._brands = brands
            self._idx_standard = idx_standard
            self._idx_name = idx_name
            self._idx_variant = idx_variant
            self._idx_alias = idx_alias
            self._fuzzy_choices = fuzzy_choices
            self.brand_count = len(brands)
            self.alias_count = sum(len(b.aliases) for b in brands.values()) + alias_rows

    # ---------------------------------------------------------------- lookup

    def get(self, standard_id: str) -> StandardBrand | None:
        return self._brands.get(standard_id)

    def lookup_standard(self, key: str) -> set[str]:
        return self._idx_standard.get(key, set())

    def lookup_name(self, key: str) -> set[str]:
        return self._idx_name.get(key, set())

    def lookup_variant(self, key: str) -> set[str]:
        return self._idx_variant.get(key, set())

    def lookup_alias(self, key: str) -> set[str]:
        return self._idx_alias.get(key, set())

    def fuzzy_candidates(self, text: str, limit: int = 5, threshold: float = 88.0) -> list[tuple[str, str, float]]:
        """模糊召回（仅候选，不可自动确认）。返回 [(展示名, standard_id, score)]。"""
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            return []
        if not text or not self._fuzzy_choices:
            return []
        matches = process.extract(
            text, list(self._fuzzy_choices.keys()), scorer=fuzz.ratio, limit=limit * 2,
        )
        out: list[tuple[str, str, float]] = []
        seen: set[str] = set()
        for name, score, _ in matches:
            if score < threshold:
                continue
            sid = self._fuzzy_choices[name]
            if sid in seen:
                continue
            out.append((name, sid, float(score)))
            seen.add(sid)
            if len(out) >= limit:
                break
        return out
