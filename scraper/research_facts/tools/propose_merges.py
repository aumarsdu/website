#!/usr/bin/env python3
"""Propose identity merges for a human to confirm.

A merge is the one operation here that destroys an identity, so this tool never
performs one. It writes a decisions file with an empty reviewer, which the
grouping stage refuses to apply until a person fills it in.

It proposes only pairs that are candidates *and* agree on every comparable
field. Real data makes the reason obvious: across three sources, 560 of 564
candidate pairs differed on start_date alone -- the same topic text offered in
different cohorts. Those are not duplicates, and a topic title that repeats
across cohorts is exactly the shape a naive merge destroys.

Usage
-----
    python propose_merges.py \\
        --inputs ../../中科/中科课题开课时间汇总-2026-09-23.csv:table_csv \\
        --profile-file data/profiles/zhongke_schedule.csv.json \\
        --out data/profiles/zhongke_dup_merges.json \\
        --reviewer "军亮"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research_facts.config import Settings  # noqa: E402
from research_facts.dedup import build_duplicate_report  # noqa: E402
from research_facts.merge import build_records  # noqa: E402
from research_facts.merging import (  # noqa: E402
    MergeDecision,
    MergeRegistry,
    fingerprint_of_claims,
)
from research_facts.pipeline import _load_inputs  # noqa: E402
from research_facts.utils import now_iso  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inputs", nargs="+", required=True, help="输入 path:kind")
    parser.add_argument("--profile-file", action="append", default=[])
    parser.add_argument("--profile", default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-records", type=int, default=800)
    parser.add_argument("--reviewer", default="", help="留空则不会被应用（需人工填写）")
    parser.add_argument("--note", default="可比字段全部一致，判定为源侧重复条目")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings(
        output_dir=args.out.parent,
        inputs=list(args.inputs),
        profile_files=list(args.profile_file),
        profile=args.profile,
        strict_identity=True,
        max_records=args.max_records,
    )
    outputs, _, errors, _, _ = _load_inputs(settings)
    if errors:
        print(f"输入有问题，未生成提案：{errors}", file=sys.stderr)
        return 2

    records, _ = build_records(outputs, settings)
    report = build_duplicate_report(records)
    by_key = {record.record_key: record for record in records}

    registry = MergeRegistry(path=args.out)
    for candidate in report["candidates"]:
        if not candidate.get("is_mergeable"):
            continue
        claims = [
            claim
            for key in (candidate["left"], candidate["right"])
            for state in by_key[key].fields.values()
            for claim in state.claims
        ]
        registry.add(
            MergeDecision(
                left=candidate["left"],
                right=candidate["right"],
                fingerprint=fingerprint_of_claims(claims),
                reviewer=args.reviewer,
                merged_at=now_iso(),
                note=args.note,
            )
        )

    if not args.reviewer:
        print("未填 --reviewer：提案已写出但不会被应用。", file=sys.stderr)
    registry.save(args.out)
    print(
        f"候选 {report['candidate_count']} 对 → 可合并 {report['mergeable_count']} 对"
        f"（有字段分歧 {report['diverging_count']} 对，不予合并）",
        file=sys.stderr,
    )
    print(f"提案写入 {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
