"""
CLI 入口 —— 与 Skill / HTTP API 共用 ofs_brand_core。

用法:
  python cli.py normalize "HP"                       # 单值标准化
  python cli.py compare --att "HP,Canon" --src "惠普/HP"  # 双侧比对
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import get_settings
from ofs_brand_core import BrandRepository, BrandNormalizer


def main() -> None:
    parser = argparse.ArgumentParser(description="欧菲斯品牌标准化 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("normalize", help="单值标准化")
    p1.add_argument("value")

    p2 = sub.add_parser("compare", help="附件/数据库品牌比对")
    p2.add_argument("--att", required=True, help="附件品牌（逗号分隔）")
    p2.add_argument("--src", required=True, help="数据库品牌（逗号分隔）")

    args = parser.parse_args()
    repo = BrandRepository(get_settings().brand_data_path)
    repo.load()
    normalizer = BrandNormalizer(repo)

    if args.cmd == "normalize":
        out = asdict(normalizer.normalize_value(args.value))
    else:
        out = asdict(normalizer.compare(args.att, args.src))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
