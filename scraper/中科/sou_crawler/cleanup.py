from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any

from .audit import audit_manifest_path, find_legacy_asset_dirs
from .config import CrawlSettings, ensure_output_dirs
from .pipeline import load_normalized_records
from .scope import is_allowed_raw_source, is_topic_source
from .storage import read_json, write_csv, write_json, write_jsonl, write_sqlite
from .utils import now_iso


def cleanup_out_of_scope(settings: CrawlSettings, *, snapshot_id: str) -> dict[str, Any]:
    """Permanently remove only entries validated by the scope-audit manifest."""

    ensure_output_dirs(settings)
    manifest_path = audit_manifest_path(settings, snapshot_id)
    if not manifest_path.exists():
        raise FileNotFoundError(f"scope-audit manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)
    records = load_normalized_records(settings)
    out_of_scope = [record for record in records if not is_topic_source(record.get("source_url"))]
    validate_record_manifest(out_of_scope, manifest.get("out_of_scope_records", []))
    site_paths = [Path(value) for value in manifest.get("out_of_scope_site_detail_paths", [])]
    raw_paths = [Path(value) for value in manifest.get("out_of_scope_raw_paths", [])]
    legacy_asset_paths = [Path(value) for value in manifest.get("out_of_scope_legacy_asset_paths", [])]
    validate_site_paths(settings, site_paths)
    validate_raw_paths(settings, raw_paths)
    validate_legacy_asset_paths(settings, legacy_asset_paths, records, out_of_scope)

    for path in site_paths:
        shutil.rmtree((settings.site_dir / path).parent)
    for path in raw_paths:
        path.unlink()
    for path in legacy_asset_paths:
        shutil.rmtree(settings.assets_dir / path)

    retained = [record for record in records if is_topic_source(record.get("source_url"))]
    write_jsonl(settings.processed_dir / "projects.jsonl", retained)
    write_csv(settings.processed_dir / "projects.csv", retained)
    reset_sqlite(settings.processed_dir / "projects.sqlite")
    write_sqlite(settings.processed_dir / "projects.sqlite", retained)
    stats = {
        "cleaned_at": now_iso(),
        "snapshot_id": snapshot_id,
        "records_removed": len(out_of_scope),
        "site_directories_removed": len(site_paths),
        "raw_files_removed": len(raw_paths),
        "legacy_asset_directories_removed": len(legacy_asset_paths),
        "records_retained": len(retained),
    }
    write_json(settings.reports_dir / f"scope_cleanup_{snapshot_id}.json", stats)
    return stats


def validate_record_manifest(records: list[dict[str, Any]], manifest_records: list[dict[str, Any]]) -> None:
    actual = {(str(record.get("id") or record.get("uuid") or ""), str(record.get("source_url") or "")) for record in records}
    expected = {(str(record.get("id") or ""), str(record.get("source_url") or "")) for record in manifest_records}
    if actual != expected:
        raise RuntimeError("scope-audit manifest no longer matches current out-of-scope records; run audit-archive again")


def validate_site_paths(settings: CrawlSettings, paths: list[Path]) -> None:
    root = settings.site_dir.resolve()
    for relative_path in paths:
        detail_path = (settings.site_dir / relative_path).resolve()
        if not detail_path.is_relative_to(root) or detail_path.name != "details.json" or not detail_path.exists():
            raise RuntimeError(f"invalid site path in scope-audit manifest: {relative_path}")
        if is_topic_source(read_json(detail_path).get("source_url")):
            raise RuntimeError(f"refusing to remove in-scope site path: {relative_path}")


def validate_raw_paths(settings: CrawlSettings, paths: list[Path]) -> None:
    root = settings.raw_dir.resolve()
    for value in paths:
        raw_path = value.resolve()
        if not raw_path.is_relative_to(root) or not raw_path.exists():
            raise RuntimeError(f"invalid raw path in scope-audit manifest: {value}")
        payload = read_json(raw_path)
        source = payload.get("request", {}).get("url") or payload.get("source_api", {}).get("endpoint")
        if not source or is_allowed_raw_source(source):
            raise RuntimeError(f"refusing to remove in-scope raw path: {value}")


def validate_legacy_asset_paths(
    settings: CrawlSettings,
    paths: list[Path],
    records: list[dict[str, Any]],
    out_of_scope: list[dict[str, Any]],
) -> None:
    in_scope = [record for record in records if is_topic_source(record.get("source_url"))]
    expected = set(find_legacy_asset_dirs(settings, in_scope, out_of_scope)["removable_paths"])
    actual = {str(path) for path in paths}
    if actual != expected:
        raise RuntimeError("scope-audit manifest no longer matches removable legacy asset directories; run audit-archive again")
    root = settings.assets_dir.resolve()
    for relative_path in paths:
        path = (settings.assets_dir / relative_path).resolve()
        if not path.is_relative_to(root) or not path.is_dir():
            raise RuntimeError(f"invalid legacy asset path in scope-audit manifest: {relative_path}")


def reset_sqlite(path: Path) -> None:
    if not path.exists():
        return
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM projects")
