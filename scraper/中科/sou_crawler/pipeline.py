from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any
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
from .storage import read_json, read_jsonl, write_csv, write_json, write_jsonl, write_sqlite
from .utils import (
    contains_redacted_value,
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


async def download_assets(settings: CrawlSettings, dry_run: bool = False) -> dict[str, Any]:
    ensure_output_dirs(settings)
    records = load_normalized_records(settings)
    if not records:
        records = [normalize_item(item).to_dict() for item in load_list_items(settings)]
    asset_jobs = build_asset_jobs(records, settings)
    if settings.max_assets is not None:
        asset_jobs = asset_jobs[: settings.max_assets]
    if dry_run:
        return {"asset_count": len(asset_jobs), "sample": asset_jobs[:10]}
    stats = {"asset_count": len(asset_jobs), "downloaded": 0, "failed": 0, "skipped": 0, "errors": {}}
    async with AsyncFetcher(settings) as fetcher:
        for job in asset_jobs:
            target = Path(job["target_path"])
            if target.exists() and target.stat().st_size > 0:
                stats["skipped"] += 1
                continue
            result = await download_asset_with_fallbacks(fetcher, job["url"], settings, stats)
            if result.ok and result.bytes_data is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(result.bytes_data)
                stats["downloaded"] += 1
            else:
                stats["failed"] += 1
                bump(stats["errors"], result.error_category or "unknown_error")
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
    raw_items = load_detail_items(settings) or load_list_items(settings)
    records: list[dict[str, Any]] = []
    errors = 0
    for item in raw_items:
        try:
            records.append(normalize_item(item).to_dict())
        except SchemaValidationError:
            errors += 1
    deduped = dedupe_records(records)
    jsonl_path = settings.processed_dir / "projects.jsonl"
    csv_path = settings.processed_dir / "projects.csv"
    sqlite_path = settings.processed_dir / "projects.sqlite"
    write_jsonl(jsonl_path, deduped)
    write_csv(csv_path, deduped)
    write_sqlite(sqlite_path, deduped)
    stats = {"raw_items": len(raw_items), "records": len(deduped), "validation_errors": errors, "duplicates": len(records) - len(deduped)}
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
        "asset_files": count_files(settings.assets_dir),
        "normalize": safe_read_json(settings.reports_dir / "normalize_stats.json"),
        "processed_files": {
            "jsonl": str(settings.processed_dir / "projects.jsonl"),
            "csv": str(settings.processed_dir / "projects.csv"),
            "sqlite": str(settings.processed_dir / "projects.sqlite"),
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
        data = payload.get("data")
        item = unwrap_detail(data)
        if isinstance(item, dict):
            if extract_items(item) and not pick(item, ("id", "uuid", "projectId", "courseId", "topicId", "title", "name", "courseName", "projectName", "topicName")):
                continue
            item.setdefault("_source_url", source_url)
            items.append(item)
    return items


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
        category=pick(item, ("category", "categoryName", "classifyName", "level1Name", "subjectName")),
        teacher=pick(item, ("teacher", "teacherName", "instructor", "professor", "professorName")),
        university=pick(item, ("university", "school", "college", "organization", "teacherSchool", "schoolName")),
        description=pick(item, ("description", "intro", "summary", "content")),
        asset_urls=[asset["url"] for asset in find_asset_urls(item, base_url=str(item.get("_source_url") or ""))],
        raw=item,
    )


def find_asset_urls(value: Any, path: str = "", parent: dict[str, Any] | None = None, base_url: str = "") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
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


def build_asset_jobs(records: list[dict[str, Any]], settings: CrawlSettings) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    planned_paths: dict[str, int] = {}
    for record in records:
        title = slugify(str(record.get("title") or record.get("id") or record.get("record_hash") or "untitled"), "untitled")
        category = slugify(str(record.get("category") or "未分类"), "uncategorized")
        raw = record.get("raw") if isinstance(record.get("raw"), dict) else record
        base_url = str(record.get("source_url") or record.get("canonical_url") or "")
        for asset in find_asset_urls(raw, base_url=base_url):
            url = asset["url"]
            if not is_allowed_url(url, settings.allowed_domains) and not is_public_asset_url(url):
                continue
            if url in seen:
                continue
            seen.add(url)
            field_path = asset.get("field_path", "")
            parent = asset.get("parent", {})
            ext = file_extension_from_url_or_type(url)
            filename_base = asset_filename_base(title, field_path, parent)
            target_path = settings.assets_dir / category / title / f"{slugify(filename_base)}{ext}"
            marker = filesystem_collision_key(target_path)
            if marker in planned_paths:
                planned_paths[marker] += 1
                target_path = settings.assets_dir / category / title / f"{slugify(filename_base)}-{planned_paths[marker]}{ext}"
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
        ]
    )
