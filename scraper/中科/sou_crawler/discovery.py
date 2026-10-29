from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from .config import CrawlSettings, DEFAULT_ENTRY_URLS, ensure_output_dirs
from .storage import write_json
from .utils import (
    compact_json_summary,
    normalize_url_for_key,
    now_iso,
    parse_post_data,
    query_params,
    contains_sensitive_key,
    headers_have_auth_indicator,
    redact_headers,
    redact_obj,
)

logger = logging.getLogger(__name__)


async def run_discovery(
    settings: CrawlSettings,
    entry_urls: list[str] | None = None,
    headed: bool = False,
    interactive: bool = False,
    wait_ms: int = 6000,
    max_body_bytes: int = 800_000,
) -> dict[str, Any]:
    ensure_output_dirs(settings)
    entries = entry_urls or DEFAULT_ENTRY_URLS
    network_log_path = settings.discovery_dir / "network_logs.jsonl"
    candidates_path = settings.discovery_dir / "api_candidates.json"
    inventory_path = settings.discovery_dir / "api_inventory.md"
    network_log_path.write_text("", encoding="utf-8")

    logs: list[dict[str, Any]] = []

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed. Run: pip install -r requirements.txt && playwright install chromium") from exc

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        context = await browser.new_context(
            user_agent=settings.user_agent,
            ignore_https_errors=False,
            extra_http_headers={"Accept": "application/json,text/plain,*/*"},
        )
        page = await context.new_page()

        async def persist(event: dict[str, Any]) -> None:
            logs.append(event)
            with network_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

        async def on_request(request: Any) -> None:
            raw_headers = await request.all_headers()
            headers, had_sensitive = redact_headers(raw_headers)
            post_data_error = None
            try:
                post_data = parse_post_data(request.post_data)
            except UnicodeDecodeError as exc:
                post_data = "<non-text-payload>"
                post_data_error = type(exc).__name__
            event = {
                "event": "request",
                "timestamp": now_iso(),
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "query_params": query_params(request.url),
                "request_headers": headers,
                "had_sensitive_headers": had_sensitive,
                "uses_auth_header": headers_have_auth_indicator(raw_headers),
                "had_sensitive_post_data": contains_sensitive_key(post_data),
                "post_data": post_data,
            }
            if post_data_error:
                event["post_data_error"] = post_data_error
            await persist(event)

        async def on_response(response: Any) -> None:
            request = response.request
            headers, had_sensitive = redact_headers(response.headers)
            event: dict[str, Any] = {
                "event": "response",
                "timestamp": now_iso(),
                "url": response.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "status": response.status,
                "query_params": query_params(response.url),
                "response_headers": headers,
                "had_sensitive_headers": had_sensitive,
                "uses_auth_header": False,
                "content_type": response.headers.get("content-type", ""),
            }
            content_type = event["content_type"].lower()
            if "json" in content_type or request.resource_type in {"xhr", "fetch"}:
                try:
                    text = await response.text()
                    event["body_size"] = len(text.encode("utf-8"))
                    if event["body_size"] <= max_body_bytes:
                        parsed = json.loads(text)
                        event["response_json"] = redact_obj(parsed)
                        event["response_json_summary"] = compact_json_summary(parsed)
                    else:
                        event["body_truncated"] = True
                except Exception as exc:  # Playwright can fail on redirects/cached opaque responses.
                    event["body_error"] = type(exc).__name__
            await persist(event)

        pending_tasks: set[asyncio.Task[Any]] = set()

        def schedule(coro: Any) -> None:
            task = asyncio.create_task(coro)
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)

        page.on("request", lambda request: schedule(on_request(request)))
        page.on("response", lambda response: schedule(on_response(response)))

        for entry in entries:
            logger.info("opening entry url", extra={"extra": {"url": entry}})
            try:
                await page.goto(entry, wait_until="networkidle", timeout=int(settings.timeout * 1000))
            except Exception as exc:
                await persist(
                    {
                        "event": "navigation_error",
                        "timestamp": now_iso(),
                        "url": entry,
                        "error": type(exc).__name__,
                        "message": str(exc),
                    }
                )
            await _auto_scroll(page)
            await page.wait_for_timeout(wait_ms)
            if interactive:
                input(f"Opened {entry}. Interact in the browser, then press Enter to continue...")
            if pending_tasks:
                await asyncio.gather(*list(pending_tasks), return_exceptions=True)

        if pending_tasks:
            await asyncio.gather(*list(pending_tasks), return_exceptions=True)
        await context.close()
        await browser.close()

    candidates = build_api_candidates(logs)
    write_json(candidates_path, candidates)
    inventory_path.write_text(render_api_inventory(candidates), encoding="utf-8")
    return {
        "network_logs": str(network_log_path),
        "api_candidates": str(candidates_path),
        "api_inventory": str(inventory_path),
        "events": len(logs),
        "candidates": len(candidates),
    }


async def _auto_scroll(page: Any) -> None:
    await page.evaluate(
        """
        async () => {
          await new Promise((resolve) => {
            let total = 0;
            const step = 500;
            const timer = setInterval(() => {
              window.scrollBy(0, step);
              total += step;
              if (total >= Math.max(document.body.scrollHeight, 1500)) {
                clearInterval(timer);
                window.scrollTo(0, 0);
                resolve();
              }
            }, 180);
          });
        }
        """
    )


def build_api_candidates(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    request_samples: dict[tuple[str, str], dict[str, Any]] = {}
    for event in logs:
        if event.get("event") == "request":
            key = (event.get("method", "GET"), normalize_url_for_key(event.get("url", "")))
            request_samples[key] = event

    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    status_counts: dict[tuple[str, str], defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    for event in logs:
        if event.get("event") != "response":
            continue
        if not (event.get("response_json") is not None or event.get("resource_type") in {"xhr", "fetch"}):
            continue
        method = event.get("method", "GET")
        endpoint = normalize_url_for_key(event.get("url", ""))
        key = (method, endpoint)
        bucket = buckets.setdefault(
            key,
            {
                "method": method,
                "endpoint": endpoint,
                "sample_url": event.get("url"),
                "resource_types": sorted({event.get("resource_type")}),
                "query_params": event.get("query_params", {}),
                "post_data": (request_samples.get(key) or {}).get("post_data"),
                "request_headers": (request_samples.get(key) or {}).get("request_headers", {}),
                "had_sensitive_headers": bool(event.get("had_sensitive_headers") or (request_samples.get(key) or {}).get("had_sensitive_headers")),
                "uses_auth_header": bool((request_samples.get(key) or {}).get("uses_auth_header")),
                "had_sensitive_post_data": bool((request_samples.get(key) or {}).get("had_sensitive_post_data")),
                "response_headers": event.get("response_headers", {}),
                "content_type": event.get("content_type"),
                "response_json_summary": event.get("response_json_summary"),
                "sample_response_json": event.get("response_json"),
                "count": 0,
            },
        )
        bucket["count"] += 1
        status_counts[key][str(event.get("status"))] += 1

    candidates = []
    for key, bucket in buckets.items():
        bucket["status_counts"] = dict(status_counts[key])
        bucket["requires_auth"] = any(status in bucket["status_counts"] for status in ("401", "403")) or bucket["uses_auth_header"] or bucket["had_sensitive_post_data"]
        candidates.append(bucket)
    candidates.sort(key=lambda item: (-item["count"], item["endpoint"]))
    return candidates


def render_api_inventory(candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# API Inventory",
        "",
        "Generated from Playwright network discovery. Sensitive header and payload fields are redacted.",
        "",
    ]
    for idx, item in enumerate(candidates, 1):
        summary = item.get("response_json_summary")
        lines.extend(
            [
                f"## {idx}. `{item.get('method')}` {item.get('endpoint')}",
                "",
                f"- sample URL: `{item.get('sample_url')}`",
                f"- count: {item.get('count')}",
                f"- status: `{item.get('status_counts')}`",
                f"- query params: `{item.get('query_params') or {}}`",
                f"- post body sample: `{item.get('post_data')}`",
                f"- requires auth: `{item.get('requires_auth')}`",
                f"- resource types: `{item.get('resource_types')}`",
                "- suspected usage: to be classified by `python -m sou_crawler analyze-apis`",
                "- pagination: unknown before classification",
                "- page params: unknown before classification",
                "- item ID field: unknown before classification",
                "- asset URL fields: unknown before classification",
                "- response structure summary:",
                "",
                "```json",
                json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                "```",
                "",
            ]
        )
    return "\n".join(lines)
