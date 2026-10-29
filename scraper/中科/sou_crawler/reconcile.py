from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .config import CrawlSettings, ensure_output_dirs
from .pipeline import load_normalized_records, record_key, record_site_dirs
from .scope import is_topic_source
from .storage import read_json, write_json
from .utils import file_digest, now_iso


def reconcile_site_layout(settings: CrawlSettings) -> dict[str, Any]:
    """Move misplaced in-scope topic directories after preserving missing assets."""

    ensure_output_dirs(settings)
    records = [record for record in load_normalized_records(settings) if is_topic_source(record.get("source_url"))]
    site_dirs = record_site_dirs(records, settings.site_dir)
    expected_dirs = {record_key(record): site_dirs[record_key(record)] for record in records}
    stats: dict[str, Any] = {"scanned": 0, "moved": 0, "assets_copied": 0, "conflicts": []}
    for detail_path in sorted(settings.site_dir.rglob("details.json")):
        payload = read_json(detail_path)
        if not is_topic_source(payload.get("source_url")):
            continue
        expected_dir = expected_dirs.get(record_key(payload))
        if expected_dir is None or detail_path.parent == expected_dir:
            continue
        stats["scanned"] += 1
        source_dir = detail_path.parent
        if not expected_dir.exists():
            expected_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_dir), str(expected_dir))
            stats["moved"] += 1
            continue
        copied = missing_asset_count(source_dir, expected_dir)
        conflicts = copy_missing_assets(source_dir, expected_dir)
        if conflicts:
            stats["conflicts"].append({"source": str(source_dir), "target": str(expected_dir), "files": conflicts})
            continue
        shutil.rmtree(source_dir)
        stats["moved"] += 1
        stats["assets_copied"] += copied
    stats["reconciled_at"] = now_iso()
    write_json(settings.reports_dir / "reconcile_site_layout.json", stats)
    return stats


def copy_missing_assets(source_dir: Path, target_dir: Path) -> list[str]:
    conflicts: list[str] = []
    for source in source_dir.rglob("*"):
        if not source.is_file() or source.name == "details.json":
            continue
        target = target_dir / source.relative_to(source_dir)
        if target.exists():
            if file_digest(source) != file_digest(target):
                conflicts.append(str(source.relative_to(source_dir)))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return conflicts


def missing_asset_count(source_dir: Path, target_dir: Path) -> int:
    return sum(1 for source in source_dir.rglob("*") if source.is_file() and source.name != "details.json" and not (target_dir / source.relative_to(source_dir)).exists())
