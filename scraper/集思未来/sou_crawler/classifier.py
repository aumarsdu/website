from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .config import CrawlConfig, ensure_output_dirs
from .utils import ASSET_URL_RE, UUID_RE, iter_jsonl, write_json


LIST_HINTS = ("list", "search", "page", "records", "rows", "total")
DETAIL_HINTS = ("detail", "id", "uuid", "share")
CATEGORY_HINTS = ("category", "classify", "level", "subject")
PROJECT_HINTS = ("project", "course", "sou")
TEXT_FIELDS = (
    "title",
    "name",
    "teacher",
    "instructor",
    "professor",
    "university",
    "major",
    "prerequisite",
    "intro",
    "description",
)
PAGINATION_FIELDS = ("total", "page", "pageSize", "current", "size", "records", "rows")
ID_FIELDS = ("id", "uuid", "projectId", "courseId", "itemId", "detailId")
ASSET_FIELDS = (
    "url",
    "file",
    "pdf",
    "image",
    "poster",
    "cover",
    "syllabus",
    "attachment",
    "oss",
)


@dataclass
class ApiSignature:
    key: str
    url: str
    method: str
    count: int
    query_params: dict[str, list[str]]
    request_body_sample: Any
    response_sample: Any
    response_shape: dict[str, Any]
    headers_sample: dict[str, str]
    request_headers_sample: dict[str, str]
    categories: list[str]
    scores: dict[str, int]
    requires_auth: bool
    is_paginated: bool
    pagination_params: list[str]
    id_fields: list[str]
    asset_url_fields: list[str]


def normalize_api_key(url: str, method: str) -> str:
    parts = urlsplit(url)
    return f"{method.upper()} {parts.scheme}://{parts.netloc}{parts.path}"


def summarize_json(value: Any, max_items: int = 5) -> Any:
    if isinstance(value, dict):
        return {key: summarize_json(inner, max_items) for key, inner in list(value.items())[:max_items]}
    if isinstance(value, list):
        if not value:
            return []
        return [summarize_json(value[0], max_items)]
    return type(value).__name__


def collect_keys(value: Any) -> set[str]:
    keys: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, inner in node.items():
                keys.add(str(key))
                walk(inner)
        elif isinstance(node, list):
            for inner in node[:20]:
                walk(inner)

    walk(value)
    return keys


def contains_array(value: Any) -> bool:
    if isinstance(value, list):
        return True
    if isinstance(value, dict):
        return any(contains_array(inner) for inner in value.values())
    return False


def classify_api(url: str, method: str, body: Any, response: Any) -> tuple[list[str], dict[str, int]]:
    text = " ".join(
        [
            url.lower(),
            method.lower(),
            json.dumps(body, ensure_ascii=False).lower() if body is not None else "",
            json.dumps(response, ensure_ascii=False).lower() if response is not None else "",
        ]
    )
    keys = collect_keys(response)
    lower_keys = {key.lower() for key in keys}
    scores = {
        "分类接口": sum(1 for hint in CATEGORY_HINTS if hint in text),
        "筛选项接口": sum(1 for hint in ("filter", "option", "dict", "tag", "subject") if hint in text),
        "项目列表接口": sum(1 for hint in LIST_HINTS + PROJECT_HINTS if hint in text) + int(contains_array(response)),
        "项目详情接口": sum(1 for hint in DETAIL_HINTS + TEXT_FIELDS if hint in text),
        "附件资源接口": sum(1 for hint in ASSET_FIELDS if hint in text) + int(bool(ASSET_URL_RE.search(text))),
        "其他接口": 1,
    }
    if lower_keys.intersection({"total", "records", "rows", "pages"}):
        scores["项目列表接口"] += 3
    if lower_keys.intersection({field.lower() for field in TEXT_FIELDS}):
        scores["项目详情接口"] += 2
    if lower_keys.intersection({field.lower() for field in ID_FIELDS}):
        scores["项目详情接口"] += 1
        scores["项目列表接口"] += 1
    categories = [
        name for name, score in sorted(scores.items(), key=lambda item: item[1], reverse=True) if score > 1
    ]
    return categories or ["其他接口"], scores


def detect_fields(response: Any, names: tuple[str, ...]) -> list[str]:
    lower_wanted = {name.lower() for name in names}
    return sorted(key for key in collect_keys(response) if key.lower() in lower_wanted)


def detect_asset_fields(response: Any) -> list[str]:
    fields: set[str] = set()

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, inner in node.items():
                child = f"{path}.{key}" if path else str(key)
                if any(hint in key.lower() for hint in ASSET_FIELDS):
                    fields.add(child)
                walk(inner, child)
        elif isinstance(node, list):
            for inner in node[:20]:
                walk(inner, path)
        elif isinstance(node, str) and ASSET_URL_RE.search(node):
            fields.add(path)

    walk(response)
    return sorted(field for field in fields if field)


def analyze_network_logs(config: CrawlConfig) -> list[ApiSignature]:
    log_path = config.discovery_dir / "network_logs.jsonl"
    rows = iter_jsonl(log_path)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("event") == "response" and row.get("is_json"):
            grouped[normalize_api_key(row["url"], row.get("method", "GET"))].append(row)

    signatures: list[ApiSignature] = []
    for key, group in sorted(grouped.items()):
        sample = group[0]
        parsed = urlsplit(sample["url"])
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        response = sample.get("json")
        body = sample.get("post_data_json", sample.get("post_data"))
        categories, scores = classify_api(sample["url"], sample.get("method", "GET"), body, response)
        pagination_params = sorted(
            set(query_params).intersection({"page", "pageNo", "pageNum", "current", "size", "pageSize", "limit"})
            | set(detect_fields(response, PAGINATION_FIELDS))
        )
        signatures.append(
            ApiSignature(
                key=key,
                url=sample["url"],
                method=sample.get("method", "GET"),
                count=len(group),
                query_params=query_params,
                request_body_sample=body,
                response_sample=response,
                response_shape=summarize_json(response),
                headers_sample=sample.get("response_headers", {}),
                request_headers_sample=sample.get("request_headers", {}),
                categories=categories,
                scores=scores,
                requires_auth=_requires_auth(sample),
                is_paginated=bool(pagination_params),
                pagination_params=pagination_params,
                id_fields=detect_fields(response, ID_FIELDS),
                asset_url_fields=detect_asset_fields(response),
            )
        )
    return signatures


def _requires_auth(sample: dict[str, Any]) -> bool:
    status = int(sample.get("status") or 0)
    headers = {key.lower(): value for key, value in sample.get("request_headers", {}).items()}
    return status in {401, 403} or "authorization" in headers or "cookie" in headers


def write_api_outputs(config: CrawlConfig, signatures: list[ApiSignature]) -> None:
    ensure_output_dirs(config)
    as_dicts = [signature.__dict__ for signature in signatures]
    write_json(config.discovery_dir / "api_candidates.json", as_dicts)
    write_json(config.discovery_dir / "api_classification.json", as_dicts)
    (config.discovery_dir / "api_inventory.md").write_text(render_inventory(signatures), encoding="utf-8")
    (config.discovery_dir / "api_classification.md").write_text(render_classification(signatures), encoding="utf-8")


def render_inventory(signatures: list[ApiSignature]) -> str:
    lines = ["# API Inventory", ""]
    for sig in signatures:
        lines.extend(
            [
                f"## `{sig.method}` {urlsplit(sig.url).path}",
                "",
                f"- URL: `{sig.url}`",
                f"- method: `{sig.method}`",
                f"- seen: `{sig.count}`",
                f"- query params: `{', '.join(sig.query_params) or '-'}`",
                f"- post body sample: `{_compact(sig.request_body_sample)}`",
                f"- response shape: `{_compact(sig.response_shape)}`",
                f"- 疑似用途: {', '.join(sig.categories)}",
                f"- 是否需要鉴权: {'是' if sig.requires_auth else '否/未发现'}",
                f"- 是否分页: {'是' if sig.is_paginated else '否/未发现'}",
                f"- 分页参数名称: `{', '.join(sig.pagination_params) or '-'}`",
                f"- 项目 ID 字段名称: `{', '.join(sig.id_fields) or '-'}`",
                f"- 附件 URL 字段名称: `{', '.join(sig.asset_url_fields) or '-'}`",
                "",
            ]
        )
    return "\n".join(lines)


def render_classification(signatures: list[ApiSignature]) -> str:
    counter = Counter(category for sig in signatures for category in sig.categories)
    lines = ["# API Classification", "", "## Summary", ""]
    lines.extend(f"- {name}: {count}" for name, count in counter.most_common())
    lines.append("")
    for sig in sorted(signatures, key=lambda item: max(item.scores.values()), reverse=True):
        lines.extend(
            [
                f"## {', '.join(sig.categories)}",
                "",
                f"- endpoint: `{sig.method} {sig.url}`",
                f"- scores: `{sig.scores}`",
                f"- pagination: `{', '.join(sig.pagination_params) or '-'}`",
                f"- id fields: `{', '.join(sig.id_fields) or '-'}`",
                f"- asset fields: `{', '.join(sig.asset_url_fields) or '-'}`",
                "",
            ]
        )
    return "\n".join(lines)


def _compact(value: Any, limit: int = 500) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = re.sub(r"\s+", " ", text)
    return text[:limit] + ("..." if len(text) > limit else "")

