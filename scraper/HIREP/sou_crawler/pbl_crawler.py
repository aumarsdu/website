from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
from typing import Any
import asyncio
import json
import logging
import os
import sys

from .config import Settings
from .fetcher import CrawlStopped, HttpFetcher
from .schema import CrawlStats
from .storage import append_jsonl, iter_jsonl, read_json, write_csv, write_json, write_jsonl, write_sqlite
from .utils import canonicalize_url, file_extension_from_url, find_asset_urls, safe_filename, stable_hash, utc_now

LOGGER = logging.getLogger(__name__)

API_BASE = "https://edu4-crm-api.neoschool.com"
PBL_REFERER = "https://pbl.hirepglobal.com/"
LIST_ENDPOINT = f"{API_BASE}/sdm/mtc/pubController/aisCisPage"
MAJOR_ENDPOINT = f"{API_BASE}/sdm/mtc/pubController/getMajorList"
START_DATE_ENDPOINT = f"{API_BASE}/sdm/cmt/eduProductPackage/listH5ProductCourseStartDateOption"
ATTACHMENT_ENDPOINT = f"{API_BASE}/bus/ath/resAttachment/noToken/getResAttachment"
DETAIL_ENDPOINT = f"{API_BASE}/sdm/mtc/pubController/get"
MAJOR_ATTACHMENT_ENDPOINT = f"{API_BASE}/sdm/mtc/pubController/getMajorAttachment"
PUBLIC_ATTACHMENT_ENDPOINT = f"{API_BASE}/sdm/mtc/pubController/getPublicAttachment"


@dataclass(frozen=True)
class AssetRef:
    record_id: str
    title: str
    category: str
    professor: str
    field: str
    attachment_id: str


from .pbl_normalize import (  # noqa: F401 - re-exported for compatibility
    _decorate_record,
    _dedupe_pbl_records,
    _known_business_ids,
    _new_projects,
    _normalize_projects,
    _pbl_record_score,
    _records_from_response,
    _split_keywords,
)


async def _finalize_projects(
    settings: Settings,
    *,
    list_items: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    duplicate_records: int,
) -> list[dict[str, Any]]:
    """Shared post-list pipeline: details, directories, exports, assets, reports."""
    write_jsonl(settings.raw_dir / "list_items.jsonl", list_items)
    await _fetch_details(settings, projects)
    projects = _merge_project_details(settings, projects)
    projects = _with_project_directories(settings, projects)
    _write_project_detail_files(settings, projects)
    write_jsonl(settings.processed_dir / "projects.jsonl", projects)
    write_csv(settings.processed_dir / "projects.csv", projects)
    write_sqlite(settings.processed_dir / "projects.sqlite", projects)

    refs = _asset_refs(projects)
    await _fetch_attachment_metadata(settings, refs)
    manifest = await _download_pbl_assets(settings, projects)
    _write_quality(settings, source_records, projects, refs, manifest, duplicate_list_records=duplicate_records)
    _write_summary(settings, projects, manifest)
    return manifest


async def crawl_pbl(settings: Settings) -> None:
    settings.ensure_dirs()
    if settings.dry_run:
        _print_dry_run(settings)
        return

    raw_response = await _fetch_list(settings)
    source_records = _records_from_response(raw_response)
    records, duplicate_records = _dedupe_pbl_records(source_records)
    major_map = await _fetch_metadata(settings)
    projects = _normalize_projects(records, major_map)

    manifest = await _finalize_projects(
        settings,
        list_items=[_decorate_record(item) for item in records],
        projects=projects,
        source_records=source_records,
        duplicate_records=duplicate_records,
    )
    LOGGER.info(
        "PBL 主站抓取完成: source_records=%s unique_projects=%s duplicate_list_records=%s assets=%s",
        len(source_records),
        len(projects),
        duplicate_records,
        len(manifest),
    )


async def crawl_pbl_incremental(settings: Settings, known_project_paths: list[Path]) -> None:
    """Fetch only PBL projects absent from the supplied historical outputs."""
    settings.ensure_dirs()
    baseline_paths = _history_project_paths(settings, known_project_paths)
    history_paths = [*baseline_paths, settings.processed_dir / "projects.jsonl"]
    known_business_ids = _known_business_ids(history_paths)
    if settings.dry_run:
        _print_dry_run(
            settings,
            command="crawl-pbl-incremental",
            known_project_paths=baseline_paths,
            known_business_ids=len(known_business_ids),
        )
        return

    if not known_business_ids:
        raise ValueError(
            "增量抓取需要至少一个包含历史 business_id 的 projects.jsonl。"
            "首次采集请使用 crawl-pbl；也可通过 --known-projects 显式指定历史输出。"
        )
    raw_response = await _fetch_list(settings, force_refresh=True)
    source_records = _records_from_response(raw_response)
    records, duplicate_records = _dedupe_pbl_records(source_records)
    major_map = await _fetch_metadata(settings)
    all_projects = _normalize_projects(records, major_map)
    projects = _new_projects(all_projects, known_business_ids)

    manifest = await _finalize_projects(
        settings,
        list_items=[_decorate_record(item.get("raw") or {}) for item in projects],
        projects=projects,
        source_records=source_records,
        duplicate_records=duplicate_records,
    )
    write_json(
        settings.reports_dir / "incremental_summary.json",
        {
            "website_list_records": len(source_records),
            "website_projects": len(all_projects),
            "website_duplicate_list_records": duplicate_records,
            "known_business_ids": len(known_business_ids),
            "new_projects": len(projects),
            "known_project_files": [str(path) for path in baseline_paths if path.exists()],
            "resume_projects_file": str(settings.processed_dir / "projects.jsonl"),
            "projects_file": str(settings.processed_dir / "projects.jsonl"),
        },
    )
    LOGGER.info(
        "PBL 增量抓取完成: website_projects=%s duplicate_list_records=%s known_business_ids=%s new_projects=%s assets=%s",
        len(all_projects),
        duplicate_records,
        len(known_business_ids),
        len(projects),
        len(manifest),
    )


_LIST_PAGE_SIZE = 200
_MAX_LIST_PAGES = 100


async def _fetch_list(settings: Settings, *, force_refresh: bool = False) -> dict[str, Any]:
    stats = CrawlStats(started_at=utc_now(), target_domain="pbl_list")
    raw_path = settings.raw_dir / "pbl_ais_cis_page.json"
    if raw_path.exists() and not force_refresh:
        data = read_json(raw_path, {})
        if data:
            return data

    headers = _api_headers("application/json")
    async with HttpFetcher(settings) as fetcher:
        try:
            merged_records: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            page_response: dict[str, Any] | None = None
            current_page, total_pages = 1, 1
            while current_page <= total_pages and current_page <= _MAX_LIST_PAGES:
                stats.pages_requested += 1
                data = await fetcher.request_json(
                    "POST",
                    LIST_ENDPOINT,
                    json={"pageSize": _LIST_PAGE_SIZE, "current": current_page},
                    headers=headers,
                )
                stats.pages_succeeded += 1
                course_list = data.get("data", {}).get("courseList", {}) if isinstance(data, dict) else {}
                records = course_list.get("records", []) if isinstance(course_list, dict) else []
                if not isinstance(records, list):
                    records = []
                page_ids = [
                    str(item.get("courseExtendId") or item.get("courseId") or "")
                    for item in records
                    if isinstance(item, dict)
                ]
                if current_page > 1 and page_ids and all(pid in seen_ids for pid in page_ids):
                    # Server ignored the `current` parameter: stop before merging duplicates.
                    LOGGER.warning("PBL 列表接口未按页推进，提前结束分页（第 %s 页）", current_page)
                    break
                seen_ids.update(pid for pid in page_ids if pid)
                merged_records.extend(item for item in records if isinstance(item, dict))
                try:
                    total_pages = int(str(course_list.get("pages") if isinstance(course_list, dict) else "1") or 1)
                except ValueError:
                    total_pages = 1
                if page_response is None:
                    page_response = data
                current_page += 1
            if page_response is None:
                raise RuntimeError("PBL list endpoint returned no response")
            course_list = page_response.get("data", {}).get("courseList")
            if isinstance(course_list, dict):
                course_list["records"] = merged_records
                course_list["size"] = str(len(merged_records))
            stats.records_extracted = len(merged_records)
            write_json(raw_path, page_response)
            return page_response
        except CrawlStopped:
            stats.pages_failed += 1
            stats.add_error("http_401_or_403_access_control")
            raise
        finally:
            write_json(settings.reports_dir / "pbl_list_stats.json", stats.as_dict())


async def _fetch_metadata(settings: Settings) -> dict[str, dict[str, str]]:
    meta_dir = settings.raw_dir / "pbl_metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    stats = CrawlStats(started_at=utc_now(), target_domain="pbl_metadata")
    endpoints = [
        ("major_list", MAJOR_ENDPOINT, {}),
        ("start_date_options", START_DATE_ENDPOINT, {}),
    ]
    async with HttpFetcher(settings) as fetcher:
        for name, url, payload in endpoints:
            path = meta_dir / f"{name}.json"
            if path.exists():
                continue
            try:
                stats.pages_requested += 1
                data = await fetcher.request_json("POST", url, json=payload, headers=_api_headers("application/json"))
                stats.pages_succeeded += 1
                write_json(path, data)
            except Exception as exc:  # noqa: BLE001 - optional metadata should not stop list extraction.
                LOGGER.warning("PBL 元数据接口失败: %s %s", name, exc)
                stats.pages_failed += 1
                stats.add_error(_classify_error(exc))
    write_json(settings.reports_dir / "pbl_metadata_stats.json", stats.as_dict())
    return _load_major_map(meta_dir / "major_list.json")


async def _fetch_details(settings: Settings, projects: list[dict[str, Any]]) -> None:
    stats = CrawlStats(started_at=utc_now(), target_domain="pbl_details")
    details_path = settings.raw_dir / "pbl_details.jsonl"
    major_path = settings.raw_dir / "pbl_major_attachments.jsonl"
    public_path = settings.raw_dir / "pbl_public_attachments.jsonl"
    failure_path = settings.raw_dir / "pbl_detail_failures.jsonl"
    done_details = {str(item.get("business_id")) for item in (iter_jsonl(details_path) or []) if item.get("business_id")}
    existing_major_rows = list(iter_jsonl(major_path) or [])
    done_major = {str(item.get("business_id")) for item in existing_major_rows if item.get("business_id")}
    done_public_codes = {str(item.get("attachment_code")) for item in (iter_jsonl(public_path) or []) if item.get("attachment_code")}
    project_by_id = {str(project.get("business_id") or ""): project for project in projects}
    major_cache: dict[str, Any] = {}
    for item in existing_major_rows:
        project = project_by_id.get(str(item.get("business_id") or ""))
        cache_key = _major_cache_key(project or {})
        if cache_key and item.get("data"):
            major_cache.setdefault(cache_key, item["data"])

    async with HttpFetcher(settings) as fetcher:
        for idx, project in enumerate(projects, 1):
            business_id = str(project.get("business_id") or "")
            params = _project_query(project)
            if business_id and business_id not in done_details:
                try:
                    stats.pages_requested += 1
                    data = await fetcher.request_json(
                        "POST",
                        DETAIL_ENDPOINT,
                        data={**params, "type": 1},
                        headers=_api_headers("application/x-www-form-urlencoded"),
                    )
                    stats.pages_succeeded += 1
                    stats.records_extracted += 1
                    append_jsonl(details_path, {"business_id": business_id, "request": params, "data": data, "crawled_at": utc_now()})
                except CrawlStopped:
                    stats.pages_failed += 1
                    stats.add_error("http_401_or_403_access_control")
                    raise
                except Exception as exc:  # noqa: BLE001
                    stats.pages_failed += 1
                    stats.add_error(_classify_error(exc))
                    append_jsonl(failure_path, {"target": "detail", "business_id": business_id, "error": str(exc), "crawled_at": utc_now()})
            if business_id and business_id not in done_major:
                cache_key = _major_cache_key(project)
                if cache_key in major_cache:
                    append_jsonl(
                        major_path,
                        {
                            "business_id": business_id,
                            "request": params,
                            "data": major_cache[cache_key],
                            "cache_key": cache_key,
                            "cached": True,
                            "crawled_at": utc_now(),
                        },
                    )
                    done_major.add(business_id)
                    if idx % 100 == 0:
                        LOGGER.info("PBL 详情进度: %s/%s", idx, len(projects))
                    continue
                try:
                    stats.pages_requested += 1
                    data = await fetcher.request_json(
                        "POST",
                        MAJOR_ATTACHMENT_ENDPOINT,
                        data=params,
                        headers=_api_headers("application/x-www-form-urlencoded"),
                    )
                    stats.pages_succeeded += 1
                    if cache_key:
                        major_cache.setdefault(cache_key, data)
                    append_jsonl(major_path, {"business_id": business_id, "request": params, "data": data, "crawled_at": utc_now()})
                except Exception as exc:  # noqa: BLE001
                    stats.pages_failed += 1
                    stats.add_error(_classify_error(exc))
                    append_jsonl(failure_path, {"target": "major_attachment", "business_id": business_id, "error": str(exc), "crawled_at": utc_now()})
            if idx % 100 == 0:
                LOGGER.info("PBL 详情进度: %s/%s", idx, len(projects))

        for code in sorted({_public_attachment_code(project) for project in projects} - done_public_codes):
            try:
                stats.pages_requested += 1
                data = await fetcher.request_json(
                    "POST",
                    PUBLIC_ATTACHMENT_ENDPOINT,
                    data={"attachmentCode": code},
                    headers=_api_headers("application/x-www-form-urlencoded"),
                )
                stats.pages_succeeded += 1
                append_jsonl(public_path, {"attachment_code": code, "data": data, "crawled_at": utc_now()})
            except Exception as exc:  # noqa: BLE001
                stats.pages_failed += 1
                stats.add_error(_classify_error(exc))
                append_jsonl(failure_path, {"target": "public_attachment", "attachment_code": code, "error": str(exc), "crawled_at": utc_now()})

    write_json(settings.reports_dir / "pbl_details_stats.json", stats.as_dict())


async def _fetch_attachment_metadata(settings: Settings, refs: list[AssetRef]) -> None:
    stats = CrawlStats(started_at=utc_now(), target_domain="pbl_attachment_metadata")
    metadata_path = settings.raw_dir / "pbl_attachment_metadata.jsonl"
    failed_path = settings.raw_dir / "pbl_attachment_failures.jsonl"
    done_ids = {
        str(item.get("attachment_id"))
        for item in (iter_jsonl(metadata_path) or [])
        if item.get("attachment_id")
    }
    failed_ids = {
        str(item.get("attachment_id"))
        for item in (iter_jsonl(failed_path) or [])
        if item.get("attachment_id")
    }
    unique_ids = []
    seen: set[str] = set()
    for ref in refs:
        if ref.attachment_id in seen:
            continue
        seen.add(ref.attachment_id)
        if ref.attachment_id in done_ids or ref.attachment_id in failed_ids:
            continue
        unique_ids.append(ref.attachment_id)

    async with HttpFetcher(settings) as fetcher:
        for idx, attachment_id in enumerate(unique_ids, 1):
            try:
                stats.pages_requested += 1
                data = await fetcher.request_json(
                    "POST",
                    ATTACHMENT_ENDPOINT,
                    params={"id": attachment_id},
                    headers=_api_headers("application/json"),
                )
                stats.pages_succeeded += 1
                append_jsonl(metadata_path, {"attachment_id": attachment_id, "data": data, "crawled_at": utc_now()})
                if idx % 100 == 0:
                    LOGGER.info("PBL 附件元数据进度: %s/%s", idx, len(unique_ids))
            except CrawlStopped:
                stats.pages_failed += 1
                stats.add_error("http_401_or_403_access_control")
                raise
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("PBL 附件元数据失败: id=%s err=%s", attachment_id, exc)
                stats.pages_failed += 1
                stats.add_error(_classify_error(exc))
                append_jsonl(failed_path, {"attachment_id": attachment_id, "error": str(exc), "crawled_at": utc_now()})
    write_json(settings.reports_dir / "pbl_attachment_metadata_stats.json", stats.as_dict())


def _manifest_item(
    manifest_key: str,
    project: dict[str, Any],
    asset: dict[str, Any],
    url: str,
    target: Path,
    headers: dict[str, str],
    attachment_id: str | None = None,
) -> dict[str, Any]:
    return {
        "manifest_key": manifest_key,
        "record_title": project.get("title"),
        "category": project.get("category"),
        "direction": project.get("direction") or project.get("major_name"),
        "project_dir": project.get("project_dir") or str(target.parent),
        "field": asset.get("field"),
        "attachment_id": attachment_id,
        "source_url": url,
        "file": str(target),
        "bytes": target.stat().st_size,
        "content_type": headers.get("content-type"),
    }


async def _download_asset_once(
    fetcher: HttpFetcher,
    *,
    stats: CrawlStats,
    manifest_path: Path,
    manifest: list[dict[str, Any]],
    done_keys: set[str],
    manifest_key: str,
    existing_item: dict[str, Any] | None,
    project_folder: Path,
    target: Path,
    cache_path: Path,
    url: str,
    build_item: Callable[[dict[str, str]], dict[str, Any]],
    label: str,
) -> bool:
    """Download or cache-restore one asset and append its manifest row.

    Returns True when no network request was needed (already current on disk or
    restored from the manifest). CrawlStopped propagates; other failures are
    recorded in stats and swallowed so one bad asset cannot abort the batch.
    """
    if manifest_key in done_keys and _manifest_file_is_current(existing_item, project_folder):
        return True
    if manifest_key in done_keys and _restore_manifest_file(existing_item, target):
        stats.pages_succeeded += 1
        item = build_item({})
        append_jsonl(manifest_path, item)
        manifest.append(item)
        return True
    try:
        stats.pages_requested += 1
        if not cache_path.exists():
            content, headers = await fetcher.request_bytes("GET", url, allow_assets=True)
            cache_path.write_bytes(content)
        else:
            headers = {}
        target.parent.mkdir(parents=True, exist_ok=True)
        _link_or_copy(cache_path, target)
        stats.pages_succeeded += 1
        item = build_item(headers)
        append_jsonl(manifest_path, item)
        manifest.append(item)
        done_keys.add(manifest_key)
        if stats.pages_succeeded % 100 == 0:
            LOGGER.info("%s 进度: %s", label, stats.pages_succeeded)
    except CrawlStopped:
        stats.pages_failed += 1
        stats.add_error("http_401_or_403_access_control")
        raise
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("%s 失败: %s %s", label, url, exc)
        stats.pages_failed += 1
        stats.add_error(_classify_error(exc))
    return False


async def _download_pbl_assets(settings: Settings, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats = CrawlStats(started_at=utc_now(), target_domain="pbl_assets")
    metadata = _load_attachment_metadata(settings.raw_dir / "pbl_attachment_metadata.jsonl")
    manifest_path = settings.processed_dir / "asset_manifest.jsonl"
    existing = list(iter_jsonl(manifest_path) or [])
    done_keys = {str(item.get("manifest_key")) for item in existing if item.get("manifest_key")}
    existing_by_key = {str(item.get("manifest_key")): item for item in existing if item.get("manifest_key")}
    cache_dir = settings.assets_dir / "_download_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = list(existing)

    async with HttpFetcher(settings) as fetcher:
        for project in projects:
            project_folder = _project_folder(settings, project)
            for asset in project.get("assets", []):
                asset_id = str(asset.get("attachment_id") or "")
                meta = metadata.get(asset_id)
                if not meta:
                    continue
                url = meta.get("url")
                if not url:
                    continue
                manifest_key = f"{project['business_id']}::{asset_id}::{asset.get('field')}"
                await _download_asset_once(
                    fetcher,
                    stats=stats,
                    manifest_path=manifest_path,
                    manifest=manifest,
                    done_keys=done_keys,
                    manifest_key=manifest_key,
                    existing_item=existing_by_key.get(manifest_key),
                    project_folder=project_folder,
                    target=_asset_target_path(settings, project, asset, meta, url),
                    cache_path=cache_dir / f"{asset_id}{file_extension_from_url(url, '.' + (meta.get('ext') or 'bin'))}",
                    url=url,
                    build_item=lambda headers, _p=project, _a=asset, _u=url, _t=_asset_target_path(settings, project, asset, meta, url), _k=manifest_key, _i=asset_id: _manifest_item(
                        _k, _p, _a, _u, _t, headers, attachment_id=_i
                    ),
                    label="PBL 附件下载",
                )
            for asset in project.get("direct_assets", []):
                url = asset.get("url")
                if not url:
                    continue
                manifest_key = f"{project['business_id']}::direct::{stable_hash(url)}::{asset.get('field')}"
                await _download_asset_once(
                    fetcher,
                    stats=stats,
                    manifest_path=manifest_path,
                    manifest=manifest,
                    done_keys=done_keys,
                    manifest_key=manifest_key,
                    existing_item=existing_by_key.get(manifest_key),
                    project_folder=project_folder,
                    target=_direct_asset_target_path(settings, project, asset, url),
                    cache_path=cache_dir / f"{stable_hash(url)}{file_extension_from_url(url)}",
                    url=url,
                    build_item=lambda headers, _p=project, _a=asset, _u=url, _t=_direct_asset_target_path(settings, project, asset, url), _k=manifest_key: _manifest_item(
                        _k, _p, _a, _u, _t, headers
                    ),
                    label="PBL 直接附件下载",
                )
    write_json(settings.processed_dir / "asset_manifest.json", manifest)
    write_json(settings.reports_dir / "download_assets_stats.json", stats.as_dict())
    return manifest


def _history_project_paths(settings: Settings, supplied_paths: list[Path]) -> list[Path]:
    """Combine explicit history with local PBL outputs, excluding the active output."""
    current_projects = (settings.processed_dir / "projects.jsonl").resolve()
    output_root = settings.output_dir.resolve().parent
    auto_paths = sorted(output_root.glob("output_pbl*/processed/projects.jsonl"))
    paths: list[Path] = []
    seen_paths: set[Path] = set()
    for path in [*supplied_paths, *auto_paths]:
        resolved = path.resolve()
        if resolved == current_projects or resolved in seen_paths or not resolved.is_file():
            continue
        seen_paths.add(resolved)
        paths.append(resolved)
    return paths








def _asset_refs(projects: list[dict[str, Any]]) -> list[AssetRef]:
    refs: list[AssetRef] = []
    for project in projects:
        for asset in project.get("assets", []):
            refs.append(
                AssetRef(
                    record_id=str(project.get("business_id") or ""),
                    title=str(project.get("title") or project.get("business_id") or "project"),
                    category=str(project.get("category") or "uncategorized"),
                    professor=str(project.get("professor") or project.get("title") or "professor"),
                    field=str(asset.get("field") or "asset"),
                    attachment_id=str(asset.get("attachment_id") or ""),
                )
            )
    return [ref for ref in refs if ref.attachment_id]


def _with_project_directories(settings: Settings, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[Path, int] = {}
    for project in projects:
        folder = _base_project_folder(settings, project)
        counts[folder] = counts.get(folder, 0) + 1
    out: list[dict[str, Any]] = []
    for project in projects:
        item = {**project}
        folder = _base_project_folder(settings, item)
        if counts.get(folder, 0) > 1:
            folder = folder.with_name(f"{folder.name}__{safe_filename(item.get('business_id'), fallback='id')}")
        item["project_dir"] = str(folder)
        out.append(item)
    return out


def _write_project_detail_files(settings: Settings, projects: list[dict[str, Any]]) -> None:
    for project in projects:
        folder = _project_folder(settings, project)
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / "详情页信息.json", project)


def _merge_project_details(settings: Settings, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details = _load_by_business_id(settings.raw_dir / "pbl_details.jsonl")
    major_attachments = _load_by_business_id(settings.raw_dir / "pbl_major_attachments.jsonl")
    public_attachments = {
        str(item.get("attachment_code")): _response_data(item.get("data"))
        for item in (iter_jsonl(settings.raw_dir / "pbl_public_attachments.jsonl") or [])
    }
    merged: list[dict[str, Any]] = []
    for project in projects:
        business_id = str(project.get("business_id") or "")
        detail = _response_data((details.get(business_id) or {}).get("data"))
        majors = _response_data((major_attachments.get(business_id) or {}).get("data")) or []
        public = public_attachments.get(_public_attachment_code(project)) or []
        if isinstance(detail, dict):
            project = {**project}
            project["title"] = str(detail.get("courseNameCn") or detail.get("courseExtendNameCn") or project.get("title"))
            project["title_en"] = detail.get("courseNameEn") or project.get("title_en")
            project["professor"] = detail.get("professorName") or project.get("professor")
            project["professor_position"] = detail.get("professorPosition") or project.get("professor_position")
            project["university"] = detail.get("collegeName") or detail.get("researchTakeOfficeSchool") or project.get("university")
            project["description"] = detail.get("courseDescribeCn") or detail.get("professorIntroduceCn") or project.get("description")
            project["course_difficulty"] = detail.get("courseDifficulty") or project.get("course_difficulty")
            project["teaching_mode"] = detail.get("teachingMode") or project.get("teaching_mode")
            project["raw"] = {"list": project.get("raw"), "detail": detail}
        direct_assets = _direct_assets(project, detail, majors, public)
        project["direct_assets"] = direct_assets
        project["asset_urls"] = sorted({asset["url"] for asset in direct_assets if asset.get("url")})
        project["major_attachments"] = majors if isinstance(majors, list) else []
        project["public_attachments"] = public if isinstance(public, list) else []
        merged.append(project)
    return merged


def _load_attachment_metadata(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in iter_jsonl(path) or []:
        attachment_id = str(item.get("attachment_id") or "")
        data = item.get("data", {})
        payload = data.get("data") if isinstance(data, dict) else None
        if attachment_id and isinstance(payload, dict):
            out[attachment_id] = payload
    return out


def _load_by_business_id(path: Path) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("business_id")): item
        for item in (iter_jsonl(path) or [])
        if item.get("business_id")
    }


def _response_data(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("data")
    return None


def _project_query(project: dict[str, Any]) -> dict[str, Any]:
    raw = project.get("raw") or {}
    return {
        "courseExtendId": raw.get("courseExtendId") or project.get("business_id"),
        "productPackageId": raw.get("productPackageId"),
        "h5Type": raw.get("h5Type") or 1,
    }


def _public_attachment_code(project: dict[str, Any]) -> str:
    raw = project.get("raw") or {}
    try:
        h5_type = int(raw.get("h5Type") or 1)
    except (TypeError, ValueError):
        h5_type = 1
    return "PA00003" if h5_type == 3 else "PA00001"


def _major_cache_key(project: dict[str, Any]) -> str:
    direction = str(project.get("direction") or "").strip()
    if direction:
        return f"direction:{direction}"
    major_name = str(project.get("major_name") or "").strip()
    if major_name:
        return f"major:{major_name}"
    return ""


def _direct_assets(project: dict[str, Any], detail: Any, majors: Any, public: Any) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(url: Any, field: str, filename: Any = None) -> None:
        if not isinstance(url, str) or not url.startswith("http") or url in seen:
            return
        seen.add(url)
        assets.append({"url": url, "field": field, "file_name": str(filename or "")})

    if isinstance(detail, dict):
        add(detail.get("professorAvatar"), "professorAvatar", project.get("professor"))
        for url in find_asset_urls(detail):
            add(url, "detailAsset")
    for item in majors if isinstance(majors, list) else []:
        if isinstance(item, dict):
            add(item.get("url"), "majorAttachment", item.get("fileName"))
    for item in public if isinstance(public, list) else []:
        if isinstance(item, dict):
            add(item.get("url"), "publicAttachment", item.get("fileName"))
    return assets


def _load_major_map(path: Path) -> dict[str, dict[str, str]]:
    data = read_json(path, {})
    result: dict[str, dict[str, str]] = {}
    for parent in data.get("data", []) if isinstance(data, dict) else []:
        parent_id = str(parent.get("majors") or "")
        parent_name = str(parent.get("majorsName") or "")
        if parent_id:
            result[parent_id] = {"name": parent_name, "parent_id": parent_id, "parent_name": parent_name}
        for child in parent.get("majorsMinList") or []:
            child_id = str(child.get("majors") or "")
            if child_id:
                result[child_id] = {
                    "name": str(child.get("majorsName") or ""),
                    "parent_id": parent_id,
                    "parent_name": parent_name,
                }
    return result




def _project_folder(settings: Settings, project: dict[str, Any]) -> Path:
    if project.get("project_dir"):
        return Path(str(project["project_dir"]))
    return _base_project_folder(settings, project)


def _base_project_folder(settings: Settings, project: dict[str, Any]) -> Path:
    category = safe_filename(project.get("category"), fallback="未分类目录")
    direction = safe_filename(project.get("direction") or project.get("major_name"), fallback="未分类方向")
    title = safe_filename(project.get("title"), fallback=str(project.get("business_id") or "project"))
    return settings.assets_dir / category / direction / title


def _asset_target_path(settings: Settings, project: dict[str, Any], asset: dict[str, Any], meta: dict[str, Any], url: str) -> Path:
    ext = file_extension_from_url(url, "." + str(meta.get("ext") or "bin").strip("."))
    title = safe_filename(project.get("title"), fallback=str(project.get("business_id") or "project"))
    professor = safe_filename(project.get("professor"), fallback="professor")
    field = asset.get("field")
    if field in {"attachmentId", "industryPoster"}:
        base = "海报"
    elif field == "courseBanner":
        base = "Banner"
    elif field == "thumbnailId":
        base = "缩略图"
    elif field and "professor" in str(field).lower():
        base = professor
    else:
        base = f"{title}-{field or 'asset'}"
    return _unique_path(_project_folder(settings, project) / f"{base}{ext}")


def _direct_asset_target_path(settings: Settings, project: dict[str, Any], asset: dict[str, Any], url: str) -> Path:
    title = safe_filename(project.get("title"), fallback=str(project.get("business_id") or "project"))
    professor = safe_filename(project.get("professor"), fallback="professor")
    ext = file_extension_from_url(url)
    field = asset.get("field")
    if field == "professorAvatar":
        base = professor
    elif field in {"majorAttachment", "publicAttachment"} and asset.get("file_name"):
        base = _filename_stem(asset.get("file_name"), fallback=str(field))
    else:
        base = f"{title}-{field or 'asset'}"
    return _unique_path(_project_folder(settings, project) / f"{base}{ext}")


def _filename_stem(value: Any, *, fallback: str) -> str:
    name = safe_filename(value, fallback=fallback)
    suffix = Path(name).suffix.lower()
    if suffix in {".pdf", ".jpg", ".jpeg", ".png", ".webp"}:
        return Path(name).stem or fallback
    return name


def _restore_manifest_file(item: dict[str, Any] | None, target: Path) -> bool:
    if not item:
        return False
    source_value = item.get("file")
    if not source_value:
        return False
    source = Path(str(source_value))
    if not source.exists() or source.resolve() == target.resolve():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    _link_or_copy(source, target)
    return target.exists()


def _manifest_file_is_current(item: dict[str, Any] | None, project_folder: Path) -> bool:
    if not item or not item.get("file"):
        return False
    path = Path(str(item["file"]))
    return path.exists() and path.parent.resolve() == project_folder.resolve()


def _link_or_copy(source: Path, target: Path) -> None:
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        target.write_bytes(source.read_bytes())


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for idx in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{idx}{path.suffix}")
        if not candidate.exists():
            return candidate
    return path


def _api_headers(content_type: str) -> dict[str, str]:
    return {
        "Content-Type": content_type,
        "Origin": "https://pbl.hirepglobal.com",
        "Referer": PBL_REFERER,
    }


def _write_quality(
    settings: Settings,
    raw_records: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    refs: list[AssetRef],
    manifest: list[dict[str, Any]],
    *,
    duplicate_list_records: int = 0,
) -> None:
    write_json(
        settings.processed_dir / "data_quality_summary.json",
        {
            "raw_records": len(raw_records),
            "duplicate_list_records": duplicate_list_records,
            "unique_list_records": len(raw_records) - duplicate_list_records,
            "normalized_records": len(projects),
            "unique_business_ids": len({item.get("business_id") for item in projects}),
            "records_with_assets": sum(1 for item in projects if item.get("assets")),
            "asset_references": len(refs),
            "unique_attachment_ids": len({ref.attachment_id for ref in refs}),
            "direct_asset_references": sum(len(item.get("direct_assets", [])) for item in projects),
            "unique_direct_asset_urls": len(
                {
                    asset.get("url")
                    for item in projects
                    for asset in item.get("direct_assets", [])
                    if asset.get("url")
                }
            ),
            "downloaded_asset_entries": len(manifest),
            "downloaded_asset_unique_keys": len({item.get("manifest_key") for item in manifest}),
            "categories": _count_by(projects, "category"),
        },
    )


def _write_summary(settings: Settings, projects: list[dict[str, Any]], manifest: list[dict[str, Any]]) -> None:
    summary = {
        "list_items": len(projects),
        "normalized_projects": len(projects),
        "downloaded_assets": len(manifest),
        "data_quality": read_json(settings.processed_dir / "data_quality_summary.json", {}),
        "file_counts": {
            "list_items": _count_jsonl(settings.raw_dir / "list_items.jsonl"),
            "details": _count_jsonl(settings.raw_dir / "pbl_details.jsonl"),
            "major_attachments": _count_jsonl(settings.raw_dir / "pbl_major_attachments.jsonl"),
            "public_attachments": _count_jsonl(settings.raw_dir / "pbl_public_attachments.jsonl"),
            "attachment_metadata": _count_jsonl(settings.raw_dir / "pbl_attachment_metadata.jsonl"),
            "attachment_failures": _count_jsonl(settings.raw_dir / "pbl_attachment_failures.jsonl"),
            "detail_failures": _count_jsonl(settings.raw_dir / "pbl_detail_failures.jsonl"),
            "asset_manifest": _count_jsonl(settings.processed_dir / "asset_manifest.jsonl"),
        },
        "pbl_list_stats": read_json(settings.reports_dir / "pbl_list_stats.json", {}),
        "pbl_metadata_stats": read_json(settings.reports_dir / "pbl_metadata_stats.json", {}),
        "pbl_details_stats": read_json(settings.reports_dir / "pbl_details_stats.json", {}),
        "pbl_attachment_metadata_stats": read_json(settings.reports_dir / "pbl_attachment_metadata_stats.json", {}),
        "download_assets_stats": read_json(settings.reports_dir / "download_assets_stats.json", {}),
    }
    write_json(settings.reports_dir / "summary.json", summary)
    lines = [
        "# PBL Crawl Report",
        "",
        f"- list items: {summary['list_items']}",
        f"- normalized projects: {summary['normalized_projects']}",
        f"- downloaded asset entries: {summary['downloaded_assets']}",
        "",
        "## Data Quality",
        "",
    ]
    for key, value in summary["data_quality"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## File Counts", ""])
    for key, value in summary["file_counts"].items():
        lines.append(f"- {key}: {value}")
    (settings.reports_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def _count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(key) or "uncategorized")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _count_jsonl(path: Path) -> int:
    return sum(1 for _ in (iter_jsonl(path) or []))


def _classify_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "timeout" in text:
        return "timeout"
    if "403" in text:
        return "http_403_forbidden"
    if "401" in text:
        return "http_401_unauthorized"
    if "429" in text:
        return "http_429_rate_limited"
    if any(code in text for code in ["500", "502", "503", "504"]):
        return "http_5xx_server_error"
    return "unknown_error"


def _print_dry_run(
    settings: Settings,
    *,
    command: str = "crawl-pbl",
    known_project_paths: list[Path] | None = None,
    known_business_ids: int | None = None,
) -> None:
    payload: dict[str, Any] = {
        "command": command,
        "dry_run": True,
        "list_endpoint": LIST_ENDPOINT,
        "metadata_endpoints": [MAJOR_ENDPOINT, START_DATE_ENDPOINT],
        "attachment_endpoint": ATTACHMENT_ENDPOINT,
        "detail_endpoint": DETAIL_ENDPOINT,
        "major_attachment_endpoint": MAJOR_ATTACHMENT_ENDPOINT,
        "public_attachment_endpoint": PUBLIC_ATTACHMENT_ENDPOINT,
        "output_dir": str(settings.output_dir),
        "rate_limit": settings.rate_limit,
        "retries": settings.retries,
        "user_agent": settings.user_agent,
        "trust_env": settings.trust_env,
        "known_project_paths": [str(path) for path in known_project_paths or []],
        "will_persist": False,
    }
    if known_business_ids is not None:
        payload["known_business_ids"] = known_business_ids
        payload["incremental_ready"] = known_business_ids > 0
    sys.stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
