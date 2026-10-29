#!/usr/bin/env python3
"""Pack per-topic ``details.json`` archives into one records JSONL.

Zhongke (and some other partners) archive one JSON file per topic rather than a
single normalized export. The package reads JSONL, so this is the seam between
the two. It only reads; nothing under the input tree is modified.

Usage
-----
    python details_json_to_jsonl.py \
        --input ../../中科/output/site_before_taxonomy_20260707 \
        --out   data/real/zhongke_details.jsonl \
        --limit 300
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterator

DETAIL_NAMES = ("details.json", "detail.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="归档根目录（递归找 details.json）")
    parser.add_argument("--out", type=Path, required=True, help="输出 records.jsonl")
    parser.add_argument("--limit", type=int, help="只打包这么多条")
    parser.add_argument("--offset", type=int, default=0)
    return parser.parse_args(argv)


def iter_details(root: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in sorted(root.rglob("*"), key=lambda item: str(item)):
        if not path.is_file() or path.name not in DETAIL_NAMES:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            yield path, payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.input.exists():
        print(f"找不到输入目录: {args.input}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)

    written = skipped = 0
    with args.out.open("w", encoding="utf-8") as handle:
        for index, (path, payload) in enumerate(iter_details(args.input)):
            if index < args.offset:
                continue
            if args.limit is not None and written >= args.limit:
                break
            if not payload.get("title") and not payload.get("id"):
                skipped += 1
                continue
            record = dict(payload)
            record.setdefault("source_url", payload.get("source_url", ""))
            # Where the record came from, so a reviewer can find the original.
            record["_archive_path"] = str(path)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(f"输出 {args.out}：{written} 条（跳过 {skipped}）", file=sys.stderr)
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
