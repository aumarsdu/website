from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .config import (
    ASSET_FIELD_HINTS,
    CATEGORY_KEYWORDS,
    DETAIL_KEYWORDS,
    ID_KEYS,
    LIST_KEYWORDS,
    PAGE_KEYS,
    PAGE_SIZE_KEYS,
    TEXT_FIELD_HINTS,
    CrawlSettings,
    ensure_output_dirs,
)
from .storage import read_jsonl, write_json
from .utils import normalize_url_for_key

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


def analyze_network_logs(settings: CrawlSettings) -> dict[str, Any]:
    ensure_output_dirs(settings)
    network_log_path = settings.discovery_dir / "network_logs.jsonl"
    output_json = settings.discovery_dir / "api_classification.json"
    output_md = settings.discovery_dir / "api_classification.md"
    rows = read_jsonl(network_log_path)
    request_lookup = {
        (row.get("method"), normalize_url_for_key(row.get("url", ""))): row
        for row in rows
        if row.get("event") == "request"
    }
    response_rows = [row for row in rows if row.get("event") == "response"]
    enriched_rows = [enrich_response_with_request(row, request_lookup) for row in response_rows]
    classifications = [classify_response(row) for row in enriched_rows if is_candidate(row)]
    classifications.sort(key=lambda item: (-item["score"], item["endpoint"]))
    payload = {
        "source": str(network_log_path),
        "total_response_events": len(response_rows),
        "classified_apis": classifications,
        "type_counts": dict(Counter(item["suspected_type"] for item in classifications)),
    }
    write_json(output_json, payload)
    output_md.write_text(render_classification_md(payload), encoding="utf-8")
    return payload


def enrich_response_with_request(
    row: dict[str, Any],
    request_lookup: dict[tuple[str | None, str], dict[str, Any]],
) -> dict[str, Any]:
    key = (row.get("method"), normalize_url_for_key(row.get("url", "")))
    request = request_lookup.get(key) or {}
    enriched = dict(row)
    if "post_data" not in enriched:
        enriched["post_data"] = request.get("post_data")
    if "request_headers" not in enriched:
        enriched["request_headers"] = request.get("request_headers", {})
    enriched["had_sensitive_headers"] = bool(enriched.get("had_sensitive_headers") or request.get("had_sensitive_headers"))
    enriched["uses_auth_header"] = bool(enriched.get("uses_auth_header") or request.get("uses_auth_header"))
    enriched["had_sensitive_post_data"] = bool(enriched.get("had_sensitive_post_data") or request.get("had_sensitive_post_data"))
    return enriched


def is_candidate(row: dict[str, Any]) -> bool:
    return bool(row.get("response_json") is not None or row.get("resource_type") in {"xhr", "fetch"})


def classify_response(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("response_json")
    endpoint = row.get("url", "")
    text = json.dumps(data, ensure_ascii=False, default=str) if data is not None else ""
    lowered_blob = f"{endpoint} {text[:20000]}".lower()
    fields = flatten_keys(data)
    field_lowers = {field.lower() for field in fields}
    arrays = find_arrays(data)
    asset_fields = sorted(field for field in fields if any(hint in field.lower() for hint in ASSET_FIELD_HINTS))
    id_fields = sorted(field for field in fields if field.split(".")[-1] in ID_KEYS or field.split(".")[-1].lower().endswith("id"))
    page_params = detect_keys(row.get("query_params", {}), PAGE_KEYS)
    page_size_params = detect_keys(row.get("query_params", {}), PAGE_SIZE_KEYS)
    body = row.get("post_data") or {}
    if isinstance(body, dict):
        page_params.extend(detect_keys(body, PAGE_KEYS))
        page_size_params.extend(detect_keys(body, PAGE_SIZE_KEYS))

    list_score = score_keywords(lowered_blob, LIST_KEYWORDS) + (3 if arrays else 0) + (4 if has_any(field_lowers, {"total", "records", "rows", "page", "pages", "allPage", "currentPage", "courseList"}) else 0)
    if any(path.lower().endswith(("records", "rows", "courselist", "list", "items")) for path in arrays):
        list_score += 3
    detail_score = score_keywords(lowered_blob, DETAIL_KEYWORDS) + score_keywords(" ".join(field_lowers), TEXT_FIELD_HINTS)
    category_score = score_keywords(lowered_blob, CATEGORY_KEYWORDS)
    asset_score = score_keywords(lowered_blob, ASSET_FIELD_HINTS) + len(asset_fields)
    uuid_count = len(UUID_RE.findall(text))

    suspected_type = "other"
    score = max(list_score, detail_score, category_score, asset_score)
    if score == list_score and list_score >= 4:
        suspected_type = "project_list"
    elif score == detail_score and detail_score >= 4:
        suspected_type = "project_detail"
    elif score == category_score and category_score >= 3:
        suspected_type = "category_or_filter"
    elif score == asset_score and asset_score >= 2:
        suspected_type = "asset_resource"

    return {
        "endpoint": row.get("url"),
        "endpoint_without_query": row.get("url", "").split("?", 1)[0],
        "method": row.get("method"),
        "status": row.get("status"),
        "resource_type": row.get("resource_type"),
        "suspected_type": suspected_type,
        "score": score,
        "scores": {
            "list": list_score,
            "detail": detail_score,
            "category": category_score,
            "asset": asset_score,
        },
        "requires_auth": bool(row.get("status") in {401, 403} or row.get("uses_auth_header") or row.get("had_sensitive_post_data")),
        "had_sensitive_headers": bool(row.get("had_sensitive_headers")),
        "uses_auth_header": bool(row.get("uses_auth_header")),
        "had_sensitive_post_data": bool(row.get("had_sensitive_post_data")),
        "has_array": bool(arrays),
        "array_paths": arrays[:20],
        "has_total_or_page": has_any(field_lowers, {"total", "page", "pages", "pageSize".lower(), "records", "rows", "allPage", "currentPage", "allNumber"}),
        "pagination_params": sorted(set(page_params)),
        "page_size_params": sorted(set(page_size_params)),
        "id_fields": id_fields[:30],
        "asset_url_fields": asset_fields[:30],
        "uuid_count": uuid_count,
        "text_field_hits": sorted(field for field in fields if any(hint in field.lower() for hint in TEXT_FIELD_HINTS))[:30],
        "query_params": row.get("query_params", {}),
        "post_data": row.get("post_data"),
        "response_summary": row.get("response_json_summary"),
    }


def flatten_keys(value: Any, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.add(path)
            keys.update(flatten_keys(item, path))
    elif isinstance(value, list):
        for item in value[:3]:
            keys.update(flatten_keys(item, f"{prefix}[]"))
    return keys


def find_arrays(value: Any, prefix: str = "") -> list[str]:
    arrays: list[str] = []
    if isinstance(value, list):
        arrays.append(prefix or "$")
        for item in value[:3]:
            arrays.extend(find_arrays(item, prefix + "[]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            arrays.extend(find_arrays(item, path))
    return arrays


def detect_keys(mapping: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    lowers = {key.lower(): key for key in mapping.keys()}
    return [lowers[key.lower()] for key in keys if key.lower() in lowers]


def score_keywords(blob: str, keywords: set[str] | tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword.lower() in blob)


def has_any(fields: set[str], names: set[str]) -> bool:
    wanted = {name.lower() for name in names}
    return any(field.split(".")[-1].lower() in wanted for field in fields)


def render_classification_md(payload: dict[str, Any]) -> str:
    lines = [
        "# API Classification",
        "",
        f"- source: `{payload.get('source')}`",
        f"- total response events: {payload.get('total_response_events')}",
        f"- type counts: `{payload.get('type_counts')}`",
        "",
    ]
    for idx, item in enumerate(payload.get("classified_apis", []), 1):
        lines.extend(
            [
                f"## {idx}. {item['suspected_type']} - `{item['method']}` {item['endpoint_without_query']}",
                "",
                f"- score: `{item['score']}` / `{item['scores']}`",
                f"- requires auth: `{item['requires_auth']}`",
                f"- has array: `{item['has_array']}`; array paths: `{item['array_paths']}`",
                f"- pagination params: `{item['pagination_params']}`",
                f"- page size params: `{item['page_size_params']}`",
                f"- ID fields: `{item['id_fields']}`",
                f"- asset URL fields: `{item['asset_url_fields']}`",
                f"- UUID count: `{item['uuid_count']}`",
                f"- query params: `{item['query_params']}`",
                f"- post data sample: `{item['post_data']}`",
                "",
            ]
        )
    return "\n".join(lines)
