from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import CrawlSettings, DEFAULT_ENTRY_URLS, ensure_output_dirs
from .pipeline import (
    build_asset_jobs,
    category_dir_name,
    extract_items,
    item_identity,
    load_detail_items,
    load_normalized_records,
    record_key,
    record_site_dirs,
    topic_dir_name,
)
from .scope import (
    HARBOUR_TOPIC_CATEGORY_URL,
    HARBOUR_TOPIC_DETAIL_URL,
    HARBOUR_TOPIC_LIST_URL,
    is_allowed_raw_source,
    is_topic_detail_source,
    is_topic_source,
)
from .storage import read_json, write_json
from .utils import now_iso


def audit_archive(settings: CrawlSettings, *, snapshot_id: str) -> dict[str, Any]:
    """Audit scope, source coverage, detail coverage, and archive placement."""

    ensure_output_dirs(settings)
    records = load_normalized_records(settings)
    in_scope_records = [record for record in records if is_topic_source(record.get("source_url"))]
    out_of_scope_records = [record for record in records if not is_topic_source(record.get("source_url"))]
    live_ids = load_snapshot_topic_ids(settings, snapshot_id)
    local_ids = {record_identifier(record) for record in in_scope_records if record_identifier(record)}
    detail_ids = {
        item_identity(item)
        for item in load_detail_items(settings)
        if is_topic_detail_source(item.get("_source_url"))
    }
    site = audit_site_layout(settings, in_scope_records)
    assets = audit_assets(settings, in_scope_records)
    raw_paths = find_out_of_scope_raw_paths(settings)
    legacy_assets = find_legacy_asset_dirs(settings, in_scope_records, out_of_scope_records)
    manifest = build_manifest(
        out_of_scope_records,
        site["out_of_scope_detail_paths"],
        raw_paths,
        legacy_assets["removable_paths"],
    )
    report_path = audit_report_path(settings, snapshot_id)
    manifest_path = audit_manifest_path(settings, snapshot_id)
    report = {
        "generated_at": now_iso(),
        "report_path": str(report_path),
        "scope": {
            "entry_urls": DEFAULT_ENTRY_URLS,
            "list_endpoint": HARBOUR_TOPIC_LIST_URL,
            "detail_endpoint": HARBOUR_TOPIC_DETAIL_URL,
            "taxonomy_endpoint": HARBOUR_TOPIC_CATEGORY_URL,
        },
        "snapshot_id": snapshot_id,
        "records": {
            "total": len(records),
            "in_scope": len(in_scope_records),
            "out_of_scope": len(out_of_scope_records),
        },
        "current_public_list": {
            "records": len(live_ids),
            "missing_from_archive": sorted(live_ids - local_ids),
            "not_in_current_list": sorted(local_ids - live_ids),
        },
        "details": {
            "captured": len(detail_ids & live_ids),
            "missing_from_current_list": sorted(live_ids - detail_ids),
        },
        "site": site,
        "assets": assets,
        "out_of_scope": {
            "records": len(out_of_scope_records),
            "site_topic_directories": len(site["out_of_scope_detail_paths"]),
            "raw_files": len(raw_paths),
            "legacy_asset_directories": len(legacy_assets["removable_paths"]),
            "ambiguous_legacy_asset_directories": legacy_assets["ambiguous_paths"],
            "manifest": str(manifest_path),
        },
    }
    write_json(manifest_path, manifest)
    write_json(report_path, report)
    return report


def audit_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": report["snapshot_id"],
        "report": str(report.get("report_path") or ""),
        "records": report["records"],
        "current_public_list": {
            "records": report["current_public_list"]["records"],
            "missing_from_archive": len(report["current_public_list"]["missing_from_archive"]),
            "not_in_current_list": len(report["current_public_list"]["not_in_current_list"]),
        },
        "details": {
            "captured": report["details"]["captured"],
            "missing_from_current_list": len(report["details"]["missing_from_current_list"]),
        },
        "site": {
            "expected_topic_directories": report["site"]["expected_topic_directories"],
            "correctly_placed": report["site"]["correctly_placed"],
            "missing_detail_paths": len(report["site"]["missing_detail_paths"]),
            "misplaced_detail_paths": len(report["site"]["misplaced_detail_paths"]),
        },
        "assets": {
            "expected": report["assets"]["expected"],
            "present": report["assets"]["present"],
            "missing": len(report["assets"]["missing_paths"]),
            "pdf_expected": report["assets"]["pdf_expected"],
            "pdf_present": report["assets"]["pdf_present"],
        },
        "out_of_scope": report["out_of_scope"],
    }


def record_identifier(record: dict[str, Any]) -> str | None:
    value = record.get("id") or record.get("uuid")
    return str(value) if value not in (None, "") else None


def load_snapshot_topic_ids(settings: CrawlSettings, snapshot_id: str) -> set[str]:
    source_dir = settings.raw_dir / "lists" / f"refresh_{snapshot_id}" / "harbour_topics"
    if not source_dir.exists():
        raise FileNotFoundError(f"refresh snapshot not found: {source_dir}")
    identifiers: set[str] = set()
    for path in sorted(source_dir.glob("page_*.json")):
        payload = read_json(path)
        for item in extract_items(payload.get("data")):
            if isinstance(item, dict):
                identifiers.add(item_identity(item))
    return identifiers


def audit_site_layout(settings: CrawlSettings, records: list[dict[str, Any]]) -> dict[str, Any]:
    site_dirs = record_site_dirs(records, settings.site_dir)
    expected_paths = {site_dirs[record_key(record)] / "details.json" for record in records}
    actual_in_scope_paths: set[Path] = set()
    out_of_scope_paths: list[Path] = []
    for path in settings.site_dir.rglob("details.json"):
        payload = read_json(path)
        if is_topic_source(payload.get("source_url")):
            actual_in_scope_paths.add(path)
        else:
            out_of_scope_paths.append(path)
    missing_paths = expected_paths - actual_in_scope_paths
    misplaced_paths = actual_in_scope_paths - expected_paths
    return {
        "expected_topic_directories": len(expected_paths),
        "correctly_placed": len(expected_paths & actual_in_scope_paths),
        "missing_detail_paths": [str(path.relative_to(settings.site_dir)) for path in sorted(missing_paths)],
        "misplaced_detail_paths": [str(path.relative_to(settings.site_dir)) for path in sorted(misplaced_paths)],
        "out_of_scope_detail_paths": [str(path.relative_to(settings.site_dir)) for path in sorted(out_of_scope_paths)],
    }


def audit_assets(settings: CrawlSettings, records: list[dict[str, Any]]) -> dict[str, Any]:
    jobs = build_asset_jobs(records, settings)
    missing = [Path(job["target_path"]) for job in jobs if not Path(job["target_path"]).exists()]
    pdf_jobs = [job for job in jobs if Path(job["target_path"]).suffix.lower() == ".pdf"]
    missing_pdfs = [Path(job["target_path"]) for job in pdf_jobs if not Path(job["target_path"]).exists()]
    return {
        "expected": len(jobs),
        "present": len(jobs) - len(missing),
        "missing_paths": [str(path.relative_to(settings.site_dir)) for path in missing],
        "pdf_expected": len(pdf_jobs),
        "pdf_present": len(pdf_jobs) - len(missing_pdfs),
        "missing_pdf_paths": [str(path.relative_to(settings.site_dir)) for path in missing_pdfs],
    }


def find_out_of_scope_raw_paths(settings: CrawlSettings) -> list[Path]:
    paths: list[Path] = []
    for path in settings.raw_dir.rglob("*.json"):
        payload = read_json(path)
        source = payload.get("request", {}).get("url") or payload.get("source_api", {}).get("endpoint")
        if source and not is_allowed_raw_source(source):
            paths.append(path)
    return sorted(paths)


def find_legacy_asset_dirs(
    settings: CrawlSettings,
    in_scope_records: list[dict[str, Any]],
    out_of_scope_records: list[dict[str, Any]],
) -> dict[str, list[str]]:
    in_scope_paths = {path for record in in_scope_records for path in legacy_asset_candidates(settings, record)}
    out_of_scope_paths = {path for record in out_of_scope_records for path in legacy_asset_candidates(settings, record)}
    removable = sorted(path for path in out_of_scope_paths - in_scope_paths if path.exists())
    ambiguous = sorted(path for path in out_of_scope_paths & in_scope_paths if path.exists())
    return {
        "removable_paths": [str(path.relative_to(settings.assets_dir)) for path in removable],
        "ambiguous_paths": [str(path.relative_to(settings.assets_dir)) for path in ambiguous],
    }


def legacy_asset_candidates(settings: CrawlSettings, record: dict[str, Any]) -> set[Path]:
    title = topic_dir_name(record)
    categories = {category_dir_name(record), "未分类"}
    return {settings.assets_dir / category / title for category in categories}


def build_manifest(
    records: list[dict[str, Any]],
    site_paths: list[str],
    raw_paths: list[Path],
    legacy_asset_paths: list[str],
) -> dict[str, Any]:
    return {
        "out_of_scope_records": [
            {"id": record_identifier(record), "title": record.get("title"), "source_url": record.get("source_url")}
            for record in records
        ],
        "out_of_scope_site_detail_paths": site_paths,
        "out_of_scope_raw_paths": [str(path) for path in raw_paths],
        "out_of_scope_legacy_asset_paths": legacy_asset_paths,
    }


def audit_report_path(settings: CrawlSettings, snapshot_id: str) -> Path:
    return settings.reports_dir / f"scope_audit_{snapshot_id}.json"


def audit_manifest_path(settings: CrawlSettings, snapshot_id: str) -> Path:
    return settings.reports_dir / f"scope_audit_{snapshot_id}_out_of_scope.json"
