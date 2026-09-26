from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .classifier import analyze_network_logs, write_api_outputs
from .config import CrawlConfig, ensure_output_dirs
from .utils import append_jsonl, redact_headers, utc_now_iso

LOGGER = logging.getLogger(__name__)


async def discover_apis(config: CrawlConfig, headless: bool = True) -> None:
    ensure_output_dirs(config)
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed. Run: python -m pip install -e . && playwright install chromium") from exc

    log_path = config.discovery_dir / "network_logs.jsonl"
    if log_path.exists():
        log_path.unlink()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=config.user_agent,
            extra_http_headers={"User-Agent": config.user_agent},
        )
        page = await context.new_page()
        request_meta: dict[str, dict[str, Any]] = {}

        async def on_request(request: Any) -> None:
            post_data = request.post_data
            post_json = None
            if post_data:
                try:
                    post_json = json.loads(post_data)
                except json.JSONDecodeError:
                    post_json = None
            parsed = urlsplit(request.url)
            item = {
                "event": "request",
                "ts": utc_now_iso(),
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "query_params": parse_qs(parsed.query, keep_blank_values=True),
                "request_headers": redact_headers(await request.all_headers()),
                "post_data": post_data,
                "post_data_json": post_json,
            }
            request_meta[str(id(request))] = item
            append_jsonl(log_path, item)

        async def on_response(response: Any) -> None:
            request = response.request
            headers = redact_headers(response.headers)
            content_type = headers.get("content-type", headers.get("Content-Type", ""))
            is_json = "json" in content_type.lower()
            payload = None
            if is_json:
                try:
                    payload = await response.json()
                except Exception:
                    payload = None
            req_item = request_meta.get(str(id(request)), {})
            parsed = urlsplit(response.url)
            item = {
                "event": "response",
                "ts": utc_now_iso(),
                "url": response.url,
                "method": request.method,
                "status": response.status,
                "ok": response.ok,
                "resource_type": request.resource_type,
                "query_params": parse_qs(parsed.query, keep_blank_values=True),
                "is_fetch_xhr": request.resource_type in {"fetch", "xhr"},
                "is_json": is_json or payload is not None,
                "request_headers": req_item.get("request_headers", {}),
                "response_headers": headers,
                "post_data": req_item.get("post_data"),
                "post_data_json": req_item.get("post_data_json"),
                "json": payload,
            }
            append_jsonl(log_path, item)

        page.on("request", on_request)
        page.on("response", on_response)

        for entry in config.discovery_entries:
            LOGGER.info("discovering %s", entry)
            try:
                await page.goto(entry, wait_until="networkidle", timeout=int(config.timeout * 1000))
                await page.wait_for_timeout(config.discovery_wait_ms)
            except Exception as exc:
                append_jsonl(
                    log_path,
                    {
                        "event": "navigation_error",
                        "ts": utc_now_iso(),
                        "url": entry,
                        "error": type(exc).__name__,
                        "message": str(exc),
                    },
                )
                LOGGER.warning("navigation failed: %s %s", entry, exc)

        await context.close()
        await browser.close()

    signatures = analyze_network_logs(config)
    write_api_outputs(config, signatures)
