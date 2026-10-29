from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import CrawlConfig
from .parser import extract_css_urls, extract_links, parse_page, render_markdown
from .storage import ArchiveStore, sha256


class XntjArchiver:
    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self.store = ArchiveStore(config.output_dir)
        self.client = httpx.Client(headers={"User-Agent": config.user_agent}, timeout=config.timeout, follow_redirects=True, trust_env=False)
        self.last_request = 0.0

    def close(self) -> None:
        self.client.close()
        self.store.close()

    def _same_origin(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme == "https" and parsed.hostname == urlparse(self.config.base_url).hostname

    def _get(self, url: str) -> httpx.Response:
        wait = max(0.0, (1 / self.config.rate_limit) - (time.monotonic() - self.last_request))
        if wait:
            time.sleep(wait)
        last_error: Exception | None = None
        for attempt in range(self.config.retries):
            try:
                response = self.client.get(url)
                self.last_request = time.monotonic()
                if response.status_code not in (429, 500, 502, 503, 504) or attempt == self.config.retries - 1:
                    return response
                time.sleep(2 ** attempt)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                self.last_request = time.monotonic()
                if attempt < self.config.retries - 1:
                    time.sleep(2 ** attempt)
        assert last_error is not None
        raise last_error

    def discover(self) -> int:
        response = self._get(self.config.sitemap_url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        found = 0
        for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
            loc = node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc is not None and loc.text and self._same_origin(loc.text):
                self.store.add_url(loc.text, "sitemap")
                found += 1
        return found

    def crawl(self, max_pages: int | None = None, dry_run: bool = False) -> dict:
        discovered = self.discover()
        if dry_run:
            return {"discovered_from_sitemap": discovered, "pending_pages": len(self.store.pending_urls()), "dry_run": True}
        pages_done = 0
        while True:
            remaining = None if max_pages is None else max_pages - pages_done
            if remaining is not None and remaining <= 0:
                break
            pending = self.store.pending_urls(limit=remaining)
            if not pending:
                break
            for url in pending:
                self._archive_page(url)
                pages_done += 1
        while self.store.pending_assets():
            for url in self.store.pending_assets():
                self._archive_asset(url)
        result = self.store.summary()
        result.update({"discovered_from_sitemap": discovered, "pages_attempted": pages_done})
        (self.config.output_dir / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result

    def _archive_page(self, url: str) -> None:
        try:
            response = self._get(url)
            content_type = response.headers.get("content-type")
            if response.status_code != 200 or "html" not in (content_type or ""):
                if response.status_code == 200:
                    # A linked Markdown/text/PDF may have been discovered as a page by an
                    # older rule or a content-type-only endpoint. Preserve the URL result
                    # and queue it in the resource pipeline instead of dropping it.
                    self.store.add_asset(str(response.url), url)
                    self.store.finish_url(url, status=200, content_type=content_type, content_hash=None, path=None, error="non_html_resource_queued_as_asset")
                else:
                    self.store.finish_url(url, status=response.status_code, content_type=content_type, content_hash=None, path=None, error="non_html_response")
                return
            data = response.content
            record = parse_page(response.text, str(response.url))
            pages, assets = extract_links(response.text, str(response.url))
            for link in pages:
                if self._same_origin(link):
                    self.store.add_url(link, url)
            for asset in assets:
                if self._same_origin(asset):
                    self.store.add_asset(asset, url)
            html_path = self.store.write_bytes("pages", url, data, ".html")
            markdown_path = self.store.write_markdown(url, render_markdown(record, str(response.url)))
            metadata_path = self.store.write_json(url, {"source_url": url, "final_url": str(response.url), "fetched_at": response.headers.get("date"), "record": record.to_dict(), "discovered_page_links": sorted(pages), "discovered_asset_links": sorted(assets), "markdown_path": markdown_path})
            self.store.finish_url(url, status=200, content_type=content_type, content_hash=sha256(data), path=html_path, error=None)
        except Exception as exc:
            self.store.finish_url(url, status=None, content_type=None, content_hash=None, path=None, error=f"{type(exc).__name__}: {exc}")

    def _archive_asset(self, url: str) -> None:
        try:
            response = self._get(url)
            content_type = response.headers.get("content-type")
            data = response.content
            if response.status_code != 200:
                self.store.finish_asset(url, status=response.status_code, content_type=content_type, size=len(data), content_hash=None, path=None, error="non_200_response")
                return
            if len(data) > self.config.max_asset_bytes:
                self.store.finish_asset(url, status=response.status_code, content_type=content_type, size=len(data), content_hash=None, path=None, error="asset_exceeds_configured_size_limit")
                return
            suffix = Path(urlparse(str(response.url)).path).suffix or ".bin"
            path = self.store.write_bytes("assets", url, data, suffix)
            if "css" in (content_type or ""):
                for nested in extract_css_urls(response.text, str(response.url)):
                    if self._same_origin(nested):
                        self.store.add_asset(nested, url)
            self.store.finish_asset(url, status=200, content_type=content_type, size=len(data), content_hash=sha256(data), path=path, error=None)
        except Exception as exc:
            self.store.finish_asset(url, status=None, content_type=None, size=None, content_hash=None, path=None, error=f"{type(exc).__name__}: {exc}")
