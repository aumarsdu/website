from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse
import asyncio
import json
import logging
import re

from .config import Settings
from .storage import append_jsonl, iter_jsonl, write_json
from .utils import find_asset_urls, utc_now

LOGGER = logging.getLogger(__name__)
STATIC_ENDPOINT_RE = re.compile(
    r"""(?P<quote>['"])(?P<path>(?:https?://[^'"]+|/[^'"]*?)(?:api|course|territory|imageClient|pubController|Attachment|Poster)[^'"]*?)(?P=quote)""",
    re.I,
)
API_BASE_RE = re.compile(r"""baseURL\s*:\s*['"](?P<base>https?://[^'"]+)['"]""", re.I)


async def discover_network(settings: Settings) -> None:
    if settings.dry_run:
        print(
            json.dumps(
                {
                    "command": "discover",
                    "dry_run": True,
                    "entry_urls": settings.entry_urls,
                    "will_open_browser": False,
                    "will_persist": False,
                    "planned_outputs": [
                        str(settings.discovery_dir / "network_logs.jsonl"),
                        str(settings.discovery_dir / "api_candidates.json"),
                        str(settings.discovery_dir / "api_inventory.md"),
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise SystemExit("Playwright 未安装。请先运行 `python -m pip install -r requirements.txt && python -m playwright install chromium`。") from exc

    settings.ensure_dirs()
    network_path = settings.discovery_dir / "network_logs.jsonl"
    if network_path.exists():
        network_path.unlink()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=settings.user_agent)
        page = await context.new_page()

        pending: dict[str, dict[str, Any]] = {}
        static_candidates: dict[str, dict[str, Any]] = {}
        event_tasks: set[asyncio.Task[Any]] = set()

        def track_task(coro: Any) -> None:
            task = asyncio.create_task(coro)
            event_tasks.add(task)
            task.add_done_callback(event_tasks.discard)

        async def on_request(request: Any) -> None:
            resource_type = request.resource_type
            if resource_type not in {"xhr", "fetch"} and not _looks_like_api(request.url):
                return
            pending[request.url + "|" + request.method] = {
                "discovered_at": utc_now(),
                "event": "request",
                "url": request.url,
                "method": request.method,
                "resource_type": resource_type,
                "query_params": parse_qs(urlparse(request.url).query),
                "request_headers": _redact_headers(await request.all_headers()),
                "post_data": _safe_post_data(request.post_data),
            }

        async def on_response(response: Any) -> None:
            request = response.request
            resource_type = request.resource_type
            content_type = response.headers.get("content-type", "")
            if resource_type == "script" or "javascript" in content_type.lower():
                try:
                    script_text = await response.text()
                    for item in extract_static_endpoints(script_text, response.url):
                        static_candidates[item["url"]] = item
                except Exception:
                    pass
                return
            if resource_type not in {"xhr", "fetch"} and "json" not in content_type.lower():
                return
            body_summary: dict[str, Any] = {"is_json": False}
            body_text_sample = None
            if "json" in content_type.lower():
                try:
                    data = await response.json()
                    body_summary = summarize_json(data)
                except Exception as exc:  # noqa: BLE001 - discovery should continue.
                    body_summary = {"is_json": False, "json_error": str(exc)}
            else:
                try:
                    body_text = await response.text()
                    body_text_sample = body_text[:1000]
                except Exception:
                    body_text_sample = None

            request_key = request.url + "|" + request.method
            record = pending.pop(request_key, {})
            record.update(
                {
                    "event": "response",
                    "url": response.url,
                    "method": request.method,
                    "resource_type": resource_type,
                    "status": response.status,
                    "response_headers": _redact_headers(response.headers),
                    "content_type": content_type,
                    "body_summary": body_summary,
                    "body_text_sample": body_text_sample,
                    "requires_auth": response.status in {401, 403},
                }
            )
            append_jsonl(network_path, record)

        page.on("request", lambda request: track_task(on_request(request)))
        page.on("response", lambda response: track_task(on_response(response)))

        for url in settings.entry_urls:
            if not settings.is_allowed_url(url):
                LOGGER.warning("跳过非授权入口 URL: %s", url)
                continue
            LOGGER.info("发现入口: %s", url)
            await page.goto(url, wait_until="networkidle", timeout=int(settings.timeout * 1000))
            await page.wait_for_timeout(2500)

        if event_tasks:
            await asyncio.gather(*event_tasks, return_exceptions=True)
        await context.close()
        await browser.close()

    candidates = build_api_candidates(settings)
    write_json(settings.discovery_dir / "api_candidates.json", candidates)
    static_items = sorted(static_candidates.values(), key=lambda item: item["url"])
    write_json(settings.discovery_dir / "static_api_candidates.json", static_items)
    write_inventory_md(settings.discovery_dir / "api_inventory.md", candidates)
    write_static_inventory_md(settings.discovery_dir / "static_api_inventory.md", static_items)
    LOGGER.info("网络发现完成: %s", network_path)


def build_api_candidates(settings: Settings) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in iter_jsonl(settings.discovery_dir / "network_logs.jsonl") or []:
        parsed = urlparse(record.get("url", ""))
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        grouped[(record.get("method", "GET"), clean_url)].append(record)

    candidates: list[dict[str, Any]] = []
    for (method, url), records in sorted(grouped.items()):
        first = records[0]
        statuses = sorted({rec.get("status") for rec in records if rec.get("status") is not None})
        summaries = [rec.get("body_summary", {}) for rec in records]
        merged_summary = merge_summaries(summaries)
        candidates.append(
            {
                "method": method,
                "url": url,
                "sample_full_url": first.get("url"),
                "query_params": first.get("query_params", {}),
                "post_data_sample": first.get("post_data"),
                "status_codes": statuses,
                "content_type": first.get("content_type"),
                "response_summary": merged_summary,
                "requires_auth": any(rec.get("requires_auth") for rec in records),
                "seen_count": len(records),
                "post_data_samples": _unique_samples([rec.get("post_data") for rec in records]),
                "query_param_samples": _unique_samples([rec.get("query_params") for rec in records]),
                "asset_fields": merged_summary.get("asset_like_fields", []),
            }
        )
    return candidates


def summarize_json(data: Any, max_keys: int = 40) -> dict[str, Any]:
    paths: list[str] = []
    array_paths: list[str] = []
    asset_fields: set[str] = set()
    scalar_samples: dict[str, Any] = {}

    def walk(value: Any, path: str = "$") -> None:
        if len(paths) < max_keys:
            paths.append(path)
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if isinstance(child, str) and find_asset_urls(child):
                    asset_fields.add(child_path)
                walk(child, child_path)
        elif isinstance(value, list):
            array_paths.append(path)
            if value:
                walk(value[0], f"{path}[]")
        else:
            if len(scalar_samples) < 12:
                scalar_samples[path] = value

    walk(data)
    return {
        "is_json": True,
        "root_type": type(data).__name__,
        "paths_sample": paths,
        "array_paths": sorted(set(array_paths)),
        "asset_like_fields": sorted(asset_fields),
        "scalar_samples": scalar_samples,
        "text_size": len(json.dumps(data, ensure_ascii=False)),
    }


def merge_summaries(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"is_json": any(item.get("is_json") for item in summaries)}
    for key in ("paths_sample", "array_paths", "asset_like_fields"):
        merged: set[str] = set()
        for item in summaries:
            merged.update(item.get(key, []) or [])
        out[key] = sorted(merged)[:80]
    roots = sorted({item.get("root_type") for item in summaries if item.get("root_type")})
    out["root_types"] = roots
    return out


def _unique_samples(values: list[Any], limit: int = 5) -> list[Any]:
    samples: list[Any] = []
    seen: set[str] = set()
    for value in values:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if encoded in seen:
            continue
        seen.add(encoded)
        samples.append(value)
        if len(samples) >= limit:
            break
    return samples


def write_inventory_md(path: Any, candidates: list[dict[str, Any]]) -> None:
    lines = ["# API Inventory", "", "由 Playwright Network 发现自动生成，需人工复核接口用途和分页参数。", ""]
    for idx, item in enumerate(candidates, 1):
        summary = item.get("response_summary", {})
        purpose = guess_purpose(item)
        pagination = guess_pagination(item)
        lines.extend(
            [
                f"## {idx}. `{item['method']} {item['url']}`",
                "",
                f"- sample URL: `{item.get('sample_full_url')}`",
                f"- query params: `{json.dumps(item.get('query_params', {}), ensure_ascii=False)}`",
                f"- post body example: `{item.get('post_data_sample')}`",
                f"- post body samples observed: `{len(item.get('post_data_samples', []))}`",
                f"- status codes: `{item.get('status_codes')}`",
                f"- requires auth: `{item.get('requires_auth')}`",
                f"- suspected purpose: `{purpose}`",
                f"- is paginated: `{pagination['is_paginated']}`",
                f"- pagination params: `{', '.join(pagination['params']) or 'unknown'}`",
                f"- item id field candidates: `{', '.join(guess_fields(summary, ['id', 'uuid', 'courseId', 'projectId', 'courseExtendId'])) or 'unknown'}`",
                f"- asset URL field candidates: `{', '.join(item.get('asset_fields', [])) or 'unknown'}`",
                f"- response structure: root `{summary.get('root_types')}`, arrays `{summary.get('array_paths')}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def extract_static_endpoints(script_text: str, source_url: str) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    api_bases = sorted(set(API_BASE_RE.findall(script_text)))
    for match in STATIC_ENDPOINT_RE.finditer(script_text):
        raw_path = match.group("path")
        if raw_path.startswith("//") or raw_path in api_bases:
            continue
        full_urls = [raw_path] if raw_path.startswith("http") else []
        if raw_path.startswith("/") and api_bases:
            full_urls.extend(f"{base.rstrip('/')}{raw_path}" for base in api_bases)
        elif not raw_path.startswith("http"):
            full_urls.append(urljoin(source_url, raw_path))
        for full_url in full_urls:
            parsed = urlparse(full_url)
            if parsed.scheme not in {"http", "https"}:
                continue
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            candidates[clean_url] = {
                "url": clean_url,
                "raw": raw_path,
                "source": source_url,
                "query_params": parse_qs(parsed.query),
            }
    return list(candidates.values())


def write_static_inventory_md(path: Any, candidates: list[dict[str, Any]]) -> None:
    lines = ["# Static API Inventory", "", "从公开 JavaScript bundle 中抽取，作为 Network discovery 的补充。", ""]
    for idx, item in enumerate(candidates, 1):
        lines.extend(
            [
                f"## {idx}. `{item['url']}`",
                "",
                f"- raw: `{item.get('raw')}`",
                f"- source: `{item.get('source')}`",
                f"- query params: `{json.dumps(item.get('query_params', {}), ensure_ascii=False)}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def guess_purpose(item: dict[str, Any]) -> str:
    text = json.dumps(item, ensure_ascii=False).lower()
    if any(token in text for token in ["detail", "info", "courseextendid", "projectid"]):
        return "项目详情接口"
    if any(token in text for token in ["list", "page", "records", "rows", "total", "search"]):
        return "项目列表接口"
    if any(token in text for token in ["category", "classify", "level", "subject"]):
        return "分类/筛选项接口"
    if any(token in text for token in ["pdf", "jpg", "png", "jpeg", "webp", "oss-cn", "aliyuncs"]):
        return "附件资源接口"
    return "其他接口"


def guess_pagination(item: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(item, ensure_ascii=False).lower()
    params = [name for name in ["page", "pageNo", "pageNum", "current", "pageSize", "size", "limit"] if name.lower() in text]
    return {"is_paginated": bool(params or any(k in text for k in ["total", "records", "rows"])), "params": params}


def guess_fields(summary: dict[str, Any], names: list[str]) -> list[str]:
    text_paths = summary.get("paths_sample", []) + summary.get("array_paths", [])
    found: list[str] = []
    for path in text_paths:
        leaf = path.rsplit(".", 1)[-1].replace("[]", "")
        if leaf in names:
            found.append(path)
    return sorted(set(found))


def _looks_like_api(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return any(token in path for token in ["/api/", "/app/", "/prod-api/", "list", "detail", "course", "project"])


def _safe_post_data(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value[:2000]


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    blocked = {"authorization", "cookie", "set-cookie", "x-token", "token"}
    return {key: ("<redacted>" if key.lower() in blocked else value) for key, value in headers.items()}
