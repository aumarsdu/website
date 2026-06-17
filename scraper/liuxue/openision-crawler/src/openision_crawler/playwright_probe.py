from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .config import Settings
from .sanitize import redact_headers, sanitize_text, sanitize_url
from .storage import Storage


AUTH_PATH_MARKERS = ("/auth", "fc_auth", "/login", "/logout", "/token")


def safe_filename(route: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "_", route.strip("/")) or "home"
    return name[:120] + ".html"


def append_jsonl(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def run_playwright_probe(settings: Settings, storage: Storage, logger) -> None:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError("Playwright is not installed. Run `pip install -e .[probe]` and `playwright install chromium`.") from exc

    storage.init_db()
    run_id = storage.start_run("playwright-probe", "browser XHR/fetch probe")
    out_dir = settings.output_dir / "probe"
    html_dir = out_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    network_log = out_dir / "network.jsonl"

    def same_site(url: str) -> bool:
        return urlsplit(url).netloc in settings.allowed_domains

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.headless)
            context_kwargs = {
                "viewport": {"width": 1440, "height": 1000},
                "user_agent": settings.user_agent,
            }
            state_path = settings.storage_state_path
            if settings.enable_login_state and state_path.exists():
                context_kwargs["storage_state"] = str(state_path)
            elif settings.enable_login_state:
                logger.info("storage_state missing; continuing public probe")
            context = browser.new_context(**context_kwargs)
            page = context.new_page()

            def handle_response(response) -> None:
                request = response.request
                if request.resource_type not in {"xhr", "fetch"}:
                    return
                if not same_site(response.url):
                    return
                content_type = response.headers.get("content-type", "")
                body_sample = ""
                lower_url = response.url.lower()
                is_auth = any(marker in lower_url for marker in AUTH_PATH_MARKERS)
                if is_auth:
                    body_sample = "[REDACTED_AUTH_RESPONSE]"
                else:
                    try:
                        if any(token in content_type for token in ("json", "text", "javascript")):
                            body_sample = sanitize_text(response.text()[:50000])
                    except Exception as exc:
                        body_sample = f"[body read failed: {exc!r}]"
                item = {
                    "timestamp": time.time(),
                    "page_url": sanitize_url(page.url),
                    "request_url": sanitize_url(response.url),
                    "method": request.method,
                    "status": response.status,
                    "resource_type": request.resource_type,
                    "request_headers": redact_headers(request.headers),
                    "response_headers": redact_headers(response.headers),
                    "post_data": request.post_data,
                    "response_content_type": content_type,
                    "response_body_sample": body_sample,
                    "response_body_sha256": hashlib.sha256(body_sample.encode("utf-8")).hexdigest() if body_sample else None,
                    "response_body_length": len(body_sample),
                }
                append_jsonl(network_log, item)
                body_hash = storage.save_raw_response(
                    run_id=run_id,
                    method=request.method,
                    url=sanitize_url(response.url),
                    status_code=response.status,
                    content_type=content_type,
                    body_text=body_sample,
                )
                storage.upsert_endpoint(request.method, urlsplit(response.url).path, "auth" if is_auth else "unknown", body_hash)

            page.on("response", handle_response)

            for route in settings.initial_paths[: settings.max_probe_pages]:
                url = urljoin(settings.base_url, route)
                logger.info("visiting %s", sanitize_url(url))
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                except PlaywrightTimeoutError:
                    logger.warning("timeout while visiting %s", sanitize_url(url))
                for _ in range(6):
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(800)
                for label in ("加载更多", "更多", "下一页", "Next", "Load more"):
                    try:
                        locator = page.get_by_text(label, exact=False)
                        if locator.count() > 0:
                            locator.first.click(timeout=1500)
                            page.wait_for_timeout(1200)
                    except Exception:
                        pass
                html = sanitize_text(page.content())
                (html_dir / safe_filename(route)).write_text(html, encoding="utf-8")
            browser.close()
        storage.finish_run(run_id, "completed")
    except Exception:
        storage.finish_run(run_id, "failed")
        raise


def run_login(settings: Settings, logger) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError("Playwright is not installed. Run `pip install -e .[probe]` and `playwright install chromium`.") from exc

    settings.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=settings.user_agent)
        page = context.new_page()
        page.goto(settings.base_url, wait_until="networkidle", timeout=60000)
        logger.info("Complete login in the browser, then press Enter here.")
        input()
        context.storage_state(path=str(settings.storage_state_path))
        browser.close()
