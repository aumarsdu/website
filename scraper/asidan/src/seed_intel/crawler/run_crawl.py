from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid
from xml.etree import ElementTree

from seed_intel.common.url_utils import is_allowed_domain, is_asset_url, normalize_url, should_block_url
from seed_intel.config import PROJECT_ROOT, load_crawl_config, load_domains
from seed_intel.crawler.fetcher import Fetcher
from seed_intel.crawler.storage import CrawlStorage
from seed_intel.extraction.project_normalizer import normalize_project
from seed_intel.extraction.rule_extractor import extract_project_from_page
from seed_intel.extraction.schema import CrawlStats, ProjectRecord
from seed_intel.parsers.html_parser import parse_html
from seed_intel.parsers.pdf_parser import parse_pdf_bytes


def _content_kind(content_type: str, url: str) -> str:
    lowered = content_type.lower()
    path = url.lower().split("?", 1)[0]
    if "text/html" in lowered:
        return "html"
    if "xml" in lowered or path.endswith(".xml"):
        return "xml"
    if "pdf" in lowered or path.endswith(".pdf"):
        return "pdf"
    if re.search(r"\.(docx?|xlsx?|pptx?|jpe?g|png|webp|gif|svg|zip|rar|mp4)$", path):
        return "asset"
    return "other"


def _parse_sitemap(content: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return []
    urls: list[str] = []
    for node in root.iter():
        if node.tag.endswith("loc") and node.text:
            urls.append(node.text.strip())
    return urls


def dry_run_targets(root: Path = PROJECT_ROOT) -> list[str]:
    crawl = load_crawl_config(root)["crawl"]
    domains = load_domains(root)
    start_urls = [normalize_url(item) for item in crawl["start_urls"]]
    allowed = domains["allowed_domains"]
    blocked = domains["blocked_patterns"]
    return [url for url in start_urls if is_allowed_domain(url, allowed) and not should_block_url(url, blocked)]


def run_crawl(
    mode: str,
    root: Path = PROJECT_ROOT,
    max_pages: int = 20,
    rate_limit: float | None = None,
    timeout: float | None = None,
    retries: int | None = None,
    dry_run: bool = False,
    resume_batch_id: str | None = None,
) -> dict[str, object]:
    crawl_config = load_crawl_config(root)["crawl"]
    domains = load_domains(root)
    allowed_domains = domains["allowed_domains"]
    blocked_patterns = domains["blocked_patterns"]
    asset_extensions = crawl_config["asset_extensions"]
    targets = dry_run_targets(root)
    if dry_run:
        return {
            "mode": mode,
            "dry_run": True,
            "targets": targets,
            "resume_batch_id": resume_batch_id,
            "expected_fields": ["project_name", "category", "target_grade", "deadline", "price", "evidence"],
        }

    batch_id = resume_batch_id or (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    storage = CrawlStorage(root, batch_id)
    stats = CrawlStats(started_at=datetime.now(timezone.utc))
    fetcher = Fetcher(
        user_agent=crawl_config["user_agent"],
        timeout=timeout or float(crawl_config["timeout_seconds"]),
        retries=retries if retries is not None else int(crawl_config["retry_times"]),
        rate_limit=rate_limit if rate_limit is not None else float(crawl_config["download_delay"]),
    )

    cached_pages = storage.load_pages() if resume_batch_id else []
    queue = deque(targets)
    for page in cached_pages:
        queue.extend(page.links)
        queue.extend(page.asset_urls)
    seen: set[str] = set()
    records = [normalize_project(extract_project_from_page(page)) for page in cached_pages]
    errors: list[dict[str, object]] = []
    cache_skipped = 0

    while queue and stats.pages_requested < max_pages:
        url = queue.popleft()
        normalized = normalize_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        if not is_allowed_domain(normalized, allowed_domains) or should_block_url(normalized, blocked_patterns):
            errors.append({"url": normalized, "error": "blocked_or_disallowed"})
            continue

        if storage.has_html(normalized) or storage.has_asset(normalized):
            cache_skipped += 1
            continue

        stats.pages_requested += 1
        result = fetcher.fetch(normalized)
        if result.error:
            stats.pages_failed += 1
            stats.error_categories[result.error] = stats.error_categories.get(result.error, 0) + 1
            errors.append({"url": normalized, "final_url": result.final_url, "status_code": result.status_code, "error": result.error})
            continue

        stats.pages_succeeded += 1
        kind = _content_kind(result.content_type, result.final_url)
        if kind == "xml":
            for discovered in _parse_sitemap(result.content):
                candidate = normalize_url(discovered)
                if is_allowed_domain(candidate, allowed_domains) and not should_block_url(candidate, blocked_patterns):
                    queue.append(candidate)
            continue
        if kind == "html":
            storage.save_html(result.final_url, result.content, result.headers)
            page = parse_html(result.content.decode("utf-8", errors="replace"), result.final_url, asset_extensions)
            storage.save_page(page)
            record = normalize_project(extract_project_from_page(page))
            records.append(record)
            for link in page.links:
                if len(seen) + len(queue) >= max_pages * 5:
                    break
                if is_allowed_domain(link, allowed_domains) and not should_block_url(link, blocked_patterns):
                    queue.append(link)
            for asset in page.asset_urls:
                if is_allowed_domain(asset, allowed_domains) and not should_block_url(asset, blocked_patterns):
                    queue.append(asset)
            continue
        if kind == "pdf":
            asset_path = storage.save_asset(result.final_url, result.content)
            parsed = parse_pdf_bytes(result.content)
            text_path = root / "data" / "silver" / "document_text" / batch_id / (asset_path.stem + ".txt")
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(parsed.text, encoding="utf-8")
            if parsed.needs_manual_review:
                errors.append({"url": normalized, "error": parsed.parse_error or "pdf_needs_manual_review"})
            continue
        if kind == "asset" or is_asset_url(result.final_url, asset_extensions):
            storage.save_asset(result.final_url, result.content)

    stats.records_extracted = len(records)
    stats.finished_at = datetime.now(timezone.utc)
    projects_path = storage.save_projects_jsonl(records)
    errors_path = storage.save_errors(errors)
    return {
        "batch_id": batch_id,
        "stats": stats.model_dump(),
        "projects_path": str(projects_path),
        "errors_path": str(errors_path),
        "resume_batch_id": resume_batch_id,
        "cached_pages_reused": len(cached_pages),
        "cache_urls_skipped": cache_skipped,
    }
