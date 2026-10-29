from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

from .api_analyzer import analyze_network_logs
from .config import (
    ASSET_FIELD_HINTS,
    ID_KEYS,
    PAGE_KEYS,
    PAGE_SIZE_KEYS,
    TEXT_FIELD_HINTS,
    CrawlSettings,
    ensure_output_dirs,
)
from .fetcher import AsyncFetcher, FetchResult
from .schema import ProjectRecord, SchemaValidationError
from .scope import is_topic_detail_source, is_topic_list_source
from .storage import read_json, read_jsonl, write_csv, write_json, write_jsonl, write_sqlite
from .utils import (
    contains_redacted_value,
    file_digest,
    file_extension_from_url_or_type,
    is_allowed_url,
    is_public_asset_url,
    now_iso,
    query_params,
    slugify,
    stable_hash,
    with_query_params,
)

logger = logging.getLogger(__name__)
ASSET_URL_RE = re.compile(r"https?://[^\s\"'<>]+?\.(?:pdf|jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?", re.I)
CATEGORY_FALLBACK_KEYS = ("category", "categoryName", "classifyName", "level1Name", "subjectName")
DIRECTION_FALLBACK_KEYS = (
    "direction",
    "directionName",
    "level2Name",
    "fieldName",
    "major",
    "majorName",
    "track",
    "trackName",
    "tagName",
)
TEXT_FOR_TAXONOMY_KEYS = ("title", "name", "courseName", "projectName", "topicName", "topicLingyu", "description", "intro", "summary")
SUPPLEMENTAL_TOPIC_KEYWORDS = [
    ("自然语言处理", "计算机", "人工智能"),
    ("计算机视觉", "计算机", "人工智能"),
    ("深度学习", "计算机", "人工智能"),
    ("机器学习", "计算机", "人工智能"),
    ("人工智能", "计算机", "人工智能"),
    ("软件工程", "计算机", "计算机科学与技术"),
    ("网络安全", "计算机", "计算机科学与技术"),
    ("计算机科学", "计算机", "计算机科学与技术"),
    ("编程", "计算机", "计算机科学与技术"),
    ("Python", "计算机", "计算机科学与技术"),
    ("电子信息", "工科", "电子科学技术"),
    ("电子工程", "工科", "电子科学技术"),
    ("通信工程", "工科", "信息与通信工程"),
    ("无线通信", "工科", "信息与通信工程"),
    ("机械工程", "工科", "机械工程"),
    ("环境工程", "工科", "环境科学与工程"),
    ("环境科学", "工科", "环境科学与工程"),
    ("生态学", "理科", "生物学"),
    ("生物制药", "理科", "生物学"),
    ("生物医学", "理科", "医学"),
    ("分子与细胞", "理科", "生物学"),
    ("海洋科学", "理科", "地球科学"),
    ("建筑规划", "工科", "建筑学"),
    ("城市规划", "工科", "建筑学"),
    ("市场营销", "商科", "营销学"),
    ("整合营销", "商科", "营销学"),
    ("数字营销", "商科", "营销学"),
    ("品牌管理", "商科", "营销学"),
    ("工商管理", "商科", "管理学"),
    ("企业战略", "商科", "管理学"),
    ("供应链", "商科", "管理学"),
    ("商业分析", "商科", "管理学"),
    ("量化金融", "商科", "金融学"),
    ("金融", "商科", "金融学"),
    ("经济学", "商科", "经济学"),
    ("公共政策", "文科", "政治学"),
    ("公共管理", "文科", "政治学"),
    ("国际关系", "文科", "政治学"),
    ("国际发展", "文科", "政治学"),
    ("社会治理", "文科", "社会学"),
    ("社会学", "文科", "社会学"),
    ("传播学", "文科", "新闻传播学"),
    ("媒体传播", "文科", "新闻传播学"),
    ("英语系", "文科", "语言文学"),
    ("英文系", "文科", "语言文学"),
    ("文学", "文科", "文学"),
    ("文化研究", "文科", "社会学"),
    ("心理", "理科", "心理学"),
    ("数学", "理科", "数学"),
    ("统计", "理科", "数学"),
    ("物理", "理科", "物理学"),
    ("化学", "理科", "化学"),
]


async def crawl_lists(settings: CrawlSettings, dry_run: bool = False) -> dict[str, Any]:
    ensure_output_dirs(settings)
    candidates = load_api_candidates(settings, "project_list")
    selected = [item for item in candidates if not item.get("requires_auth")]
    if dry_run:
        return {"selected_list_apis": selected, "would_request_pages": settings.max_pages}
    stats = {"apis": len(selected), "pages_requested": 0, "pages_succeeded": 0, "pages_failed": 0, "pages_skipped_existing": 0, "duplicate_pages": 0, "errors": {}}
    async with AsyncFetcher(settings) as fetcher:
        for api in selected:
            name = candidate_dir_name(api, "list-api")
            api_dir = settings.raw_dir / "lists" / name
            api_dir.mkdir(parents=True, exist_ok=True)
            page_param = first(api.get("pagination_params")) or detect_param(api, PAGE_KEYS)
            size_param = first(api.get("page_size_params")) or detect_param(api, PAGE_SIZE_KEYS)
            seen_item_keys: set[str] = set()
            for page_no in range(1, settings.max_pages + 1):
                url = api.get("endpoint") or api.get("sample_url")
                body = api.get("post_data")
                params: dict[str, Any] = {}
                if page_param:
                    params[page_param] = page_no
                if size_param:
                    params[size_param] = query_params(api.get("endpoint", "")).get(size_param, 20)
                page_path = api_dir / f"page_{page_no:04d}.json"
                if page_path.exists():
                    existing = read_json(page_path)
                    existing_items = extract_items(existing.get("data"))
                    seen_item_keys.update(item_identity(item) for item in existing_items if isinstance(item, dict))
                    stats["pages_skipped_existing"] += 1
                    total_pages = extract_total_pages(existing.get("data"))
                    if total_pages is not None and page_no >= total_pages:
                        break
                    continue
                result = await request_candidate(fetcher, api, url, params, body)
                stats["pages_requested"] += 1
                if result.ok and result.json_data is not None:
                    write_json(page_path, wrap_raw_result(result, api, {"page": page_no}))
                    stats["pages_succeeded"] += 1
                    items = extract_items(result.json_data)
                    if not items:
                        break
                    total_pages = extract_total_pages(result.json_data)
                    new_keys = {item_identity(item) for item in items if isinstance(item, dict)}
                    if new_keys and new_keys.issubset(seen_item_keys):
                        stats["duplicate_pages"] += 1
                        break
                    seen_item_keys.update(new_keys)
                    if total_pages is not None and page_no >= total_pages:
                        break
                else:
                    stats["pages_failed"] += 1
                    bump(stats["errors"], result.error_category or "unknown_error")
                    if result.error_category in {"http_401_unauthorized", "http_403_forbidden"}:
                        break
    write_json(settings.reports_dir / "crawl_lists_stats.json", stats)
    return stats


async def crawl_details(settings: CrawlSettings, dry_run: bool = False) -> dict[str, Any]:
    ensure_output_dirs(settings)
    list_items = load_list_items(settings)
    list_endpoints = {candidate.get("endpoint_without_query") or candidate.get("endpoint") for candidate in load_api_candidates(settings, "project_list")}
    detail_apis = [
        item
        for item in load_api_candidates(settings, "project_detail")
        if not item.get("requires_auth")
        and (item.get("endpoint_without_query") or item.get("endpoint")) not in list_endpoints
        and not item.get("has_total_or_page")
    ]
    identifiers = collect_identifiers(list_items)
    if dry_run:
        return {"detail_apis": detail_apis, "identifiers": identifiers[:20], "identifier_count": len(identifiers)}
    stats = {"detail_apis": len(detail_apis), "items": len(identifiers), "requested": 0, "succeeded": 0, "failed": 0, "errors": {}}
    if not detail_apis:
        write_json(settings.reports_dir / "crawl_details_stats.json", stats)
        return stats
    async with AsyncFetcher(settings) as fetcher:
        for api in detail_apis:
            id_param = detect_param(api, ID_KEYS) or first(api.get("id_fields")) or "id"
            api_dir = settings.raw_dir / "details" / candidate_dir_name(api, "detail-api")
            api_dir.mkdir(parents=True, exist_ok=True)
            for identifier in identifiers:
                url = api.get("endpoint") or api.get("sample_url")
                body = api.get("post_data")
                params = {id_param.split(".")[-1]: identifier}
                result = await request_candidate(fetcher, api, url, params, body, identifier=identifier, id_param=id_param)
                stats["requested"] += 1
                if result.ok and result.json_data is not None:
                    write_json(api_dir / f"{slugify(str(identifier), 'id')}.json", wrap_raw_result(result, api, {"identifier": identifier}))
                    stats["succeeded"] += 1
                else:
                    stats["failed"] += 1
                    bump(stats["errors"], result.error_category or "unknown_error")
                    if result.error_category in {"http_401_unauthorized", "http_403_forbidden"}:
                        break
    write_json(settings.reports_dir / "crawl_details_stats.json", stats)
    return stats


async def download_assets(
    settings: CrawlSettings,
    dry_run: bool = False,
    records: list[dict[str, Any]] | None = None,
    site_dirs: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    ensure_output_dirs(settings)
    if records is None:
        records = load_normalized_records(settings)
        if not records:
            records = [normalize_item(item).to_dict() for item in load_list_items(settings)]
    asset_jobs = build_asset_jobs(records, settings, site_dirs=site_dirs)
    cache_manifest = load_asset_cache_manifest(settings)
    all_asset_groups = group_asset_jobs_by_url(asset_jobs)
    pending_asset_groups = [group for group in all_asset_groups if asset_group_needs_processing(settings, group, cache_manifest)]
    asset_groups = pending_asset_groups
    if settings.max_assets is not None:
        asset_groups = asset_groups[: settings.max_assets]
    selected_jobs = [job for group in asset_groups for job in group]
    if dry_run:
        return {
            "unique_asset_urls": len(all_asset_groups),
            "pending_asset_urls": len(pending_asset_groups),
            "asset_urls": len(asset_groups),
            "materializations": len(selected_jobs),
            "sample": selected_jobs[:10],
        }
    manifest_dirty = 0
    stats = {
        "asset_urls": len(asset_groups),
        "materializations": len(selected_jobs),
        "downloaded": 0,
        "cache_hits": 0,
        "adopted_existing": 0,
        "content_duplicates": 0,
        "hardlinked": 0,
        "copied": 0,
        "materialized_skipped": 0,
        "target_conflicts": 0,
        "failed": 0,
        "errors": {},
    }
    stopped_hosts: set[str] = set()
    async with AsyncFetcher(settings) as fetcher:
        for group in asset_groups:
            url = group[0]["url"]
            source_host = urlparse(url).hostname or ""
            if source_host in stopped_hosts:
                stats["skipped_stopped_host"] = stats.get("skipped_stopped_host", 0) + 1
                continue
            cache_path = cached_asset_path(settings, cache_manifest.get(url))
            if cache_path is not None:
                stats["cache_hits"] += 1
            else:
                cache_path = adopt_existing_asset(settings, group)
                if cache_path is not None:
                    stats["adopted_existing"] += 1
                else:
                    result = await download_asset_with_fallbacks(fetcher, url, settings, stats)
                    if not result.ok or result.bytes_data is None:
                        stats["failed"] += 1
                        bump(stats["errors"], result.error_category or "unknown_error")
                        if result.error_category in {"http_401_unauthorized", "http_403_forbidden"}:
                            stopped_hosts.add(source_host)
                        continue
                    cache_path, content_exists = store_cached_bytes(settings, result.bytes_data)
                    stats["downloaded"] += 1
                    if content_exists:
                        stats["content_duplicates"] += 1
                cache_manifest[url] = cache_path.name
                manifest_dirty += 1
                if manifest_dirty >= 25:
                    write_json(asset_cache_manifest_path(settings), cache_manifest)
                    manifest_dirty = 0
            for job in group:
                materialize_cached_asset(cache_path, Path(job["target_path"]), stats)
    if manifest_dirty or not asset_cache_manifest_path(settings).exists():
        write_json(asset_cache_manifest_path(settings), cache_manifest)
    stats["asset_count"] = stats["asset_urls"]
    stats["stopped_hosts"] = sorted(host for host in stopped_hosts if host)
    write_json(settings.reports_dir / "download_assets_stats.json", stats)
    return stats


async def download_asset_with_fallbacks(
    fetcher: AsyncFetcher,
    url: str,
    settings: CrawlSettings,
    stats: dict[str, Any],
) -> FetchResult:
    last_result: FetchResult | None = None
    for index, candidate_url in enumerate(asset_url_candidates(url)):
        host = urlparse(candidate_url).hostname or ""
        if host in settings.skipped_asset_hosts:
            last_result = FetchResult(candidate_url, "GET", None, {}, None, None, None, f"asset_host_skipped:{host}", "asset host skipped by configuration")
            continue
        try:
            result = await asyncio.wait_for(fetcher.download(candidate_url), timeout=settings.timeout + 5)
        except asyncio.TimeoutError:
            result = FetchResult(candidate_url, "GET", None, {}, None, None, None, "timeout", "asset download exceeded hard timeout")
        if result.ok and result.bytes_data is not None:
            if index > 0:
                stats["fallback_downloaded"] = stats.get("fallback_downloaded", 0) + 1
            return result
        if result.error_category in {"http_401_unauthorized", "http_403_forbidden"}:
            return result
        last_result = result
    return last_result or FetchResult(url, "GET", None, {}, None, None, None, "unknown_error", "no asset URL candidates")


def asset_url_candidates(url: str) -> list[str]:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    candidates: list[str] = []
    match = re.fullmatch(r"(?P<bucket>[^.]+)\.oss-(?P<region>cn-[^.]+)\.aliyuncs\.com", host)
    if match:
        bucket = match.group("bucket")
        region = match.group("region")
        candidates.append(parsed._replace(netloc=f"{bucket}.{region}.oss.aliyuncs.com").geturl())
        candidates.append(parsed._replace(netloc=f"{bucket}.oss-accelerate.aliyuncs.com").geturl())
    candidates.append(url)
    return list(dict.fromkeys(candidates))


def normalize(settings: CrawlSettings) -> dict[str, Any]:
    ensure_output_dirs(settings)
    raw_items = merge_list_and_detail_items(load_list_items(settings), load_detail_items(settings))
    taxonomy = load_taxonomy_context(settings)
    records: list[dict[str, Any]] = []
    errors = 0
    for item in raw_items:
        try:
            records.append(enrich_record_taxonomy(normalize_item(item).to_dict(), taxonomy))
        except SchemaValidationError:
            errors += 1
    deduped = dedupe_records(records)
    jsonl_path = settings.processed_dir / "projects.jsonl"
    csv_path = settings.processed_dir / "projects.csv"
    sqlite_path = settings.processed_dir / "projects.sqlite"
    write_jsonl(jsonl_path, deduped)
    write_csv(csv_path, deduped)
    write_sqlite(sqlite_path, deduped)
    site_detail_files = write_site_detail_files(settings, deduped)
    stats = {
        "raw_items": len(raw_items),
        "records": len(deduped),
        "validation_errors": errors,
        "duplicates": len(records) - len(deduped),
        "site_detail_files": site_detail_files,
        "site_dir": str(settings.site_dir),
    }
    write_json(settings.reports_dir / "normalize_stats.json", stats)
    return stats


def generate_report(settings: CrawlSettings) -> dict[str, Any]:
    ensure_output_dirs(settings)
    report = {
        "generated_at": now_iso(),
        "network_logs": count_jsonl(settings.discovery_dir / "network_logs.jsonl"),
        "classification": safe_read_json(settings.discovery_dir / "api_classification.json"),
        "crawl_lists": safe_read_json(settings.reports_dir / "crawl_lists_stats.json"),
        "crawl_details": safe_read_json(settings.reports_dir / "crawl_details_stats.json"),
        "download_assets": safe_read_json(settings.reports_dir / "download_assets_stats.json"),
        "asset_files": count_files(settings.site_dir),
        "normalize": safe_read_json(settings.reports_dir / "normalize_stats.json"),
        "processed_files": {
            "jsonl": str(settings.processed_dir / "projects.jsonl"),
            "csv": str(settings.processed_dir / "projects.csv"),
            "sqlite": str(settings.processed_dir / "projects.sqlite"),
            "site_dir": str(settings.site_dir),
        },
    }
    write_json(settings.reports_dir / "crawl_report.json", report)
    (settings.reports_dir / "crawl_report.md").write_text(render_report_md(report), encoding="utf-8")
    return report


async def run_all(settings: CrawlSettings, skip_discovery: bool = False) -> dict[str, Any]:
    from .discovery import run_discovery

    results: dict[str, Any] = {}
    if not skip_discovery:
        results["discover"] = await run_discovery(settings)
    results["analyze"] = analyze_network_logs(settings)
    results["crawl_lists"] = await crawl_lists(settings)
    results["crawl_details"] = await crawl_details(settings)
    results["normalize"] = normalize(settings)
    results["download_assets"] = await download_assets(settings)
    results["report"] = generate_report(settings)
    return results


def load_api_candidates(settings: CrawlSettings, suspected_type: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    path = settings.discovery_dir / "api_classification.json"
    if path.exists():
        payload = read_json(path)
        candidates.extend([item for item in payload.get("classified_apis", []) if item.get("suspected_type") == suspected_type])
    candidates.extend(load_override_candidates(suspected_type))
    return dedupe_candidates(candidates)


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for candidate in candidates:
        marker = stable_hash(
            {
                "method": candidate.get("method"),
                "endpoint": candidate.get("endpoint_without_query") or candidate.get("endpoint"),
                "post_data": candidate.get("post_data"),
                "query_params": candidate.get("query_params"),
            }
        )
        if marker in seen:
            continue
        seen.add(marker)
        output.append(candidate)
    return output


def candidate_dir_name(api: dict[str, Any], fallback: str) -> str:
    endpoint = api.get("endpoint_without_query") or api.get("endpoint") or fallback
    if not api.get("post_data"):
        return slugify(endpoint, fallback)
    marker = stable_hash({"post_data": api.get("post_data"), "query_params": api.get("query_params")})
    return f"{slugify(endpoint, fallback)}__{marker}"


def load_override_candidates(suspected_type: str) -> list[dict[str, Any]]:
    path = Path("config/api_overrides.json")
    if not path.exists():
        return []
    payload = read_json(path)
    key = "list_apis" if suspected_type == "project_list" else "detail_apis" if suspected_type == "project_detail" else ""
    overrides = payload.get(key, []) if key else []
    candidates: list[dict[str, Any]] = []
    for item in overrides:
        url = item.get("url")
        if not url:
            continue
        candidates.append(
            {
                "name": item.get("name") or url,
                "endpoint": url,
                "endpoint_without_query": url.split("?", 1)[0],
                "sample_url": url,
                "method": item.get("method", "GET"),
                "suspected_type": suspected_type,
                "requires_auth": bool(item.get("requires_auth", False)),
                "query_params": item.get("query_params", {}),
                "post_data": item.get("post_data"),
                "pagination_params": [item["page_param"]] if item.get("page_param") else [],
                "page_size_params": [item["page_size_param"]] if item.get("page_size_param") else [],
                "id_fields": [item["id_param"]] if item.get("id_param") else [],
            }
        )
    return candidates


async def request_candidate(
    fetcher: AsyncFetcher,
    api: dict[str, Any],
    url: str,
    params: dict[str, Any],
    body: Any,
    identifier: Any | None = None,
    id_param: str | None = None,
) -> FetchResult:
    method = (api.get("method") or "GET").upper()
    if method == "GET":
        return await fetcher.request(method, with_query_params(url, params))
    if isinstance(body, dict):
        if contains_redacted_value(body):
            return FetchResult(url, method, None, {}, None, None, None, "requires_sensitive_payload", "request body contains redacted sensitive values")
        request_body = dict(body)
        if identifier is not None and id_param:
            request_body[id_param.split(".")[-1]] = identifier
        request_body.update(params)
        return await fetcher.request(method, url, json_body=request_body)
    return await fetcher.request(method, url, params=params)


def wrap_raw_result(result: FetchResult, api: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "fetched_at": now_iso(),
        "source_api": api,
        "request": {"url": result.url, "method": result.method, **meta},
        "status_code": result.status_code,
        "data": result.json_data,
    }


def load_list_items(settings: CrawlSettings) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted((settings.raw_dir / "lists").glob("**/*.json")):
        payload = read_json(path)
        source_url = payload.get("request", {}).get("url") or payload.get("source_api", {}).get("endpoint") or ""
        if not is_topic_list_source(source_url):
            continue
        for item in extract_items(payload.get("data")):
            if isinstance(item, dict):
                item.setdefault("_source_url", source_url)
                items.append(item)
    return items


def load_detail_items(settings: CrawlSettings) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted((settings.raw_dir / "details").glob("**/*.json")):
        payload = read_json(path)
        source_url = payload.get("request", {}).get("url") or payload.get("source_api", {}).get("endpoint") or ""
        if not is_topic_detail_source(source_url):
            continue
        data = payload.get("data")
        item = unwrap_detail(data)
        if isinstance(item, dict):
            if extract_items(item) and not pick(item, ("id", "uuid", "projectId", "courseId", "topicId", "title", "name", "courseName", "projectName", "topicName")):
                continue
            detail_item = dict(item)
            detail_item.setdefault("_source_url", source_url)
            detail_item["_detail_response"] = data
            items.append(detail_item)
    return items


def merge_list_and_detail_items(list_items: list[dict[str, Any]], detail_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep every list record and overlay a matching public detail response."""
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in list_items:
        key = source_item_key(item)
        if key not in merged:
            order.append(key)
        # Later snapshots replace stale list values for the same source record.
        merged[key] = item
    for detail in detail_items:
        key = source_item_key(detail)
        if key in merged:
            combined = dict(merged[key])
            combined.update(detail)
            merged[key] = combined
        else:
            order.append(key)
            merged[key] = detail
    return [merged[key] for key in order]


def source_item_key(item: dict[str, Any]) -> str:
    source_url = str(item.get("_source_url") or item.get("source_url") or "")
    host = urlparse(source_url).netloc
    return f"{host}:{item_identity(item)}"


def extract_items(value: Any) -> list[Any]:
    candidates: list[tuple[int, int, list[Any]]] = []

    def walk(node: Any, path: str = "$") -> None:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node):
                candidates.append((array_path_score(path), len(node), node))
            for item in node[:5]:
                walk(item, path + "[]")
        elif isinstance(node, dict):
            for key in ("records", "rows", "courseList", "list", "items", "data", "result"):
                if key in node:
                    walk(node[key], f"{path}.{key}")
            for item in node.values():
                if isinstance(item, (dict, list)):
                    walk(item, path + ".*")

    walk(value)
    return max(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2] if candidates else []


def array_path_score(path: str) -> int:
    lowered = path.lower()
    if any(key in lowered for key in (".records", ".rows")):
        return 100
    if any(key in lowered for key in (".list", ".items")):
        return 80
    if lowered.endswith(".data") or ".data." in lowered:
        return 50
    if lowered.endswith(".result") or ".result." in lowered:
        return 40
    return 0


def unwrap_detail(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("data", "result", "detail", "item"):
            if isinstance(value.get(key), dict):
                return unwrap_detail(value[key])
    return value


def extract_total_pages(value: Any) -> int | None:
    if isinstance(value, dict):
        for key in ("pages", "allPage", "totalPages", "pageCount"):
            candidate = value.get(key)
            if isinstance(candidate, int):
                return candidate
            if isinstance(candidate, str) and candidate.isdigit():
                return int(candidate)
        for key in ("data", "result"):
            nested = extract_total_pages(value.get(key))
            if nested is not None:
                return nested
    return None


def collect_identifiers(items: list[dict[str, Any]]) -> list[Any]:
    seen: set[str] = set()
    identifiers: list[Any] = []
    for item in items:
        for key in ID_KEYS:
            if key in item and item[key] not in (None, ""):
                value = item[key]
                marker = str(value)
                if marker not in seen:
                    seen.add(marker)
                    identifiers.append(value)
                break
    return identifiers


def normalize_item(item: dict[str, Any]) -> ProjectRecord:
    return ProjectRecord(
        source_url=str(item.get("_source_url") or item.get("source_url") or ""),
        canonical_url=item.get("url") or item.get("link") or item.get("detailUrl"),
        id=pick(item, ("id", "projectId", "courseId", "topicId")),
        uuid=pick(item, ("uuid",)),
        title=pick(item, ("title", "name", "courseName", "projectName", "topicName")),
        category=pick(item, CATEGORY_FALLBACK_KEYS),
        direction=pick(item, DIRECTION_FALLBACK_KEYS),
        teacher=pick(
            item,
            ("teacher", "teacherName", "instructor", "professor", "professorName", "speaker", "chineseSpeaker", "jiaoshou", "chineseJiaoshou"),
        ),
        university=pick(
            item,
            ("university", "school", "college", "organization", "teacherSchool", "schoolName", "teacherCollege", "speakerCollege", "chineseSchoolName"),
        ),
        description=pick(
            item,
            (
                "description",
                "intro",
                "summary",
                "content",
                "courseIntroduction",
                "introduceDetail",
                "introduceDetailRich",
                "originalIntroduction",
                "originalOverview",
                "courseResearch",
                "speakerIntroduce",
                "chineseSpeakerIntroduce",
            ),
        ),
        asset_urls=sorted({asset["url"] for asset in find_asset_urls(item, base_url=str(item.get("_source_url") or ""))}),
        raw=item,
    )


def load_taxonomy_context(settings: CrawlSettings) -> dict[str, Any]:
    return {
        "gec_professions": load_gec_profession_map(settings),
        "topic_categories": load_topic_category_tree(settings),
    }


def load_gec_profession_map(settings: CrawlSettings) -> dict[str, dict[str, str]]:
    taxonomy_dir = settings.raw_dir / "taxonomy"
    if taxonomy_dir.exists():
        for path in sorted(taxonomy_dir.glob("**/gec_profession_direction.json"), reverse=True):
            directions = extract_gec_directions(read_json(path).get("data"))
            if directions:
                return build_gec_profession_map(directions)
    path = settings.discovery_dir / "network_logs.jsonl"
    if not path.exists():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event") != "response" or "territory/query/summary" not in str(event.get("url", "")):
            continue
        directions = extract_gec_directions(event.get("response_json"))
        if directions:
            return build_gec_profession_map(directions)
    return {}


def extract_gec_directions(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("direction"), list):
        return payload["direction"]
    for key in ("data", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("direction"), list):
            return nested["direction"]
    return []


def build_gec_profession_map(directions: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for direction in directions:
        category_name = str(direction.get("name") or "")
        for profession in direction.get("profession") or []:
            profession_name = str(profession.get("name") or "")
            profession_id = profession.get("id")
            if profession_id not in (None, ""):
                mapping[f"profession:{profession_id}"] = {
                    "category": category_name,
                    "direction": profession_name,
                    "source": "gec_profession",
                }
            for fine_profession in profession.get("allFp") or []:
                fine_id = fine_profession.get("id")
                fine_name = str(fine_profession.get("name") or "")
                if profession_id not in (None, "") and fine_id not in (None, ""):
                    mapping[f"profession:{profession_id}:direction:{fine_id}"] = {
                        "category": category_name,
                        "direction": fine_name or profession_name,
                        "profession": profession_name,
                        "source": "gec_profession_direction",
                    }
    return mapping


def load_topic_category_tree(settings: CrawlSettings) -> list[dict[str, str]]:
    taxonomy_dir = settings.raw_dir / "taxonomy"
    if taxonomy_dir.exists():
        for path in sorted(taxonomy_dir.glob("**/harbour_topic_category.json"), reverse=True):
            tree = extract_topic_category_tree(read_json(path).get("data"))
            if tree:
                return flatten_topic_categories(tree)
    candidates = sorted((settings.raw_dir / "lists").glob("**/page_*.json"))
    for path in candidates:
        if "topic category" not in str(path):
            continue
        payload = read_json(path)
        tree = extract_topic_category_tree(payload.get("data"))
        if tree:
            return flatten_topic_categories(tree)
    return []


def extract_topic_category_tree(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("result", "data"):
        nested = payload.get(key)
        if isinstance(nested, list) and all(isinstance(item, dict) for item in nested):
            return nested
        if isinstance(nested, dict):
            tree = extract_topic_category_tree(nested)
            if tree:
                return tree
    return []


def flatten_topic_categories(tree: list[dict[str, Any]]) -> list[dict[str, str]]:
    categories: list[dict[str, str]] = []
    for category in tree:
        category_name = str(category.get("name") or "")
        for child in category.get("child") or category.get("children") or []:
            child_name = str(child.get("name") or "")
            if category_name and child_name:
                categories.append({"category": category_name, "direction": child_name, "source": "topic_category"})
    return sorted(categories, key=lambda item: len(item["direction"]), reverse=True)


def enrich_record_taxonomy(record: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    existing_category = record.get("category")
    existing_direction = record.get("direction")

    gec_match = match_gec_taxonomy(raw, taxonomy.get("gec_professions", {}))
    topic_match = match_topic_taxonomy(raw, taxonomy.get("topic_categories", []))
    match = gec_match or topic_match
    if not match:
        return record
    if not existing_category:
        record["category"] = match.get("category")
    if not existing_direction:
        record["direction"] = match.get("direction")
    record["taxonomy_source"] = match.get("source")
    if match.get("profession"):
        record["profession"] = match.get("profession")
    return record


def match_gec_taxonomy(raw: dict[str, Any], mapping: dict[str, dict[str, str]]) -> dict[str, str] | None:
    profession_id = raw.get("professionId")
    direction_id = raw.get("directionId")
    if profession_id in (None, ""):
        return None
    if direction_id not in (None, ""):
        match = mapping.get(f"profession:{profession_id}:direction:{direction_id}")
        if match:
            return match
    return mapping.get(f"profession:{profession_id}")


def match_topic_taxonomy(raw: dict[str, Any], categories: list[dict[str, str]]) -> dict[str, str] | None:
    text = " ".join(str(raw.get(key) or "") for key in TEXT_FOR_TAXONOMY_KEYS)
    if not text.strip():
        return None
    for category in categories:
        direction = category["direction"]
        if direction and direction in text:
            return category
    for keyword, category, direction in SUPPLEMENTAL_TOPIC_KEYWORDS:
        if keyword in text:
            return {"category": category, "direction": direction, "source": "supplemental_keyword"}
    return None


def find_asset_urls(value: Any, path: str = "", parent: dict[str, Any] | None = None, base_url: str = "") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "_detail_response":
                continue
            found.extend(find_asset_urls(item, f"{path}.{key}" if path else str(key), value, base_url))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found.extend(find_asset_urls(item, f"{path}[{idx}]", parent, base_url))
    elif isinstance(value, str):
        urls = ASSET_URL_RE.findall(value)
        if value.startswith("http") and any(hint in value.lower() for hint in ASSET_FIELD_HINTS):
            urls.append(value)
        if value.startswith("/") and any(hint in f"{path} {value}".lower() for hint in ASSET_FIELD_HINTS):
            urls.append(urljoin(base_url, value))
        for url in sorted(set(urls)):
            found.append({"url": url, "field_path": path, "parent": parent or {}})
    return found


def build_asset_jobs(
    records: list[dict[str, Any]],
    settings: CrawlSettings,
    site_dirs: Mapping[str, Path] | None = None,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    planned_paths: dict[str, int] = {}
    resolved_site_dirs = site_dirs or record_site_dirs(records, settings.site_dir)
    for record in records:
        seen_urls: set[str] = set()
        title = topic_dir_name(record)
        topic_dir = resolved_site_dirs[record_key(record)]
        raw = record.get("raw") if isinstance(record.get("raw"), dict) else record
        base_url = str(record.get("source_url") or record.get("canonical_url") or "")
        for asset in find_asset_urls(raw, base_url=base_url):
            url = asset["url"]
            if not is_allowed_url(url, settings.allowed_domains) and not is_public_asset_url(url):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            field_path = asset.get("field_path", "")
            parent = asset.get("parent", {})
            ext = file_extension_from_url_or_type(url)
            filename_base = asset_filename_base(title, field_path, parent)
            target_path = topic_dir / f"{slugify(filename_base)}{ext}"
            marker = filesystem_collision_key(target_path)
            if marker in planned_paths:
                planned_paths[marker] += 1
                target_path = topic_dir / f"{slugify(filename_base)}-{planned_paths[marker]}{ext}"
                marker = filesystem_collision_key(target_path)
                planned_paths[marker] = 1
            else:
                planned_paths[marker] = 1
            jobs.append(
                {
                    "url": url,
                    "field_path": field_path,
                    "target_path": str(target_path),
                }
            )
    return jobs


def group_asset_jobs_by_url(jobs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        groups.setdefault(str(job["url"]), []).append(job)
    return list(groups.values())


def asset_group_needs_processing(settings: CrawlSettings, jobs: list[dict[str, Any]], manifest: dict[str, str]) -> bool:
    cache_path = cached_asset_path(settings, manifest.get(jobs[0]["url"]))
    if cache_path is None:
        return True
    return any(not Path(job["target_path"]).is_file() or Path(job["target_path"]).stat().st_size == 0 for job in jobs)


def asset_cache_manifest_path(settings: CrawlSettings) -> Path:
    return settings.asset_cache_dir / "url_manifest.json"


def load_asset_cache_manifest(settings: CrawlSettings) -> dict[str, str]:
    path = asset_cache_manifest_path(settings)
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(url): str(digest) for url, digest in payload.items() if isinstance(url, str) and isinstance(digest, str)}


def cached_asset_path(settings: CrawlSettings, digest: str | None) -> Path | None:
    if digest is None or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    path = settings.asset_cache_dir / "sha256" / digest
    return path if path.is_file() and path.stat().st_size > 0 else None


def adopt_existing_asset(settings: CrawlSettings, jobs: list[dict[str, Any]]) -> Path | None:
    for job in jobs:
        path = Path(job["target_path"])
        if not path.is_file() or path.stat().st_size == 0:
            continue
        digest = file_digest(path)
        cache_path = settings.asset_cache_dir / "sha256" / digest
        if not cache_path.exists():
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(path, cache_path)
            except OSError:
                shutil.copy2(path, cache_path)
        return cache_path
    return None


def store_cached_bytes(settings: CrawlSettings, content: bytes) -> tuple[Path, bool]:
    digest = hashlib.sha256(content).hexdigest()
    cache_path = settings.asset_cache_dir / "sha256" / digest
    if cache_path.is_file() and cache_path.stat().st_size > 0:
        return cache_path, True
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_name(f".{digest}.{os.getpid()}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(cache_path)
    return cache_path, False


def materialize_cached_asset(cache_path: Path, target_path: Path, stats: dict[str, Any]) -> None:
    if target_path.exists():
        if target_path.is_file() and target_path.stat().st_size > 0 and file_digest(target_path) == cache_path.name:
            stats["materialized_skipped"] += 1
        else:
            stats["target_conflicts"] += 1
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(cache_path, target_path)
        stats["hardlinked"] += 1
    except OSError:
        shutil.copy2(cache_path, target_path)
        stats["copied"] += 1


def write_site_detail_files(settings: CrawlSettings, records: list[dict[str, Any]]) -> int:
    count = 0
    site_dirs = record_site_dirs(records, settings.site_dir)
    for record in records:
        write_json(site_dirs[record_key(record)] / "details.json", record)
        count += 1
    return count


def record_site_dirs(records: list[dict[str, Any]], root: Path) -> dict[str, Path]:
    bases = {record_key(record): record_site_dir_parts(record) for record in records}
    counts = Counter(bases.values())
    dirs: dict[str, Path] = {}
    for record in records:
        key = record_key(record)
        category, direction, topic = bases[key]
        if counts[bases[key]] > 1:
            topic = f"{topic}__{slugify(key, 'record', 24)}"
        dirs[key] = root / category / direction / topic
    return dirs


def record_site_dir(record: dict[str, Any], root: Path) -> Path:
    return root.joinpath(*record_site_dir_parts(record))


def record_site_dir_parts(record: dict[str, Any]) -> tuple[str, str, str]:
    return category_dir_name(record), direction_dir_name(record), topic_dir_name(record)


def category_dir_name(record: dict[str, Any]) -> str:
    return slugify(str(record.get("category") or nested_pick(record, CATEGORY_FALLBACK_KEYS) or "未分类"), "uncategorized")


def direction_dir_name(record: dict[str, Any]) -> str:
    return slugify(str(record.get("direction") or nested_pick(record, DIRECTION_FALLBACK_KEYS) or "未分方向"), "uncategorized")


def topic_dir_name(record: dict[str, Any]) -> str:
    return slugify(str(record.get("title") or record.get("id") or record.get("record_hash") or "untitled"), "untitled")


def record_key(record: dict[str, Any]) -> str:
    return str(record.get("id") or record.get("uuid") or record.get("canonical_url") or record.get("record_hash") or stable_hash(record))


def filesystem_collision_key(path: Path) -> str:
    return unicodedata.normalize("NFC", str(path)).casefold()


def asset_filename_base(title: str, field_path: str, parent: dict[str, Any]) -> str:
    lowered = field_path.lower()
    if any(hint in lowered for hint in ("poster", "cover", "海报")):
        return title
    if any(hint in lowered for hint in ("avatar", "head", "photo", "teacher", "professor", "头像")):
        teacher = pick(parent, ("teacher", "teacherName", "professor", "professorName", "name"))
        if teacher:
            return str(teacher)
    field = field_path.split(".")[-1].replace("[]", "")
    return field or title


def load_normalized_records(settings: CrawlSettings) -> list[dict[str, Any]]:
    path = settings.processed_dir / "projects.jsonl"
    return read_jsonl(path) if path.exists() else []


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get("id") or record.get("uuid") or record.get("canonical_url") or record.get("record_hash") or stable_hash(record))
        if key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


def item_identity(item: dict[str, Any]) -> str:
    return str(
        pick(item, ("id", "uuid", "projectId", "courseId", "topicId", "itemId", "url", "detailUrl"))
        or stable_hash(item)
    )


def detect_param(api: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    params = api.get("query_params") or {}
    body = api.get("post_data") or {}
    for source in (params, body if isinstance(body, dict) else {}):
        lowers = {str(key).lower(): str(key) for key in source.keys()}
        for candidate in candidates:
            if candidate.lower() in lowers:
                return lowers[candidate.lower()]
    return None


def pick(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if item.get(key) not in (None, ""):
            return item[key]
    lowered = {str(key).lower(): key for key in item.keys()}
    for key in keys:
        actual = lowered.get(key.lower())
        if actual and item.get(actual) not in (None, ""):
            return item[actual]
    return None


def nested_pick(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else item
    if isinstance(raw, dict):
        return pick(raw, keys)
    return None


def first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else None


def bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def safe_read_json(path: Path) -> Any:
    return read_json(path) if path.exists() else None


def render_report_md(report: dict[str, Any]) -> str:
    normalize_stats = report.get("normalize") or {}
    asset_stats = report.get("download_assets") or {}
    return "\n".join(
        [
            "# Crawl Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- network log events: `{report.get('network_logs')}`",
            f"- normalized records: `{normalize_stats.get('records', 0)}`",
            f"- asset files present: `{report.get('asset_files', 0)}`",
            f"- downloaded assets in last run: `{asset_stats.get('downloaded', 0)}`",
            f"- skipped existing assets in last run: `{asset_stats.get('skipped', 0)}`",
            f"- failed assets: `{asset_stats.get('failed', 0)}`",
            "",
            "## Outputs",
            "",
            f"- JSONL: `{report['processed_files']['jsonl']}`",
            f"- CSV: `{report['processed_files']['csv']}`",
            f"- SQLite: `{report['processed_files']['sqlite']}`",
            f"- Site mirror: `{report['processed_files']['site_dir']}`",
        ]
    )
