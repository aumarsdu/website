#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sou_crawler.config import CrawlSettings
from sou_crawler.pipeline import category_dir_name, record_key, record_site_dirs, topic_dir_name
from sou_crawler.storage import read_jsonl, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild output/site from normalized records and existing assets.")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = CrawlSettings(output_dir=Path(args.output_dir))
    records = read_jsonl(settings.processed_dir / "projects.jsonl")
    site_dirs = record_site_dirs(records, settings.site_dir)
    stats = {
        "records": len(records),
        "detail_files": 0,
        "asset_files_seen": 0,
        "asset_files_copied": 0,
        "asset_files_skipped_existing": 0,
        "missing_asset_dirs": 0,
        "dry_run": args.dry_run,
    }

    for record in records:
        key = record_key(record)
        target_dir = site_dirs[key]
        if not args.dry_run:
            write_json(target_dir / "details.json", record)
        stats["detail_files"] += 1

        copied_from_any_dir = False
        for source_dir in old_asset_dirs(settings.assets_dir, record):
            if not source_dir.exists():
                continue
            copied_from_any_dir = True
            for source_file in sorted(item for item in source_dir.iterdir() if item.is_file() and item.name != ".DS_Store"):
                stats["asset_files_seen"] += 1
                base_target_file = target_dir / source_file.name
                if base_target_file.exists() and base_target_file.stat().st_size == source_file.stat().st_size:
                    stats["asset_files_skipped_existing"] += 1
                    continue
                target_file = unique_target_path(base_target_file)
                if not args.dry_run:
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, target_file)
                stats["asset_files_copied"] += 1
        if not copied_from_any_dir:
            stats["missing_asset_dirs"] += 1

    if not args.dry_run:
        write_json(settings.reports_dir / "rebuild_site_mirror_stats.json", stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def old_asset_dirs(assets_root: Path, record: dict) -> list[Path]:
    title = topic_dir_name(record)
    categories = [category_dir_name(record), "未分类"]
    seen: set[Path] = set()
    dirs: list[Path] = []
    for category in categories:
        path = assets_root / category / title
        if path not in seen:
            seen.add(path)
            dirs.append(path)
    return dirs


def unique_target_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10_000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"unable to allocate unique target path for {path}")


if __name__ == "__main__":
    raise SystemExit(main())
