from __future__ import annotations

import asyncio
import copy
import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .classifier import analyze_network_logs, collect_keys
from .config import CrawlConfig, ensure_output_dirs
from .fetcher import Fetcher, set_query_param
from .parser import extract_records
from .utils import append_jsonl, canonical_url, content_hash, iter_jsonl, read_json, stable_json_dumps, utc_now_iso, write_json

LOGGER = logging.getLogger(__name__)


def load_api_candidates(config: CrawlConfig, category: str) -> list[dict[str, Any]]:
    path = config.discovery_dir / "api_classification.json"
    if not path.exists():
        signatures = analyze_network_logs(config)
        candidates = [signature.__dict__ for signature in signatures]
        write_json(path, candidates)
    else:
        candidates = read_json(path, [])
    return [api for api in candidates if category in api.get("categories", [])]


async def crawl_lists(config: CrawlConfig, *, dry_run: bool = False) -> None:
    ensure_output_dirs(config)
    seeds = load_request_seeds(config, "项目列表接口")
    candidates = [seed for seed in seeds if is_viable_list_seed(seed)] or seeds
    if dry_run:
        _print_plan("crawl-lists", candidates, config.max_pages)
        return
    fetcher = Fetcher(config)
    seen_hashes: set[str] = set()
    try:
        for api in candidates:
            pagination = api.get("pagination_params") or []
            page_param = choose_page_param(pagination, api.get("url", ""))
            size_param = choose_size_param(pagination, api.get("url", ""))
            for page_no in range(1, config.max_pages + 1):
                url = api["url"]
                body = copy.deepcopy(api.get("request_body_sample"))
                if page_param:
                    url = set_query_param(url, page_param, page_no)
                if size_param:
                    url = set_query_param(url, size_param, 50)
                body_page_changed = set_nested_key(body, {"page", "pageNo", "pageNum", "current"}, page_no)
                body_size_changed = set_nested_key(body, {"limit", "size", "pageSize"}, 50)
                payload, meta = await fetcher.request_json(
                    api.get("method", "GET"),
                    url,
                    json_body=body if api.get("method") == "POST" else None,
                )
                row = {
                    "crawled_at": utc_now_iso(),
                    "api": api["key"],
                    "page": page_no,
                    "meta": meta,
                    "payload": payload,
                }
                append_jsonl(config.raw_dir / "list_responses.jsonl", row)
                records = extract_records(payload)
                new_records = 0
                for record in records:
                    digest = content_hash(record)
                    if digest in seen_hashes:
                        fetcher.stats.duplicate_records += 1
                        continue
                    seen_hashes.add(digest)
                    new_records += 1
                    fetcher.stats.records_extracted += 1
                    append_jsonl(
                        config.raw_dir / "list_records.jsonl",
                        {
                            "source_url": meta.get("url", url),
                            "canonical_url": canonical_url(meta.get("url", url)),
                            "crawled_at": utc_now_iso(),
                            "record": record,
                        },
                    )
                if not records or (page_no > 1 and new_records == 0):
                    break
                total_pages = find_first_int(payload, ("allPage", "pages", "totalPage", "totalPages"))
                if total_pages is not None and page_no >= total_pages:
                    break
                if not page_param and not body_page_changed:
                    break
    finally:
        await fetcher.close()
        write_json(config.reports_dir / "crawl_lists_stats.json", fetcher.stats.__dict__)


async def crawl_details(config: CrawlConfig, *, dry_run: bool = False) -> None:
    ensure_output_dirs(config)
    candidates = load_detail_candidates(config)
    records = read_records(config.raw_dir / "list_records.jsonl")
    ids = collect_ids(records)
    if dry_run:
        print(f"crawl-details: {len(candidates)} candidate detail APIs, {len(ids)} discovered IDs")
        for api in candidates[:20]:
            print(f"- {api.get('method')} {api.get('url')}")
        return
    fetcher = Fetcher(config)
    try:
        for api in candidates:
            if not ids:
                continue
            id_param = choose_id_param(api)
            if not id_param and not api.get("body_id_field"):
                continue
            for idx, item_id in enumerate(sorted(ids)):
                if idx >= config.max_details:
                    break
                url = api["url"]
                body = copy.deepcopy(api.get("request_body_sample"))
                if api.get("body_id_field"):
                    body = body if isinstance(body, dict) else {}
                    body[api["body_id_field"]] = item_id
                elif id_param:
                    url = set_query_param(url, id_param, item_id)
                payload, meta = await fetcher.request_json(
                    api.get("method", "GET"),
                    url,
                    json_body=body if api.get("method") == "POST" else None,
                )
                append_jsonl(
                    config.raw_dir / "detail_responses.jsonl",
                    {
                        "crawled_at": utc_now_iso(),
                        "api": api["key"],
                        "id": item_id,
                        "meta": meta,
                        "payload": payload,
                    },
                )
                if payload is not None:
                    fetcher.stats.records_extracted += 1
    finally:
        await fetcher.close()
        write_json(config.reports_dir / "crawl_details_stats.json", fetcher.stats.__dict__)


async def download_assets(config: CrawlConfig, *, dry_run: bool = False) -> None:
    from .asset_downloader import download_assets_from_outputs

    await download_assets_from_outputs(config, dry_run=dry_run)


def read_records(path: Path) -> list[dict[str, Any]]:
    return iter_jsonl(path)


def load_request_seeds(config: CrawlConfig, category: str) -> list[dict[str, Any]]:
    candidates = load_api_candidates(config, category)
    candidate_by_key = {api["key"]: api for api in candidates}
    seeds: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in iter_jsonl(config.discovery_dir / "network_logs.jsonl"):
        if row.get("event") != "response" or not row.get("is_json"):
            continue
        key = f"{row.get('method', 'GET').upper()} {urlsplit(row['url']).scheme}://{urlsplit(row['url']).netloc}{urlsplit(row['url']).path}"
        if key not in candidate_by_key:
            continue
        api = dict(candidate_by_key[key])
        api["url"] = row["url"]
        api["method"] = row.get("method", api.get("method", "GET"))
        api["request_body_sample"] = row.get("post_data_json", row.get("post_data"))
        seed_key = stable_json_dumps(
            {
                "method": api["method"],
                "url": api["url"],
                "body": api["request_body_sample"],
            }
        )
        if seed_key in seen:
            continue
        seen.add(seed_key)
        seeds.append(api)
    return seeds or candidates


def load_detail_candidates(config: CrawlConfig) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    seen: set[str] = set()
    for api in load_request_seeds(config, "项目详情接口"):
        seed = dict(api)
        if is_viable_detail_seed(seed):
            seed["body_id_field"] = find_body_id_field(seed.get("request_body_sample"))
            seed_key = stable_json_dumps(seed)
            if seed_key not in seen:
                seen.add(seed_key)
                seeds.append(seed)
    for row in iter_jsonl(config.discovery_dir / "mobile_share_logs.jsonl"):
        if row.get("event") != "response" or not row.get("is_json"):
            continue
        if row.get("url", "").endswith("/souapi/course/query/share"):
            request = row.get("request", {})
            body = request.get("post_data_json") or {"isQrcode": False}
            seed = {
                "key": "POST https://gec-api.gecacademy.cn/souapi/course/query/share",
                "url": row["url"],
                "method": "POST",
                "request_body_sample": body,
                "body_id_field": "id",
                "categories": ["项目详情接口"],
            }
            seed_key = stable_json_dumps(seed)
            if seed_key not in seen:
                seen.add(seed_key)
                seeds.append(seed)
    if seeds:
        return seeds
    return [
        {
            "key": "POST https://gec-api.gecacademy.cn/souapi/course/query/share",
            "url": "https://gec-api.gecacademy.cn/souapi/course/query/share",
            "method": "POST",
            "request_body_sample": {"isQrcode": False},
            "body_id_field": "id",
            "categories": ["项目详情接口"],
        }
    ]


def is_viable_list_seed(api: dict[str, Any]) -> bool:
    url = api.get("url", "")
    if not url.startswith(("http://", "https://")):
        return False
    if "项目列表接口" not in api.get("categories", []):
        return False
    response_keys = {key.lower() for key in collect_keys(api.get("response_sample"))}
    if "courselist" in response_keys or response_keys.intersection({"allpage", "totalpage", "totalpages"}):
        return True
    path = urlsplit(url).path.lower()
    return "course/query" in path and not path.endswith(("/timescope", "/summary"))


def is_viable_detail_seed(api: dict[str, Any]) -> bool:
    if "项目详情接口" not in api.get("categories", []):
        return False
    path = urlsplit(api.get("url", "")).path.lower()
    if "argstoid" in path or path.endswith(("/query/common", "/query/aihub", "/query/summary")):
        return False
    response_keys = {key.lower() for key in collect_keys(api.get("response_sample"))}
    if "courselist" in response_keys:
        return False
    return any(hint in path for hint in ("/detail", "/share", "/info", "/query/share")) and (
        choose_id_param(api) or find_body_id_field(api.get("request_body_sample"))
    )


def find_body_id_field(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for name in ("id", "uuid", "projectId", "courseId", "itemId", "detailId"):
        if name in body:
            return name
    return None


def collect_ids(rows: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    id_names = {"id", "uuid", "projectId", "courseId", "itemId", "detailId"}
    for row in rows:
        record = row.get("record", row)
        if isinstance(record, dict):
            for key, value in record.items():
                if key in id_names and value not in (None, ""):
                    ids.add(str(value))
    return ids


def choose_page_param(params: list[str], url: str) -> str | None:
    query = parse_qs(urlsplit(url).query)
    for name in ("page", "pageNo", "pageNum", "current"):
        if name in params or name in query:
            return name
    return None


def choose_size_param(params: list[str], url: str) -> str | None:
    query = parse_qs(urlsplit(url).query)
    for name in ("pageSize", "size", "limit"):
        if name in params or name in query:
            return name
    return None


def choose_id_param(api: dict[str, Any]) -> str | None:
    query = parse_qs(urlsplit(api.get("url", "")).query)
    for name in ("id", "uuid", "projectId", "courseId", "itemId", "detailId"):
        if name in query or name in api.get("id_fields", []):
            return name
    return None


def set_nested_key(value: Any, names: set[str], replacement: Any) -> bool:
    changed = False
    if isinstance(value, dict):
        for key, inner in value.items():
            if key in names:
                value[key] = replacement
                changed = True
            elif isinstance(inner, (dict, list)):
                changed = set_nested_key(inner, names, replacement) or changed
    elif isinstance(value, list):
        for inner in value:
            if isinstance(inner, (dict, list)):
                changed = set_nested_key(inner, names, replacement) or changed
    return changed


def find_first_int(value: Any, names: tuple[str, ...]) -> int | None:
    if isinstance(value, dict):
        for key, inner in value.items():
            if key in names:
                try:
                    return int(inner)
                except (TypeError, ValueError):
                    pass
            found = find_first_int(inner, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for inner in value:
            found = find_first_int(inner, names)
            if found is not None:
                return found
    return None


def _print_plan(name: str, candidates: list[dict[str, Any]], max_pages: int) -> None:
    print(f"{name}: {len(candidates)} candidate APIs, max_pages={max_pages}")
    for api in candidates:
        print(f"- {api.get('method')} {api.get('url')}")


def run_async(coro: Any) -> None:
    asyncio.run(coro)
