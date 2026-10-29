#!/usr/bin/env python3
"""Convert an existing OCR batch CSV into the poster_ocr.jsonl contract.

Some source folders already carry a completed OCR batch as CSV: one row per
poster, with the recognised text and the per-block geometry in
``text_blocks_json``. Re-running a multi-gigabyte OCR model over data that has
already been recognised is waste, so this converter reuses that work.

It is the same seam as ``posters_to_ocr_jsonl.py`` and equally optional: the
package never imports it.

Usage
-----
    python ocr_csv_to_ocr_jsonl.py \
        --input ../../盐趣/盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv \
        --out   data/real/poster_ocr.jsonl \
        --provider yanxu \
        --limit 200
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

# poster_path is a long relative path; the default limit is too small for it.
csv.field_size_limit(10**9)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="OCR 批次 CSV")
    parser.add_argument("--out", type=Path, required=True, help="输出 poster_ocr.jsonl")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--limit", type=int, help="只转换这么多行")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--source-authority", default="supplier_marketing")
    parser.add_argument(
        "--title-from",
        choices=("poster-headline", "none"),
        default="none",
        help="不从 OCR 文本猜标题：真实海报的最大字号块未必是课题名，"
        "猜错会污染归组。默认留空，身份退回 --external-id-from。",
    )
    return parser.parse_args(argv)


def polygon_to_bbox(polygon: Any) -> list[int] | None:
    try:
        points = [(float(point[0]), float(point[1])) for point in polygon]
    except (TypeError, ValueError, IndexError):
        return None
    if len(points) < 2:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))]


def to_blocks(raw: str) -> list[dict[str, Any]]:
    """Convert ``text_blocks_json`` into contract blocks, keeping every block."""
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    blocks: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        bbox = polygon_to_bbox(item.get("polygon"))
        if bbox is None:
            continue
        confidence = item.get("confidence", item.get("conf"))
        blocks.append(
            {
                "text": text,
                "bbox": bbox,
                "conf": round(float(confidence), 4) if isinstance(confidence, (int, float)) else None,
            }
        )
    return blocks


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.input.exists():
        print(f"找不到输入 CSV: {args.input}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)

    written = skipped = 0
    with args.input.open(encoding="utf-8-sig", newline="") as src, args.out.open(
        "w", encoding="utf-8"
    ) as dst:
        for index, row in enumerate(csv.DictReader(src)):
            if index < args.offset:
                continue
            if args.limit is not None and written >= args.limit:
                break
            if str(row.get("status", "")).strip() != "ok":
                skipped += 1
                continue
            blocks = to_blocks(row.get("text_blocks_json", ""))
            if not blocks:
                skipped += 1
                continue
            poster_path = str(row.get("poster_path", "")).strip()
            stem = Path(poster_path).stem or f"row-{index:05d}"
            record = {
                "document_id": f"poster-{stem[:60]}",
                "provider": args.provider,
                "external_id": stem[:120],
                "title_hint": None,
                "source_authority": args.source_authority,
                "image": poster_path,
                "meta": {
                    "engine": row.get("engine"),
                    "detection_model": row.get("detection_model"),
                    "recognition_model": row.get("recognition_model"),
                    "block_count": row.get("text_block_count"),
                    "confidence_average": row.get("confidence_average"),
                    "source": str(args.input),
                },
                "blocks": blocks,
            }
            dst.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(f"输出 {args.out}：{written} 条（跳过 {skipped}）", file=sys.stderr)
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
