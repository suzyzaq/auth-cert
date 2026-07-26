#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCS 候选品牌回流脚本（品牌主数据自增长闭环）。

背景:
  brand-normalize-service 在本地品牌库未命中时会回退查询 SCS 在线品牌库，
  命中结果仅作候选（scs_candidate），需人工复核确认后才可视为同品牌。
  本脚本把「人工已确认」的 SCS 品牌写回本地 matcher.db，使后续请求直接命中
  本地库，不再每次查 SCS，逐步沉淀品牌主数据。

写入规则（依据 BrandRepository 加载逻辑）:
  - standard_brand 已存在于 brands  -> 写入 brand_alias（作为已有标准品牌的别名），
    复用其标准品牌 ID（BRAND_xxxxxx）；不触碰 brands 的 UNIQUE(version_id,brand_code)。
  - standard_brand 不存在 / 未填      -> 写入 brands 新建标准品牌，brand_code 自增生成。

输入文件 (JSON 数组):
  [
    {"firm_code": 182805, "firm_name": "洁佳人", "standard_brand": "洁佳人"},
    {"firm_code": 7563,   "firm_name": "惠普企业版", "standard_brand": "惠普/HP"}
  ]
  firm_code      : SCS 厂商编码（仅追溯，不进 matcher.db）
  firm_name      : 必填，要识别的品牌名（写入 brand_name 或 alias_name）
  standard_brand : 可选。填了且库中存在=映射为别名；填了但库中没有=新建该标准品牌；
                  不填=以 firm_name 作为新标准品牌。

用法:
  python scripts/scs_backfill.py --db <matcher.db> --input confirmed.json          # dry-run
  python scripts/scs_backfill.py --db <matcher.db> --input confirmed.json --apply   # 写库
  python scripts/scs_backfill.py --db <matcher.db> --input confirmed.json --apply --reload-cmd "bash manage.sh reload"

默认 dry-run（不写库）。写库后需 reload 服务（manage.sh reload）才生效。
幂等：已存在的 brand_name / alias_name 自动跳过。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path.home() / ".workbuddy" / "skills" / "brand-matcher" / "data" / "matcher.db"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_active_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM brand_versions WHERE status='active' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        raise ValueError("matcher.db 中没有 active 品牌版本")
    return int(row["id"])


def max_brand_code(conn: sqlite3.Connection, version_id: int) -> int:
    rows = conn.execute(
        "SELECT brand_code FROM brands WHERE version_id=?", (version_id,)
    ).fetchall()
    m = 0
    for r in rows:
        try:
            m = max(m, int(str(r["brand_code"]).strip()))
        except ValueError:
            pass
    return m


def canonical_id_for_standard(conn: sqlite3.Connection, version_id: int, std: str):
    """标准品牌已存在则返回其规范 BRAND_xxxxxx ID；否则 None。"""
    row = conn.execute(
        "SELECT brand_code FROM brands WHERE version_id=? AND status='启用' "
        "AND standard_brand=? ORDER BY length(brand_code), brand_code LIMIT 1",
        (version_id, std),
    ).fetchone()
    if not row:
        return None
    return "BRAND_" + str(row["brand_code"]).zfill(6)


def brand_name_exists(conn: sqlite3.Connection, version_id: int, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM brands WHERE version_id=? AND status='启用' AND brand_name=?",
        (version_id, name),
    ).fetchone() is not None


def alias_exists(conn: sqlite3.Connection, name: str) -> bool:
    try:
        return conn.execute(
            "SELECT 1 FROM brand_alias WHERE alias_name=?", (name,)
        ).fetchone() is not None
    except sqlite3.OperationalError:
        return False


def build_plan(conn: sqlite3.Connection, items: list[dict]) -> tuple[list[dict], int, int]:
    version_id = get_active_version(conn)
    next_code = max_brand_code(conn, version_id) + 1
    plan: list[dict] = []
    skipped = 0
    for it in items:
        firm_code = it.get("firm_code")
        firm_name = (it.get("firm_name") or "").strip()
        std_in = (it.get("standard_brand") or "").strip()
        if not firm_name:
            print(f"[跳过] firm_name 为空: {it}")
            skipped += 1
            continue
        if brand_name_exists(conn, version_id, firm_name) or alias_exists(conn, firm_name):
            print(f"[跳过] 已存在 {firm_name!r} (firm_code={firm_code})")
            skipped += 1
            continue

        if std_in:
            sid = canonical_id_for_standard(conn, version_id, std_in)
            if sid is not None:
                # 映射到已有标准品牌 -> 写 brand_alias
                plan.append({"kind": "alias", "firm_name": firm_name,
                             "std": std_in, "sid": sid, "firm_code": firm_code})
                continue
            target_std = std_in
        else:
            target_std = firm_name

        # 新建标准品牌 -> 写 brands（本地自增编码，保证同批次唯一）
        code = next_code
        next_code += 1
        plan.append({"kind": "brand", "firm_name": firm_name, "std": target_std,
                     "code": str(code), "sid": "BRAND_" + str(code).zfill(6),
                     "firm_code": firm_code})

    return plan, skipped, version_id


def apply_plan(conn: sqlite3.Connection, plan: list[dict]) -> None:
    now = _now()
    cur = conn.cursor()
    for p in plan:
        if p["kind"] == "alias":
            cur.execute(
                "INSERT INTO brand_alias "
                "(alias_name, standard_brand_id, standard_brand_cn, standard_brand_en, "
                "alias_type, match_method, confidence, hit_count, success_count, fail_count, "
                "status, need_review, created_at, updated_at, last_hit_at, created_by, "
                "review_by, review_note, version) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["firm_name"], p["sid"], p["std"], "", "scs_backfill", "exact", 1.0,
                 0, 0, 0, "active", 0, now, now, None, "scs_backfill", "", "", 1),
            )
        else:
            cur.execute(
                "INSERT INTO brands (version_id, brand_code, brand_name, standard_brand, "
                "aliases, status, standard_source) VALUES (?,?,?,?,?,?,?)",
                (get_active_version(conn), p["code"], p["firm_name"], p["std"],
                 "", "启用", "scs_backfill"),
            )
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser(description="SCS 候选品牌回流到 matcher.db")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="matcher.db 路径")
    ap.add_argument("--input", required=True, help="确认后的 SCS 品牌 JSON 文件")
    ap.add_argument("--apply", action="store_true", help="真正写库（默认 dry-run）")
    ap.add_argument("--reload-cmd", default="", help="写库后执行的 reload 命令（可选）")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[错误] 输入文件不存在: {in_path}", file=sys.stderr)
        return 2
    try:
        items = json.loads(in_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 解析 JSON 失败: {exc}", file=sys.stderr)
        return 2
    if not isinstance(items, list):
        print("[错误] 输入 JSON 必须是数组", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        plan, skipped, version_id = build_plan(conn, items)
    finally:
        conn.close()

    print(f"\n=== backfill plan (version_id={version_id}, apply={args.apply}) ===")
    for p in plan:
        if p["kind"] == "alias":
            print(f"  + [alias] {p['firm_name']!r} -> 标准品牌 {p['std']!r} "
                  f"(id={p['sid']})  [scs firm_code={p['firm_code']}]")
        else:
            print(f"  + [brand] {p['firm_name']!r} -> 标准品牌 {p['std']!r} "
                  f"(brand_code={p['code']}, id={p['sid']})  [scs firm_code={p['firm_code']}]")

    if not args.apply:
        print(f"\n[DRY-RUN] 将写入 {len(plan)} 条，跳过 {skipped} 条。加 --apply 真正写库。")
        return 0

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row  # 关键：apply 分支重开 conn 必须补上，否则 get_active_version 的 row["id"] 会 TypeError
    try:
        apply_plan(conn, plan)
    finally:
        conn.close()
    print(f"\n[APPLIED] 已写入 {len(plan)} 条，跳过 {skipped} 条。")

    if args.reload_cmd:
        import subprocess
        print(f"\n[reload] 执行: {args.reload_cmd}")
        try:
            subprocess.run(args.reload_cmd, shell=True, check=False)
        except Exception as exc:  # noqa: BLE001
            print(f"[警告] reload 命令执行失败: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
