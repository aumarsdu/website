#!/usr/bin/env python3
"""Move the confirmed merged poster set into subject folders."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SUBJECTS = {"商科", "工科", "理科", "人文"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("Poster/output_pbl_merged_unique_20260710"))
    parser.add_argument("--poster-root", type=Path, default=Path("Poster"))
    parser.add_argument("--execute", action="store_true", help="Perform the move; otherwise only validate and print the plan.")
    return parser.parse_args()


def target_for(source_file: Path, source_root: Path, poster_root: Path) -> tuple[str, Path]:
    relative = source_file.relative_to(source_root)
    source_batch = relative.parts[0]
    parts = relative.parts[1:]
    subject_index = next(index for index, part in enumerate(parts) if part in SUBJECTS)
    subject = parts[subject_index]
    remaining = parts[subject_index + 1 :]
    return subject, poster_root / subject / source_batch / Path(*remaining)


def main() -> int:
    args = parse_args()
    source_root = args.source.resolve()
    poster_root = args.poster_root.resolve()
    if not source_root.is_dir():
        raise SystemExit(f"Source directory missing: {source_root}")
    files = sorted(
        path
        for path in source_root.rglob("Finish_*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    moves: list[dict[str, str]] = []
    target_paths: set[Path] = set()
    for source_file in files:
        subject, target = target_for(source_file, source_root, poster_root)
        if target in target_paths:
            raise SystemExit(f"Duplicate target path: {target}")
        target_paths.add(target)
        moves.append({"subject": subject, "source": str(source_file), "target": str(target)})

    existing = [Path(item["target"]) for item in moves if Path(item["target"]).exists()]
    if existing:
        raise SystemExit(f"Target paths already exist: {len(existing)}")

    report_dir = poster_root / "_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "confirmed_poster_organization_20260710.jsonl"
    with report_path.open("w", encoding="utf-8") as stream:
        for item in moves:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")

    if args.execute:
        for item in moves:
            target = Path(item["target"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(item["source"], target)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source_root),
        "poster_root": str(poster_root),
        "planned_count": len(moves),
        "by_subject": {subject: sum(1 for item in moves if item["subject"] == subject) for subject in sorted(SUBJECTS)},
        "executed": args.execute,
        "manifest": str(report_path),
    }
    (report_dir / "confirmed_poster_organization_20260710.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
