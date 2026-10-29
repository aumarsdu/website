#!/usr/bin/env python3
"""Survey poster templates: which layouts exist and what each one is worth.

The package refuses to guess a value it cannot read, which is right, but it
leaves one question open: *which* templates are worth writing a field table for?
This tool answers that from data instead of opinion.

For every poster in an OCR batch it runs the real extraction path and records:

* which labels were found and whether each produced a value,
* what was refused and why,
* a signature, so posters that behave the same cluster together.

A cluster is a template family. Its size is the payoff: a family worth 40
posters is worth a field table; a family worth one poster is not.

Usage
-----
    python survey_poster_templates.py \\
        --input ../../盐趣/盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv \\
        --out   data/real/template_survey.json \\
        --markdown data/real/template_survey.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research_facts.adapters.textblock import _blocks_from_payload, _row_blocks  # noqa: E402
from research_facts.config import Settings  # noqa: E402
from research_facts.extract import claims_from_blocks  # noqa: E402
from research_facts.labels import scan_line, template_signature  # noqa: E402

csv.field_size_limit(10**9)

# Shapes that identify a marketing poster's stat strip rather than a label/value
# pair: a big number with a unit, plus short caption chips under it.
_STAT_TILE_RE = re.compile(r"^\s*\d+\s*(?:周|次|封|课时|个月|天|人|篇)\s*$")
_CAPTIONISH_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z|｜·\-—\s]{2,12}$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="OCR 批次 CSV")
    parser.add_argument("--out", type=Path, required=True, help="输出 JSON")
    parser.add_argument("--markdown", type=Path, default=None, help="同时输出可读摘要")
    parser.add_argument("--provider", default="yanxu")
    parser.add_argument("--limit", type=int)
    return parser.parse_args(argv)


def polygon_to_bbox(polygon: Any) -> list[int] | None:
    try:
        points = [(float(p[0]), float(p[1])) for p in polygon]
    except (TypeError, ValueError, IndexError):
        return None
    if len(points) < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))]


def blocks_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(row.get("text_blocks_json", "") or "[]")
    except json.JSONDecodeError:
        return []
    blocks = []
    for item in parsed if isinstance(parsed, list) else []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        bbox = polygon_to_bbox(item.get("polygon"))
        if text and bbox:
            confidence = item.get("confidence", item.get("conf"))
            blocks.append(
                {
                    "text": text,
                    "bbox": bbox,
                    "conf": round(float(confidence), 4) if isinstance(confidence, (int, float)) else None,
                }
            )
    return blocks


def survey_one(row: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Run the real extractor and describe what this poster's layout offers."""
    document = {
        "document_id": f"poster-{Path(row.get('poster_path', '') or 'x').stem[:60]}",
        "blocks": blocks_from_row(row),
    }
    blocks, _ = _blocks_from_payload(document, document["document_id"])
    rows = _row_blocks(blocks, document["document_id"])
    rejected: list[Any] = []
    claims = claims_from_blocks(
        rows,
        document_id=document["document_id"],
        source_kind="poster_ocr",
        settings=settings,
        require_delimiter=False,
        locator_kind="text_row",
        base_confidence="medium",
        label_must_lead_row=True,
        rejected=rejected,
    )

    # Every label the layout contains, whether or not it produced a value.
    labels_found: Counter[str] = Counter()
    for block in rows:
        for hit in scan_line(block.text, require_delimiter=False):
            labels_found[hit.label] += 1
    leading = template_signature(rows)

    texts = [block.text for block in blocks]
    stat_tiles = [text for text in texts if _STAT_TILE_RE.match(text)]
    captions = [text for text in texts if _CAPTIONISH_RE.match(text)]
    affil = [text for text in texts if "大学" in text and "教授" in text]

    return {
        "document_id": document["document_id"],
        "poster_path": row.get("poster_path", ""),
        "signature": list(leading),
        "claims": [
            {"field": claim.field, "label": claim.extractor, "value": claim.normalized_value}
            for claim in claims
        ],
        "labels_found": dict(labels_found),
        "rejected": [
            {"field": item.field, "text": item.candidate_text, "reason": item.reason}
            for item in rejected
        ],
        "block_count": len(blocks),
        "stat_tiles": stat_tiles,
        "caption_count": len(captions),
        "affiliation_rows": len(affil),
    }


def iter_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("status", "")).strip() == "ok":
                yield row


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.input.exists():
        print(f"找不到输入: {args.input}", file=sys.stderr)
        return 2
    settings = Settings()

    clusters: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    scanned = 0
    for row in iter_rows(args.input):
        if args.limit is not None and scanned >= args.limit:
            break
        scanned += 1
        result = survey_one(row, settings)
        clusters[tuple(result["signature"])].append(result)

    families = []
    for signature, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        field_hits = Counter()
        label_hits: Counter[str] = Counter()
        for member in members:
            for claim in member["claims"]:
                field_hits[claim["field"]] += 1
                label_hits[claim["label"]] += 1
        tiles = Counter()
        for member in members:
            tiles.update(member["stat_tiles"])
        families.append(
            {
                "signature": list(signature),
                "posters": len(members),
                "share": round(len(members) / scanned, 4) if scanned else 0.0,
                "field_yield": dict(field_hits),
                "label_yield": dict(label_hits),
                "rejected_total": sum(len(m["rejected"]) for m in members),
                "blocks_median": sorted(m["block_count"] for m in members)[len(members) // 2],
                "stat_tile_share": round(
                    sum(1 for m in members if m["stat_tiles"]) / len(members), 4
                ),
                "common_stat_tiles": [value for value, _ in tiles.most_common(6)],
                "affiliation_row_share": round(
                    sum(1 for m in members if m["affiliation_rows"]) / len(members), 4
                ),
                "sample_posters": [m["poster_path"] for m in members[:3]],
            }
        )

    payload = {
        "input": str(args.input),
        "posters_scanned": scanned,
        "families": len(families),
        "rule": (
            "签名 = 该海报中位于行首且未被规则排除的标签集合；"
            "同一签名的海报行为一致，视为同一模板族。"
        ),
        "by_family": families,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.markdown:
        lines = [
            "# 海报模板族普查",
            "",
            f"输入：`{args.input}`　海报数：**{scanned}**　模板族数：**{len(families)}**",
            "",
            "| 模板族签名 | 海报数 | 占比 | 抽出字段 | 拒收 | 有大数字 | 常驻机构+职称行 |",
            "| --- | ---: | ---: | --- | ---: | ---: | ---: |",
        ]
        for family in families:
            lines.append(
                f"| {'、'.join(family['signature'])} | {family['posters']} | "
                f"{family['share']:.0%} | {family['field_yield'] or '—'} | "
                f"{family['rejected_total']} | {family['stat_tile_share']:.0%} | "
                f"{family['affiliation_row_share']:.0%} |"
            )
        lines.append("")
        lines.append("## 各族要点")
        lines.append("")
        for family in families:
            lines.append(f"### {'、'.join(family['signature'])}（{family['posters']} 张）")
            lines.append("")
            lines.append(f"- 抽出字段：{family['field_yield'] or '无'}")
            lines.append(f"- 命中标签：{family['label_yield'] or '无'}")
            lines.append(f"- 常见大数字：{family['common_stat_tiles'] or '无'}")
            lines.append(f"- 样例：{'；'.join(family['sample_posters'][:2]) or '—'}")
            lines.append("")
        args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"扫描 {scanned} 张，识别 {len(families)} 个模板族 → {args.out}", file=sys.stderr)
    for family in families:
        print(
            f"  {family['posters']:4} 张 ({family['share']:5.1%})  "
            f"{'+'.join(family['signature'])[:60]}  抽出={family['field_yield'] or '无'}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
