from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from string import Formatter
from typing import Any
from urllib.parse import urlencode
import asyncio
import json
import logging
import sys

from .config import Settings
from .fetcher import CrawlStopped, HttpFetcher
from .schema import CrawlStats
from .storage import iter_jsonl, read_json, write_json, write_jsonl
from .utils import extract_records, find_first, flatten_json, stable_hash, utc_now

LOGGER = logging.getLogger(__name__)


async def crawl_lists(settings: Settings) -> None:
    targets = _load_targets(settings).get("list_endpoints", [])
    if settings.dry_run:
        _print_dry_run("crawl-lists", targets, settings)
        return
    stats = CrawlStats(started_at=utc_now(), target_domain="list_endpoints")
    all_records: list[dict[str, Any]] = []
    raw_path = settings.raw_dir / "lists_raw.jsonl"
    if raw_path.exists():
        raw_path.unlink()

    async with HttpFetcher(settings) as fetcher:
        for target in targets:
            for request_spec in _iter_paginated_requests(target, settings.max_pages):
                try:
                    stats.pages_requested += 1
                    data = await _fetch_spec(fetcher, request_spec)
                    stats.pages_succeeded += 1
                    page_records = extract_records(data)
                    stats.records_extracted += len(page_records)
                    write_jsonl_append(raw_path, {"target": target.get("name"), "request": request_spec, "data": data})
                    all_records.extend(_decorate_record(item, request_spec) for item in page_records)
                    if not _should_continue(data, page_records, request_spec):
                        break
                except CrawlStopped:
                    stats.pages_failed += 1
                    stats.add_error("http_401_or_403_access_control")
                    break
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("列表抓取失败: %s", exc)
                    stats.pages_failed += 1
                    stats.add_error(classify_exception(exc))
                    break

    unique = _dedupe_records(all_records)
    stats.duplicate_records = len(all_records) - len(unique)
    write_jsonl(settings.raw_dir / "list_items.jsonl", unique)
    write_json(settings.reports_dir / "crawl_lists_stats.json", stats.as_dict())
    LOGGER.info("列表抓取完成: records=%s", len(unique))


async def crawl_details(settings: Settings) -> None:
    config = _load_targets(settings)
    detail_targets = config.get("detail_endpoints", [])
    if settings.dry_run:
        _print_dry_run("crawl-details", detail_targets, settings)
        return
    if not detail_targets:
        LOGGER.warning("未配置 detail_endpoints，跳过详情抓取。")
        return
    list_items = list(iter_jsonl(settings.raw_dir / "list_items.jsonl") or [])
    source_items = list_items[: settings.max_pages]
    if not source_items and any(target.get("standalone") for target in detail_targets):
        source_items = [{}]
    stats = CrawlStats(started_at=utc_now(), target_domain="detail_endpoints")
    raw_path = settings.raw_dir / "details_raw.jsonl"
    if raw_path.exists():
        raw_path.unlink()

    async with HttpFetcher(settings) as fetcher:
        for item in source_items:
            for target in detail_targets:
                try:
                    request_spec = _build_detail_request(target, item)
                    if request_spec is None:
                        continue
                    stats.pages_requested += 1
                    data = await _fetch_spec(fetcher, request_spec)
                    stats.pages_succeeded += 1
                    stats.records_extracted += 1
                    write_jsonl_append(
                        raw_path,
                        {
                            "target": target.get("name"),
                            "source_item": item,
                            "request": request_spec,
                            "data": data,
                        },
                    )
                    for followup in target.get("followups", []) or []:
                        followup_spec = _build_followup_request(followup, item, data)
                        stats.pages_requested += 1
                        followup_data = await _fetch_spec(fetcher, followup_spec)
                        stats.pages_succeeded += 1
                        stats.records_extracted += 1
                        write_jsonl_append(
                            raw_path,
                            {
                                "target": followup.get("name"),
                                "source_item": item,
                                "parent_target": target.get("name"),
                                "parent_data": data,
                                "request": followup_spec,
                                "data": followup_data,
                            },
                        )
                except CrawlStopped:
                    stats.pages_failed += 1
                    stats.add_error("http_401_or_403_access_control")
                    break
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("详情抓取失败: %s", exc)
                    stats.pages_failed += 1
                    stats.add_error(classify_exception(exc))

    write_json(settings.reports_dir / "crawl_details_stats.json", stats.as_dict())
    LOGGER.info("详情抓取完成: pages=%s", stats.pages_succeeded)


def _load_targets(settings: Settings) -> dict[str, Any]:
    settings.ensure_dirs()
    if settings.api_targets_path.exists():
        return read_json(settings.api_targets_path, {})
    example_path = settings.config_dir / "api_targets.example.json"
    if settings.dry_run and example_path.exists():
        return read_json(example_path, {})
    example = {
        "list_endpoints": [
            {
                "name": "replace-with-discovered-list-api",
                "method": "GET",
                "url": "https://edu4-crm-api.neoschool.com/sdm/mtc/pubController/pageV2",
                "params": {"page": 1, "pageSize": 20},
                "pagination": {"page_param": "page", "page_size_param": "pageSize", "page_size": 20, "start_page": 1},
            }
        ],
        "detail_endpoints": [
            {
                "name": "replace-with-discovered-detail-api",
                "method": "GET",
                "url": "https://edu4-crm-api.neoschool.com/sdm/mtc/pubController/get",
                "params": {"id": "{id}"},
                "id_fields": ["id", "uuid", "courseId", "projectId", "courseExtendId"],
            }
        ],
    }
    write_json(settings.config_dir / "api_targets.example.json", example)
    raise SystemExit(
        "未找到 config/api_targets.json。请先运行 discover/analyze-apis，"
        "再参考 config/api_targets.example.json 填入确认后的列表和详情接口。"
    )


def _iter_paginated_requests(target: dict[str, Any], max_pages: int) -> list[dict[str, Any]]:
    pagination = target.get("pagination") or {}
    page_param = pagination.get("page_param")
    page_size_param = pagination.get("page_size_param")
    start_page = int(pagination.get("start_page", 1))
    page_size = int(pagination.get("page_size", target.get("params", {}).get(page_size_param, 20) if page_size_param else 20))
    requests: list[dict[str, Any]] = []
    for offset in range(max_pages):
        spec = deepcopy(target)
        spec.pop("pagination", None)
        params = dict(spec.get("params") or {})
        json_body = deepcopy(spec.get("json")) if isinstance(spec.get("json"), dict) else spec.get("json")
        page = start_page + offset
        if page_param:
            params[page_param] = page
        if page_size_param:
            params[page_size_param] = page_size
        if isinstance(json_body, dict):
            if page_param and page_param in json_body:
                json_body[page_param] = page
            if page_size_param and page_size_param in json_body:
                json_body[page_size_param] = page_size
        spec["params"] = params
        if json_body is not None:
            if page_param:
                json_body = _set_key_recursive(json_body, page_param, page)
            if page_size_param:
                json_body = _set_key_recursive(json_body, page_size_param, page_size)
            spec["json"] = json_body
        spec["_page"] = page
        spec["_page_size"] = page_size
        requests.append(spec)
    return requests


async def _fetch_spec(fetcher: HttpFetcher, spec: dict[str, Any]) -> Any:
    method = spec.get("method", "GET")
    url = _render_template(spec["url"], spec)
    params = spec.get("params") or None
    json_body = spec.get("json")
    data = spec.get("data")
    headers = _safe_request_headers(spec.get("headers") or {})
    return await fetcher.request_json(method, url, params=params, json=json_body, data=data, headers=headers or None)


def _build_detail_request(target: dict[str, Any], item: dict[str, Any]) -> dict[str, Any] | None:
    id_fields = target.get("id_fields") or ["id", "uuid", "courseId", "projectId", "courseExtendId"]
    item_id = find_first(item, id_fields)
    if item_id in (None, "") and not target.get("standalone"):
        return None
    spec = deepcopy(target)
    spec["_item_id"] = item_id
    context = {"id": item_id or "", **(target.get("context") or {}), **item}
    spec["url"] = _render_template(spec["url"], context)
    spec["params"] = _render_values(spec.get("params") or {}, context)
    if "json" in spec:
        spec["json"] = _render_values(spec["json"], context)
    if "data" in spec:
        spec["data"] = _render_values(spec["data"], context)
    if "headers" in spec:
        spec["headers"] = _render_values(spec["headers"], context)
    return spec


def _build_followup_request(followup: dict[str, Any], item: dict[str, Any], parent_data: Any) -> dict[str, Any]:
    spec = deepcopy(followup)
    context = _response_context(parent_data)
    context.update(item)
    context.update(followup.get("context") or {})
    spec["url"] = _render_template(spec["url"], context)
    spec["params"] = _render_values(spec.get("params") or {}, context)
    if "json" in spec:
        spec["json"] = _render_values(spec["json"], context)
    if "data" in spec:
        spec["data"] = _render_values(spec["data"], context)
    if "headers" in spec:
        spec["headers"] = _render_values(spec["headers"], context)
    return spec


def _response_context(data: Any) -> dict[str, Any]:
    context: dict[str, Any] = {"response": data}
    if isinstance(data, dict):
        context.update(data)
        nested = data.get("data")
        context["data"] = nested
        if isinstance(nested, dict):
            context.update(nested)
        flat = flatten_json(data)
        for key, value in flat.items():
            safe_key = "".join(char if char.isalnum() else "_" for char in key).strip("_")
            if safe_key:
                context[safe_key] = value
    else:
        context["data"] = data
    return context


def _render_template(value: str, context: dict[str, Any]) -> str:
    names = [field_name for _, field_name, _, _ in Formatter().parse(value) if field_name]
    for name in names:
        if name not in context:
            context[name] = context.get("_item_id", "")
    return value.format(**context)


def _render_values(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _render_template(value, context)
    if isinstance(value, dict):
        return {key: _render_values(child, context) for key, child in value.items()}
    if isinstance(value, list):
        return [_render_values(child, context) for child in value]
    return value


def _set_key_recursive(value: Any, target_key: str, new_value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (new_value if key == target_key else _set_key_recursive(child, target_key, new_value))
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_set_key_recursive(child, target_key, new_value) for child in value]
    return value


def _should_continue(data: Any, records: list[dict[str, Any]], request_spec: dict[str, Any]) -> bool:
    if not records:
        return False
    page_size = request_spec.get("_page_size")
    if page_size and len(records) < int(page_size):
        return False
    text = json.dumps(data, ensure_ascii=False).lower()
    if '"hasnext":false' in text or '"has_next":false' in text:
        return False
    return True


def _decorate_record(item: dict[str, Any], request_spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_url": _source_url(request_spec),
        "crawled_at": utc_now(),
        "raw": item,
        "business_id": find_first(item, ["id", "uuid", "courseId", "projectId", "courseExtendId"]) or stable_hash(json.dumps(item, ensure_ascii=False)),
    }


def _source_url(request_spec: dict[str, Any]) -> str:
    params = request_spec.get("params") or {}
    if not params:
        return request_spec.get("url", "")
    return f"{request_spec.get('url')}?{urlencode(params, doseq=True)}"


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get("business_id") or stable_hash(json.dumps(record, ensure_ascii=False)))
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def write_jsonl_append(path: Path, record: dict[str, Any]) -> None:
    from .storage import append_jsonl

    append_jsonl(path, record)


def classify_exception(exc: Exception) -> str:
    text = str(exc).lower()
    if "timeout" in text:
        return "timeout"
    if "403" in text:
        return "http_403_forbidden"
    if "401" in text:
        return "http_401_unauthorized"
    if "429" in text:
        return "http_429_rate_limited"
    if re_match := __import__("re").search(r"\b5\d\d\b", text):
        return "http_5xx_server_error"
    if "json" in text:
        return "parse_error"
    return "unknown_error"


def _safe_request_headers(headers: dict[str, Any]) -> dict[str, str]:
    blocked = {"authorization", "cookie", "set-cookie", "x-token", "token", "password", "secret"}
    return {
        str(key): str(value)
        for key, value in headers.items()
        if str(key).lower() not in blocked and value not in (None, "")
    }


def _print_dry_run(command: str, targets: list[dict[str, Any]], settings: Settings) -> None:
    preview = {
        "command": command,
        "dry_run": True,
        "max_pages": settings.max_pages,
        "rate_limit": settings.rate_limit,
        "timeout": settings.timeout,
        "retries": settings.retries,
        "user_agent": settings.user_agent,
        "targets": targets,
        "expected_fields": [
            "business_id",
            "title/name/courseName/projectName",
            "category/level/classify/subject",
            "professor/teacher/instructor",
            "university/school/college",
            "description/intro/summary",
            "asset URLs: pdf/jpg/jpeg/png/webp",
        ],
        "will_persist": False,
    }
    sys.stdout.write(json.dumps(preview, ensure_ascii=False, indent=2) + "\n")
