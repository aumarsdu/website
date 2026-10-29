from __future__ import annotations

import html
import json
import random
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from .config import Settings
from .sanitize import dumps_safe, sanitize_text, sanitize_url, strip_sensitive_query
from .storage import Storage


SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.I)
LINK_HREF_RE = re.compile(r"<a[^>]+href=[\"']([^\"']+)[\"']", re.I)
ASSET_RE = re.compile(r"https?://[^\s\"'<>\\]+|/(?:_next|icons|images|logo|favicon)[^\s\"'<>\\]*", re.I)


def safe_filename(path: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", path.strip("/")) or "home"
    return value[:120] + ".html"


def same_allowed(url: str, settings: Settings) -> bool:
    host = urlsplit(url).netloc
    return host in settings.allowed_domains


def fetch_text(url: str, settings: Settings, timeout: int = 30) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.status, response.headers.get("content-type", ""), response.read().decode(charset, errors="replace")


def _balanced_json_array(text: str, marker: str) -> list[dict[str, Any]]:
    start = text.find(marker)
    if start < 0:
        return []
    idx = start + len(marker)
    if idx >= len(text) or text[idx] != "[":
        return []
    depth = 0
    in_string = False
    escape = False
    for pos in range(idx, len(text)):
        char = text[pos]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[idx : pos + 1])
                except json.JSONDecodeError:
                    return []
                return value if isinstance(value, list) else []
    return []


def extract_initial_schools(raw_html: str) -> list[dict[str, Any]]:
    decoded = html.unescape(raw_html).replace('\\"', '"').replace("\\u0026", "&")
    return _balanced_json_array(decoded, '"initialSchools":')


def extract_assets(raw_html: str, base_url: str) -> list[str]:
    assets: set[str] = set()
    for match in ASSET_RE.finditer(raw_html):
        url = match.group(0)
        if url.startswith("/"):
            url = urljoin(base_url, url)
        assets.add(strip_sensitive_query(sanitize_url(url)))
    return sorted(assets)


def extract_links(raw_html: str, base_url: str, settings: Settings) -> list[str]:
    links: set[str] = set()
    for href in LINK_HREF_RE.findall(raw_html):
        url = urljoin(base_url, href)
        if same_allowed(url, settings):
            links.add(strip_sensitive_query(sanitize_url(url)))
    return sorted(links)


def run_static_probe(settings: Settings, storage: Storage, logger) -> None:
    storage.init_db()
    run_id = storage.start_run("static-probe", "stdlib HTML probe without browser automation")
    output_dir = settings.output_dir
    html_dir = output_dir / "probe" / "html"
    raw_dir = output_dir / "raw"
    normalized_dir = output_dir / "normalized"
    reports_dir = output_dir / "reports"
    for directory in (html_dir, raw_dir, normalized_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    all_assets: dict[str, str] = {}
    all_links: set[str] = set()
    school_records: dict[str, dict[str, Any]] = {}
    route_summaries: list[dict[str, Any]] = []

    try:
        for path in settings.initial_paths[: settings.max_probe_pages]:
            url = urljoin(settings.base_url, path)
            logger.info("fetching %s", sanitize_url(url))
            try:
                status, content_type, body = fetch_text(url, settings)
            except Exception as exc:
                storage.save_error(run_id=run_id, target="static-probe", method="GET", url=sanitize_url(url), error_type="unknown_error", message=repr(exc))
                logger.error("failed %s: %s", sanitize_url(url), exc)
                continue

            sanitized_body = sanitize_text(body)
            body_hash = storage.save_raw_response(
                run_id=run_id,
                method="GET",
                url=sanitize_url(url),
                status_code=status,
                content_type=content_type,
                body_text=sanitized_body,
            )
            storage.upsert_endpoint("GET", urlsplit(url).path or "/", "page", body_hash)
            (html_dir / safe_filename(path)).write_text(sanitized_body, encoding="utf-8")

            links = extract_links(body, settings.base_url, settings)
            assets = extract_assets(body, settings.base_url)
            all_links.update(links)
            for asset in assets:
                all_assets[asset] = sanitize_url(url)
                storage.upsert_asset(asset, guess_asset_type(asset), sanitize_url(url))

            schools = extract_initial_schools(body)
            for item in schools:
                if not isinstance(item, dict):
                    continue
                source_id = str(item.get("id") or "")
                if not source_id:
                    continue
                safe_item = json.loads(dumps_safe(item))
                school_records[source_id] = safe_item
                normalized = {
                    "source_id": source_id,
                    "name": safe_item.get("name"),
                    "name_en": safe_item.get("name_en"),
                    "website_url": safe_item.get("website_url"),
                    "image_url": safe_item.get("image_url"),
                    "source_url": sanitize_url(url),
                }
                storage.upsert_source_record("home_initial_school", source_id, safe_item, normalized)

            route_summaries.append(
                {
                    "url": sanitize_url(url),
                    "status": status,
                    "content_type": content_type,
                    "body_hash": body_hash,
                    "links_found": len(links),
                    "assets_found": len(assets),
                    "initial_schools_found": len(schools),
                }
            )
            time.sleep(random.uniform(settings.request_min_delay_seconds, settings.request_max_delay_seconds))

        (normalized_dir / "home_initial_schools.jsonl").write_text(
            "\n".join(dumps_safe(record) for record in school_records.values()) + ("\n" if school_records else ""),
            encoding="utf-8",
        )
        (reports_dir / "asset_manifest.json").write_text(
            dumps_safe([{"url": url, "referer_url": referer} for url, referer in sorted(all_assets.items())], indent=2),
            encoding="utf-8",
        )
        (reports_dir / "links.json").write_text(dumps_safe(sorted(all_links), indent=2), encoding="utf-8")
        (reports_dir / "static_probe_report.md").write_text(
            build_static_report(route_summaries, len(school_records), len(all_assets), len(all_links)),
            encoding="utf-8",
        )
        storage.finish_run(run_id, "completed")
    except Exception:
        storage.finish_run(run_id, "failed")
        raise


def guess_asset_type(url: str) -> str:
    path = urlsplit(url).path.lower()
    if path.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico")):
        return "image"
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith(".js"):
        return "script"
    if path.endswith(".css"):
        return "stylesheet"
    return "unknown"


def build_static_report(routes: list[dict[str, Any]], schools_count: int, assets_count: int, links_count: int) -> str:
    lines = [
        "# Openision Static Probe Report",
        "",
        "## Summary",
        f"- routes_requested: {len(routes)}",
        f"- embedded_home_initial_schools: {schools_count}",
        f"- unique_assets_listed: {assets_count}",
        f"- same_site_links_found: {links_count}",
        "",
        "## Routes",
        "",
        "| URL | Status | Links | Assets | Embedded Schools |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in routes:
        lines.append(
            f"| {row['url']} | {row['status']} | {row['links_found']} | {row['assets_found']} | {row['initial_schools_found']} |"
        )
    lines.extend(
        [
            "",
            "## Compliance Notes",
            "- Only public routes from configured initial_paths were requested.",
            "- Sensitive query values in signed asset URLs were redacted or stripped before persistence.",
            "- No login, CAPTCHA, paywall, or access-control bypass was attempted.",
        ]
    )
    return "\n".join(lines) + "\n"
