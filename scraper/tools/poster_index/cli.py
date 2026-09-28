"""poster_index CLI: index / find (需求文档 4.3)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import common, hirep, jisi, zhongke

SUPPLIERS = {"集思未来": jisi, "HIREP": hirep, "中科浩博": zhongke}


def cmd_index(args: argparse.Namespace) -> int:
    names = list(SUPPLIERS) if args.supplier == "all" else [args.supplier]
    for name in names:
        module = SUPPLIERS.get(name)
        if module is None:
            print(f"未知供应商: {name}", file=sys.stderr)
            return 2
        items, report = module.build()
        index_path, report_path = common.write_index_and_report(name, items, report)
        print(json.dumps({
            "supplier": name,
            "index": str(index_path),
            "report": str(report_path),
            "items": len(items),
            "total_courses": report.get("total_courses"),
        }, ensure_ascii=False))
    return 0


def _load_items(supplier: str) -> list[dict[str, Any]]:
    path = common.OUTPUT_DIR / f"{supplier}.index.json"
    if not path.exists():
        raise FileNotFoundError(f"索引不存在: {path}，请先运行 index --supplier {supplier}")
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def cmd_find(args: argparse.Namespace) -> int:
    names = list(SUPPLIERS) if args.supplier == "all" else [args.supplier]
    items = []
    for name in names:
        items.extend(_load_items(name))
    matched = common.find_in_index(
        items,
        subject=args.subject,
        project_type=args.type,
        begins_from=args.begins_from,
        begins_to=args.begins_to,
        open_only=args.open_only,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(matched, ensure_ascii=False, indent=1, default=str))
        return 0
    print(f"{'供应商':<6} {'学科':<10} {'开课':<12} {'类型':<14} 课题 / 海报")
    for item in matched:
        begins = item.get("schoolBegins") or "—"
        print(f"{item['supplier']:<6} {item['subject']:<10} {begins:<12} {item['projectType'][:14]:<14} "
              f"{item['title'][:36]}  {item['posterPath']}")
    print(f"-- 共 {len(matched)} 条", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="poster_index", description="供应商课题海报统一索引")
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="生成或重建索引与报告")
    p_index.add_argument("--supplier", choices=[*SUPPLIERS, "all"], required=True)

    p_find = sub.add_parser("find", help="按条件列出课题")
    p_find.add_argument("--supplier", choices=[*SUPPLIERS, "all"], required=True)
    p_find.add_argument("--subject", choices=common.SUBJECTS, default=None)
    p_find.add_argument("--type", dest="type", default=None, help="项目类型精确匹配")
    p_find.add_argument("--begins-from", default=None, help="YYYY-MM-DD")
    p_find.add_argument("--begins-to", default=None, help="YYYY-MM-DD")
    p_find.add_argument("--open-only", action="store_true", help="只列开课在今天之后的")
    p_find.add_argument("--limit", type=int, default=None)
    p_find.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "index":
        return cmd_index(args)
    if args.command == "find":
        return cmd_find(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
