from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import parse_qs, urlparse
import asyncio
import json
import logging
import re

from .config import Settings, canonicalize_url
from .fetcher import Fetcher
from .storage import append_jsonl, iter_jsonl, write_json
from .utils import utc_now

LOGGER = logging.getLogger(__name__)
API_HINT_RE = re.compile(r"""['"](?P<url>(?:https?://[^'"]+|/[^'"]*?)(?:api|search|project|program|article|news|course|graphql)[^'"]*)['"]""", re.I)


async def check_site(settings: Settings) -> None:
    plan = {
        "target": settings.base_url,
        "search_url": settings.search_url,
        "user_agent": settings.user_agent,
        "allowed_hosts": ["www.dianedu.com", "dianedu.com"],
        "denied_hosts": ["admin.dianedu.com"],
        "dry_run": settings.dry_run,
    }
    if settings.dry_run:
        write_json(settings.reports_dir / "check_site_plan.json", plan)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    fetcher = Fetcher(settings)
    rows: list[dict[str, Any]] = []
    try:
        for url in [settings.base_url, settings.search_url, settings.base_url.rstrip("/") + "/robots.txt", settings.base_url.rstrip("/") + "/sitemap.xml"]:
            result = await fetcher.get(url)
            rows.append(
                {
                    "url": url,
                    "final_url": result.final_url,
                    "status_code": result.status_code,
                    "content_type": result.content_type,
                    "error": result.error.model_dump() if result.error else None,
                    "checked_at": utc_now(),
                }
            )
    finally:
        await fetcher.close()
    write_json(settings.reports_dir / "check_site.json", rows)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


async def discover_static(settings: Settings) -> None:
    if settings.dry_run:
        print(json.dumps({"command": "discover-static", "entry_urls": settings.allowed_entry_urls(), "will_fetch": False}, ensure_ascii=False, indent=2))
        return
    fetcher = Fetcher(settings)
    pages: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    api_candidates: dict[str, dict[str, Any]] = {}
    try:
        for url in settings.allowed_entry_urls() + [settings.base_url.rstrip("/") + "/robots.txt", settings.base_url.rstrip("/") + "/sitemap.xml"]:
            result = await fetcher.get(url)
            if result.error:
                errors.append(result.error.model_dump())
                continue
            text = result.text or ""
            if "html" in (result.content_type or "").lower():
                from .parser import parse_page

                page = parse_page(text, result.final_url, result.content_type, result.status_code).model_dump()
                pages.append(page)
                append_jsonl(settings.raw_dir / "pages_raw.jsonl", {**page, "raw_html_path": save_raw_html(settings, page["canonical_url"], text)})
            for candidate in extract_api_candidates(text, result.final_url):
                api_candidates[candidate["url"]] = candidate
    finally:
        await fetcher.close()
    write_json(settings.discovery_dir / "static_pages.json", pages)
    write_json(settings.discovery_dir / "static_api_candidates.json", sorted(api_candidates.values(), key=lambda item: item["url"]))
    write_json(settings.reports_dir / "discover_static_errors.json", errors)
    write_inventory(settings.discovery_dir / "static_inventory.md", pages, list(api_candidates.values()))


async def discover_browser(settings: Settings) -> None:
    if settings.dry_run:
        print(json.dumps({"command": "discover-browser", "entry_urls": settings.allowed_entry_urls(), "will_open_browser": False}, ensure_ascii=False, indent=2))
        return
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise SystemExit("Playwright 未安装。请运行 `python -m pip install -r requirements.txt && python -m playwright install chromium`。") from exc

    network_path = settings.discovery_dir / "network_logs.jsonl"
    if network_path.exists():
        network_path.unlink()
    observations: list[dict[str, Any]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=settings.user_agent)
        page = await context.new_page()
        pending: dict[str, dict[str, Any]] = {}
        tasks: set[asyncio.Task[Any]] = set()

        def track(coro: Any) -> None:
            task = asyncio.create_task(coro)
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        async def on_request(request: Any) -> None:
            if not settings.is_allowed_url(request.url):
                return
            if request.resource_type not in {"xhr", "fetch", "document"} and not looks_like_api(request.url):
                return
            pending[request.url + "|" + request.method] = {
                "method": request.method,
                "url": request.url,
                "resource_type": request.resource_type,
                "observed_at": utc_now(),
                "query_params": parse_qs(urlparse(request.url).query),
                "post_data_present": bool(request.post_data),
                "post_data": request.post_data[:4000] if request.post_data else None,
            }

        async def on_response(response: Any) -> None:
            request = response.request
            if not settings.is_allowed_url(response.url):
                return
            content_type = response.headers.get("content-type", "")
            if request.resource_type not in {"xhr", "fetch", "document"} and "json" not in content_type.lower():
                return
            record = pending.pop(request.url + "|" + request.method, {})
            body_summary: dict[str, Any] = {}
            if "json" in content_type.lower():
                try:
                    body_summary = summarize_json(await response.json())
                except Exception as exc:  # noqa: BLE001
                    body_summary = {"json_error": str(exc)}
            elif request.resource_type in {"xhr", "fetch"}:
                try:
                    text = await response.text()
                    body_summary = {
                        "root_type": "text",
                        "bytes": len(text),
                        "text_sample": text[:4000],
                    }
                except Exception as exc:  # noqa: BLE001
                    body_summary = {"text_error": str(exc)}
            record.update(
                {
                    "method": request.method,
                    "url": response.url,
                    "status_code": response.status,
                    "resource_type": request.resource_type,
                    "content_type": content_type,
                    "observed_at": record.get("observed_at") or utc_now(),
                    "requires_auth": response.status in {401, 403},
                    "response_summary": body_summary,
                }
            )
            observations.append(record)
            append_jsonl(network_path, record)

        page.on("request", lambda request: track(on_request(request)))
        page.on("response", lambda response: track(on_response(response)))

        for url in settings.allowed_entry_urls():
            LOGGER.info("浏览器发现入口: %s", url)
            await page.goto(url, wait_until="networkidle", timeout=int(settings.timeout * 1000))
            await safe_discover_interactions(page)
            await page.wait_for_timeout(1500)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await context.close()
        await browser.close()

    write_json(settings.discovery_dir / "api_candidates.json", build_api_candidates(observations))
    write_api_inventory(settings.discovery_dir / "api_inventory.md", build_api_candidates(observations))


def analyze_apis(settings: Settings) -> None:
    records = list(iter_jsonl(settings.discovery_dir / "network_logs.jsonl"))
    candidates = build_api_candidates(records)
    write_json(settings.discovery_dir / "api_candidates.json", candidates)
    write_api_inventory(settings.discovery_dir / "api_inventory.md", candidates)


def extract_api_candidates(text: str, source_url: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for match in API_HINT_RE.finditer(text or ""):
        raw = match.group("url")
        url = canonicalize_url(raw, source_url)
        out.append({"url": url, "source_url": source_url, "discovered_at": utc_now(), "method": "GET", "source": "static"})
    return out


def looks_like_api(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in ("api", "search", "project", "program", "article", "news", "course", "graphql"))


def summarize_json(data: Any) -> dict[str, Any]:
    paths: list[str] = []
    arrays: list[str] = []

    def walk(value: Any, path: str = "$") -> None:
        if len(paths) < 80:
            paths.append(path)
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            arrays.append(path)
            if value:
                walk(value[0], f"{path}[]")

    walk(data)
    encoded = json.dumps(data, ensure_ascii=False)
    return {"root_type": type(data).__name__, "paths_sample": paths, "array_paths": sorted(set(arrays)), "bytes": len(encoded)}


def build_api_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        parsed = urlparse(record.get("url", ""))
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        grouped[(record.get("method") or "GET", clean_url)].append(record)
    candidates: list[dict[str, Any]] = []
    for (method, url), items in sorted(grouped.items()):
        candidates.append(
            {
                "method": method,
                "url": url,
                "seen_count": len(items),
                "sample_full_url": items[0].get("url"),
                "status_codes": sorted({item.get("status_code") for item in items if item.get("status_code") is not None}),
                "content_types": sorted({item.get("content_type") for item in items if item.get("content_type")}),
                "requires_auth": any(item.get("requires_auth") for item in items),
                "query_param_samples": [item.get("query_params") for item in items[:3] if item.get("query_params")],
                "response_paths": sorted({path for item in items for path in item.get("response_summary", {}).get("paths_sample", [])})[:80],
            }
        )
    return candidates


async def safe_discover_interactions(page: Any) -> None:
    for selector in ["select", "input[type=search]", "input[name*=keyword i]", "input[placeholder*=Keyword i]", "input[placeholder*=关键 i]"]:
        try:
            count = await page.locator(selector).count()
        except Exception:
            continue
        for idx in range(min(count, 3)):
            locator = page.locator(selector).nth(idx)
            try:
                tag = await locator.evaluate("(el) => el.tagName.toLowerCase()")
                if tag == "select":
                    options = await locator.locator("option").all()
                    if len(options) > 1:
                        value = await options[1].get_attribute("value")
                        if value is not None:
                            await locator.select_option(value=value)
                else:
                    await locator.fill("research")
                await page.wait_for_timeout(600)
            except Exception:
                continue
    for label in ["Search", "搜索", "筛选", "查询"]:
        try:
            button = page.get_by_text(label, exact=False).first
            if await button.count():
                await button.click(timeout=1500)
                await page.wait_for_timeout(1000)
        except Exception:
            continue


def save_raw_html(settings: Settings, canonical_url: str, html: str) -> str:
    from .utils import safe_filename_from_url

    path = settings.raw_dir / "html" / safe_filename_from_url(canonical_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path.relative_to(settings.root_dir))


def write_inventory(path: Any, pages: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> None:
    lines = ["# Static Discovery Inventory", "", f"- pages: {len(pages)}", f"- api candidates: {len(candidates)}", ""]
    for page in pages:
        lines.extend([f"## {page.get('title') or page.get('canonical_url')}", "", f"- url: `{page.get('canonical_url')}`", f"- links: {len(page.get('links', []))}", f"- assets: {len(page.get('assets', []))}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_api_inventory(path: Any, candidates: list[dict[str, Any]]) -> None:
    lines = ["# API Inventory", "", "仅包含页面实际观察或静态 bundle 中发现的候选接口；GraphQL 不做 introspection。", ""]
    for idx, item in enumerate(candidates, 1):
        lines.extend(
            [
                f"## {idx}. `{item.get('method')} {item.get('url')}`",
                "",
                f"- sample: `{item.get('sample_full_url')}`",
                f"- status: `{item.get('status_codes')}`",
                f"- requires_auth: `{item.get('requires_auth')}`",
                f"- seen_count: `{item.get('seen_count')}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
