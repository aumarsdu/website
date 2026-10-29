from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
import json
import logging

from .config import Settings
from .storage import iter_jsonl, write_json
from .utils import safe_filename, utc_now

LOGGER = logging.getLogger(__name__)

PBL_PUBLIC_ORIGIN = "https://pbl.hirepglobal.com/"
PBL_PROJECT_PATH = "/Professor"
PBL_PROJECT_HOST = "pbl.hirepglobal.com"


async def audit_pbl_coverage(settings: Settings, known_project_paths: list[Path]) -> dict[str, Any]:
    """Compare the current public PBL list with all local PBL output batches."""
    from .pbl_crawler import _dedupe_pbl_records, _fetch_list, _history_project_paths, _known_business_ids, _records_from_response

    settings.ensure_dirs()
    project_paths = _history_project_paths(settings, known_project_paths)
    if settings.dry_run:
        payload = {
            "command": "audit-pbl",
            "dry_run": True,
            "scope_origin": PBL_PUBLIC_ORIGIN,
            "output_dir": str(settings.output_dir),
            "known_project_paths": [str(path) for path in project_paths],
            "known_business_ids": len(_known_business_ids(project_paths)),
            "rate_limit": settings.rate_limit,
            "retries": settings.retries,
            "user_agent": settings.user_agent,
            "will_persist": False,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    raw_response = await _fetch_list(settings, force_refresh=True)
    source_records = _records_from_response(raw_response)
    live_records, duplicate_list_records = _dedupe_pbl_records(source_records)
    report = build_pbl_coverage_report(settings, live_records, project_paths)
    report["audited_at"] = utc_now()
    report["public_list"].update(
        {
            "source_records": len(source_records),
            "unique_records": len(live_records),
            "duplicate_list_records": duplicate_list_records,
        }
    )
    write_json(settings.reports_dir / "pbl_coverage_audit.json", report)
    LOGGER.info(
        "PBL 覆盖审计完成: public=%s local=%s missing=%s layout_errors=%s scope_candidates=%s",
        report["public_list"]["unique_records"],
        report["local_records"]["unique_business_ids"],
        len(report["coverage"]["missing_business_ids"]),
        len(report["layout"]["error_outputs"]),
        len(report["scope_validation"]["deletion_candidates"]),
    )
    return report


def build_pbl_coverage_report(
    settings: Settings,
    live_records: list[dict[str, Any]],
    project_paths: list[Path],
) -> dict[str, Any]:
    """Build a deterministic local audit report without making network requests."""
    live_ids = sorted({_list_business_id(record) for record in live_records if _list_business_id(record)})
    live_without_business_id = sum(1 for record in live_records if not _list_business_id(record))

    local_business_ids: set[str] = set()
    local_scoped_records = 0
    local_records_without_business_id = 0
    missing_detail_payloads: list[dict[str, str]] = []
    output_checks: list[dict[str, Any]] = []
    error_outputs: list[str] = []
    out_of_scope_projects: list[dict[str, str]] = []
    out_of_scope_assets: list[dict[str, str]] = []
    asset_records_without_source_url = 0
    deletion_candidates: list[dict[str, str | int]] = []

    seen_paths: set[Path] = set()
    for project_path in project_paths:
        resolved_path = project_path.resolve()
        if resolved_path in seen_paths or not resolved_path.is_file():
            continue
        seen_paths.add(resolved_path)
        output_dir = resolved_path.parent.parent
        projects = [item for item in (iter_jsonl(resolved_path) or []) if isinstance(item, dict)]
        manifest_path = output_dir / "processed" / "asset_manifest.jsonl"
        manifest = [item for item in (iter_jsonl(manifest_path) or []) if isinstance(item, dict)]
        verification = verify_pbl_output(output_dir)
        scoped_projects: list[dict[str, Any]] = []
        invalid_projects: list[dict[str, Any]] = []
        for project in projects:
            if is_pbl_project_source_url(project.get("source_url")):
                scoped_projects.append(project)
            else:
                invalid_projects.append(project)

        output_checks.append(
            {
                "output_dir": str(output_dir),
                "project_records": len(projects),
                "scoped_project_records": len(scoped_projects),
                "verification": verification,
            }
        )
        if scoped_projects and not verification["valid"]:
            error_outputs.append(str(output_dir))

        for project in scoped_projects:
            local_scoped_records += 1
            business_id = str(project.get("business_id") or "").strip()
            if business_id:
                local_business_ids.add(business_id)
            else:
                local_records_without_business_id += 1
            if not _has_detail_payload(project):
                missing_detail_payloads.append(_project_reference(output_dir, project))

        invalid_references = [_project_reference(output_dir, project) for project in invalid_projects]
        out_of_scope_projects.extend(invalid_references)
        if invalid_projects and len(invalid_projects) == len(projects):
            deletion_candidates.append(
                {
                    "candidate_type": "output_directory",
                    "path": str(output_dir),
                    "reason": "all_project_records_outside_pbl_scope",
                    "project_records": len(projects),
                }
            )
        else:
            deletion_candidates.extend(
                {
                    "candidate_type": "project_directory",
                    "path": reference["project_dir"],
                    "reason": "project_source_url_outside_pbl_scope",
                    "business_id": reference["business_id"],
                }
                for reference in invalid_references
            )

        if scoped_projects:
            for item in manifest:
                source_url = str(item.get("source_url") or "").strip()
                if not source_url:
                    asset_records_without_source_url += 1
                    continue
                if settings.is_allowed_url(source_url, allow_assets=True):
                    continue
                reference = {
                    "output_dir": str(output_dir),
                    "source_url": source_url,
                    "file": str(_resolve_record_path(item.get("file"), output_dir) or ""),
                }
                out_of_scope_assets.append(reference)
                deletion_candidates.append(
                    {
                        "candidate_type": "asset_file",
                        "path": reference["file"],
                        "reason": "asset_source_url_outside_pbl_allowed_hosts",
                        "source_url": source_url,
                    }
                )

    live_id_set = set(live_ids)
    missing_business_ids = sorted(live_id_set - local_business_ids)
    historical_business_ids = sorted(local_business_ids - live_id_set)
    coverage_complete = not missing_business_ids and live_without_business_id == 0
    detail_complete = not missing_detail_payloads and local_records_without_business_id == 0
    layout_complete = not error_outputs
    scope_clean = not out_of_scope_projects and not out_of_scope_assets

    return {
        "scope": {
            "course_origin": PBL_PUBLIC_ORIGIN,
            "project_source_url": "https://pbl.hirepglobal.com/Professor?courseExtendId=...",
            "allowed_attachment_host_suffixes": sorted(settings.allowed_asset_host_suffixes),
            "approved_api_hosts": sorted(settings.allowed_hosts),
        },
        "public_list": {
            "unique_business_ids": len(live_ids),
            "records_without_business_id": live_without_business_id,
        },
        "local_records": {
            "project_files": [str(path) for path in sorted(seen_paths)],
            "scoped_project_records": local_scoped_records,
            "unique_business_ids": len(local_business_ids),
            "records_without_business_id": local_records_without_business_id,
            "historical_business_ids_not_in_current_list": historical_business_ids,
        },
        "coverage": {
            "complete": coverage_complete,
            "missing_business_ids": missing_business_ids,
        },
        "details": {
            "complete": detail_complete,
            "missing_detail_payloads": missing_detail_payloads,
        },
        "layout": {
            "complete": layout_complete,
            "outputs": output_checks,
            "error_outputs": error_outputs,
        },
        "scope_validation": {
            "clean": scope_clean,
            "out_of_scope_project_records": out_of_scope_projects,
            "out_of_scope_asset_records": out_of_scope_assets,
            "asset_records_without_source_url": asset_records_without_source_url,
            "deletion_candidates": _unique_candidates(deletion_candidates),
        },
        "valid": coverage_complete and detail_complete and layout_complete and scope_clean,
    }


def verify_pbl_output(output_dir: Path) -> dict[str, Any]:
    """Verify one PBL batch's details, directory hierarchy, and local asset files."""
    output_dir = output_dir.resolve()
    projects_path = output_dir / "processed" / "projects.jsonl"
    manifest_path = output_dir / "processed" / "asset_manifest.jsonl"
    if not projects_path.is_file():
        return _verification_result(output_dir, errors=["missing_projects_jsonl"], warnings=[], valid=False)
    if not manifest_path.is_file():
        return _verification_result(output_dir, errors=["missing_asset_manifest_jsonl"], warnings=[], valid=False)

    projects = [item for item in (iter_jsonl(projects_path) or []) if isinstance(item, dict)]
    manifest = [item for item in (iter_jsonl(manifest_path) or []) if isinstance(item, dict)]
    expected_dirs = _expected_project_dirs(output_dir, projects)
    project_dirs = [_resolve_record_path(project.get("project_dir"), output_dir) for project in projects]
    project_ids = [str(project.get("business_id") or "").strip() for project in projects]
    missing_project_dirs = sum(path is None or not path.is_dir() for path in project_dirs)
    missing_detail_files = sum(path is None or not (path / "详情页信息.json").is_file() for path in project_dirs)
    missing_detail_payloads = sum(not _has_detail_payload(project) for project in projects)
    misplaced_project_directories = sum(
        path is None or path.resolve() != expected.resolve()
        for path, expected in zip(project_dirs, expected_dirs, strict=True)
    )
    manifest_files = [_resolve_record_path(item.get("file"), output_dir) for item in manifest]
    missing_asset_files = sum(path is None or not path.is_file() for path in manifest_files)
    existing_project_dirs = {path.resolve() for path in project_dirs if path is not None and path.is_dir()}
    assets_outside_project_directories = sum(
        path is not None and path.is_file() and path.parent.resolve() not in existing_project_dirs
        for path in manifest_files
    )
    duplicate_business_ids = _duplicate_count(value for value in project_ids if value)
    duplicate_manifest_keys = _duplicate_count(
        str(item.get("manifest_key") or "") for item in manifest if item.get("manifest_key")
    )

    errors: list[str] = []
    warnings: list[str] = []
    if missing_project_dirs:
        errors.append("missing_project_directories")
    if missing_detail_files:
        errors.append("missing_project_detail_files")
    if missing_detail_payloads:
        errors.append("missing_project_detail_payloads")
    if misplaced_project_directories:
        errors.append("misplaced_project_directories")
    if missing_asset_files:
        errors.append("missing_manifest_asset_files")
    if assets_outside_project_directories:
        errors.append("assets_outside_project_directories")
    if duplicate_business_ids:
        warnings.append("duplicate_business_ids")
    if duplicate_manifest_keys:
        errors.append("duplicate_manifest_keys")
    return _verification_result(
        output_dir,
        projects=len(projects),
        unique_business_ids=len(set(value for value in project_ids if value)),
        duplicate_business_ids=duplicate_business_ids,
        project_directories=len({path for path in project_dirs if path is not None}),
        missing_project_directories=missing_project_dirs,
        misplaced_project_directories=misplaced_project_directories,
        detail_files=len(projects) - missing_detail_files,
        missing_detail_files=missing_detail_files,
        missing_detail_payloads=missing_detail_payloads,
        manifest_entries=len(manifest),
        duplicate_manifest_keys=duplicate_manifest_keys,
        missing_asset_files=missing_asset_files,
        assets_outside_project_directories=assets_outside_project_directories,
        errors=errors,
        warnings=warnings,
        valid=not errors,
    )


def is_pbl_project_source_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != PBL_PROJECT_HOST:
        return False
    if parsed.path.rstrip("/") != PBL_PROJECT_PATH:
        return False
    course_extend_id = parse_qs(parsed.query).get("courseExtendId", [""])[0]
    return bool(str(course_extend_id).strip())


def _expected_project_dirs(output_dir: Path, projects: list[dict[str, Any]]) -> list[Path]:
    base_dirs = [_base_project_folder(output_dir, project) for project in projects]
    counts = Counter(base_dirs)
    expected: list[Path] = []
    for project, folder in zip(projects, base_dirs, strict=True):
        if counts[folder] > 1:
            folder = folder.with_name(f"{folder.name}__{safe_filename(project.get('business_id'), fallback='id')}")
        expected.append(folder)
    return expected


def _base_project_folder(output_dir: Path, project: dict[str, Any]) -> Path:
    category = safe_filename(project.get("category"), fallback="未分类目录")
    direction = safe_filename(project.get("direction") or project.get("major_name"), fallback="未分类方向")
    title = safe_filename(project.get("title"), fallback=str(project.get("business_id") or "project"))
    return output_dir / "assets" / category / direction / title


def _has_detail_payload(project: dict[str, Any]) -> bool:
    raw = project.get("raw")
    return isinstance(raw, dict) and isinstance(raw.get("detail"), dict)


def _project_reference(output_dir: Path, project: dict[str, Any]) -> dict[str, str]:
    project_dir = _resolve_record_path(project.get("project_dir"), output_dir)
    return {
        "output_dir": str(output_dir),
        "business_id": str(project.get("business_id") or ""),
        "source_url": str(project.get("source_url") or ""),
        "project_dir": str(project_dir or ""),
    }


def _list_business_id(record: dict[str, Any]) -> str:
    return str(record.get("courseExtendId") or record.get("courseId") or "").strip()


def _resolve_record_path(value: Any, output_dir: Path) -> Path | None:
    if not value:
        return None
    raw = Path(str(value))
    candidates = [raw] if raw.is_absolute() else [Path.cwd() / raw, output_dir.parent / raw, output_dir / raw]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _duplicate_count(values: Any) -> int:
    counts = Counter(values)
    return sum(count - 1 for count in counts.values() if count > 1)


def _unique_candidates(candidates: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    unique: dict[tuple[str, str, str], dict[str, str | int]] = {}
    for candidate in candidates:
        key = (
            str(candidate.get("candidate_type") or ""),
            str(candidate.get("path") or ""),
            str(candidate.get("reason") or ""),
        )
        unique.setdefault(key, candidate)
    return list(unique.values())


def _verification_result(output_dir: Path, *, errors: list[str], warnings: list[str], valid: bool, **values: Any) -> dict[str, Any]:
    return {"output_dir": str(output_dir), **values, "errors": errors, "warnings": warnings, "valid": valid}
