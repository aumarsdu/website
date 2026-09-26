from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .config import CrawlSettings
from .pipeline import download_assets, load_normalized_records, record_key, record_site_dirs
from .storage import read_json, write_json
from .utils import now_iso


def archive_snapshot_topics(
    settings: CrawlSettings,
    *,
    snapshot_id: str,
    target_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy one refresh snapshot's topic directories without overwriting conflicts."""

    identifiers = snapshot_detail_identifiers(settings, snapshot_id)
    records = load_normalized_records(settings)
    site_dirs = record_site_dirs(records, settings.site_dir)
    selected = [record for record in records if record_identifier(record) in identifiers]
    target_root = target_dir.resolve()
    site_root = settings.site_dir.resolve()
    if target_root == site_root or target_root.is_relative_to(site_root):
        raise ValueError("target directory must not be inside output/site")

    stats: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "target_dir": str(target_root),
        "topics": len(selected),
        "source_detail_identifiers": len(identifiers),
        "copied": 0,
        "skipped_existing": 0,
        "missing_source_files": 0,
        "conflicts": [],
        "dry_run": dry_run,
    }
    for record in selected:
        source_dir = site_dirs[record_key(record)]
        if not source_dir.is_dir():
            stats["missing_source_files"] += 1
            continue
        for source_path in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            relative_path = source_path.relative_to(settings.site_dir)
            target_path = target_root / relative_path
            if target_path.exists():
                if target_path.is_file() and file_digest(source_path) == file_digest(target_path):
                    stats["skipped_existing"] += 1
                else:
                    stats["conflicts"].append(str(relative_path))
                continue
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
            stats["copied"] += 1
    if not dry_run:
        stats["finished_at"] = now_iso()
        write_json(settings.reports_dir / f"archive_snapshot_{snapshot_id}.json", stats)
    return stats


async def download_snapshot_assets(
    settings: CrawlSettings,
    *,
    snapshot_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Download public assets only for topics first detailed in one refresh snapshot."""

    identifiers = snapshot_detail_identifiers(settings, snapshot_id)
    all_records = load_normalized_records(settings)
    selected = [record for record in all_records if record_identifier(record) in identifiers]
    stats = await download_assets(
        settings,
        dry_run=dry_run,
        records=selected,
        site_dirs=record_site_dirs(all_records, settings.site_dir),
    )
    stats["snapshot_id"] = snapshot_id
    stats["snapshot_topics"] = len(selected)
    stats["source_detail_identifiers"] = len(identifiers)
    if not dry_run:
        write_json(settings.reports_dir / f"download_snapshot_assets_{snapshot_id}.json", stats)
    return stats


def snapshot_detail_identifiers(settings: CrawlSettings, snapshot_id: str) -> set[str]:
    detail_dir = settings.raw_dir / "details" / f"refresh_{snapshot_id}" / "harbour_topics"
    if not detail_dir.exists():
        raise FileNotFoundError(f"refresh detail snapshot not found: {detail_dir}")
    identifiers: set[str] = set()
    for path in sorted(detail_dir.glob("*.json")):
        payload = read_json(path)
        request = payload.get("request") if isinstance(payload, dict) else None
        identifier = request.get("identifier") if isinstance(request, dict) else None
        if identifier not in (None, ""):
            identifiers.add(str(identifier))
    return identifiers


def record_identifier(record: dict[str, Any]) -> str:
    value = record.get("id") or record.get("uuid")
    return str(value) if value not in (None, "") else ""


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()
