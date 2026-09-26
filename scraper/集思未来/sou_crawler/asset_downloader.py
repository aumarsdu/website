from __future__ import annotations

import asyncio
from http.client import IncompleteRead
import hashlib
import logging
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from .config import CrawlConfig, ensure_output_dirs
from .utils import deep_find_asset_urls, iter_jsonl, safe_filename, write_json

LOGGER = logging.getLogger(__name__)


async def download_assets_from_outputs(config: CrawlConfig, *, dry_run: bool = False) -> None:
    ensure_output_dirs(config)
    urls = collect_asset_urls(config)
    if dry_run:
        print(f"download-assets: {len(urls)} asset URLs")
        for url in urls[:50]:
            print(f"- {url}")
        return

    stats = {"assets_found": len(urls), "downloaded": 0, "failed": 0, "skipped": 0, "errors": {}}
    if httpx is None:
        semaphore = asyncio.Semaphore(config.concurrency)

        async def fetch_stdlib(url: str) -> None:
            async with semaphore:
                if asset_path(config, url).exists():
                    stats["skipped"] = int(stats["skipped"]) + 1
                    return
                await asyncio.sleep(config.rate_limit)
                await asyncio.to_thread(download_one_stdlib, url, config, stats)

        await asyncio.gather(*(fetch_stdlib(url) for url in urls))
        write_json(config.reports_dir / "download_assets_stats.json", stats)
        return

    async with httpx.AsyncClient(
        timeout=config.timeout,
        headers={"User-Agent": config.user_agent},
        follow_redirects=True,
    ) as client:
        semaphore = asyncio.Semaphore(config.concurrency)

        async def fetch(url: str) -> None:
            async with semaphore:
                filename = asset_filename(url)
                target = config.assets_dir / filename
                if target.exists():
                    stats["skipped"] += 1
                    return
                last_error = "unknown_error"
                for attempt in range(config.retries + 1):
                    await asyncio.sleep(config.rate_limit * (2**attempt if attempt else 1))
                    try:
                        response = await client.get(url)
                        if response.status_code == 403:
                            record_download_error(stats, "http_403_forbidden")
                            return
                        if response.status_code == 429 or response.status_code >= 500:
                            last_error = classify_asset_status(response.status_code)
                            continue
                        if response.status_code == 404:
                            record_download_error(stats, "http_404_not_found")
                            return
                        response.raise_for_status()
                        target.write_bytes(response.content)
                        stats["downloaded"] += 1
                        return
                    except httpx.TimeoutException:
                        last_error = "timeout"
                    except httpx.HTTPError as exc:
                        last_error = f"http_error_{type(exc).__name__}"
                        break
                record_download_error(stats, last_error)

        await asyncio.gather(*(fetch(url) for url in urls))
    write_json(config.reports_dir / "download_assets_stats.json", stats)


def record_download_error(stats: dict[str, Any], category: str) -> None:
    stats["failed"] += 1
    stats["errors"][category] = stats["errors"].get(category, 0) + 1


def classify_asset_status(status: int) -> str:
    if status == 429:
        return "http_429_rate_limited"
    if status == 404:
        return "http_404_not_found"
    if status == 403:
        return "http_403_forbidden"
    if status >= 500:
        return "http_5xx_server_error"
    return f"http_error_{status}"


def download_one_stdlib(url: str, config: CrawlConfig, stats: dict[str, object]) -> None:
    target = asset_path(config, url)
    if target.exists():
        stats["skipped"] = int(stats["skipped"]) + 1
        return
    request = Request(quote_url(url), headers={"User-Agent": config.user_agent})
    try:
        with urlopen(request, timeout=config.timeout) as response:
            target.write_bytes(response.read())
            stats["downloaded"] = int(stats["downloaded"]) + 1
    except HTTPError as exc:
        stats["failed"] = int(stats["failed"]) + 1
        key = "http_403_forbidden" if exc.code == 403 else f"http_error_{exc.code}"
        errors = stats["errors"]
        assert isinstance(errors, dict)
        errors[key] = errors.get(key, 0) + 1
    except TimeoutError:
        stats["failed"] = int(stats["failed"]) + 1
        errors = stats["errors"]
        assert isinstance(errors, dict)
        errors["timeout"] = errors.get("timeout", 0) + 1
    except URLError as exc:
        stats["failed"] = int(stats["failed"]) + 1
        reason = getattr(exc, "reason", None)
        key = "timeout" if isinstance(reason, TimeoutError) else "unknown_error"
        errors = stats["errors"]
        assert isinstance(errors, dict)
        errors[key] = errors.get(key, 0) + 1
    except IncompleteRead:
        stats["failed"] = int(stats["failed"]) + 1
        errors = stats["errors"]
        assert isinstance(errors, dict)
        errors["incomplete_read"] = errors.get("incomplete_read", 0) + 1
    except UnicodeEncodeError:
        stats["failed"] = int(stats["failed"]) + 1
        errors = stats["errors"]
        assert isinstance(errors, dict)
        errors["url_encoding_error"] = errors.get("url_encoding_error", 0) + 1


def collect_asset_urls(config: CrawlConfig) -> list[str]:
    urls: set[str] = set()
    for path in (
        config.raw_dir / "list_records.jsonl",
        config.raw_dir / "detail_responses.jsonl",
        config.raw_dir / "summary_poster_responses.jsonl",
    ):
        for row in iter_jsonl(path):
            urls.update(deep_find_asset_urls(row))
    return sorted(urls)


def asset_filename(url: str) -> str:
    parsed = urlsplit(url)
    suffix = Path(parsed.path).suffix
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    stem = Path(parsed.path).name or digest
    return safe_filename(f"{digest}_{stem}", suffix=suffix)


def asset_path(config: CrawlConfig, url: str) -> Path:
    return config.assets_dir / asset_filename(url)


def quote_url(url: str) -> str:
    parsed = urlsplit(url)
    path = quote(parsed.path, safe="/%")
    query = quote(parsed.query, safe="=&?/%")
    return urlunsplit((parsed.scheme, parsed.netloc, path, query, parsed.fragment))
