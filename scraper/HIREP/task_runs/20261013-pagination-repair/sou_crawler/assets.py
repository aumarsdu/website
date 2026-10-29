from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import logging
import sys
from urllib.parse import urlparse

from .config import Settings
from .fetcher import CrawlStopped, HttpFetcher
from .schema import CrawlStats
from .storage import iter_jsonl, write_json
from .utils import file_extension_from_url, find_asset_urls, find_first, safe_filename, stable_hash, utc_now

LOGGER = logging.getLogger(__name__)


async def download_assets(settings: Settings) -> None:
    records = _load_candidate_records(settings)
    if settings.dry_run:
        urls = sorted({url for record in records for url in find_asset_urls(record)})
        sys.stdout.write(
            json.dumps(
                {
                    "command": "download-assets",
                    "dry_run": True,
                    "candidate_records": len(records),
                    "asset_urls": urls[:100],
                    "asset_url_count": len(urls),
                    "will_download": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        return
    stats = CrawlStats(started_at=utc_now(), target_domain="assets")
    manifest: list[dict[str, Any]] = []
    response_cache: dict[str, tuple[bytes, dict[str, str]]] = {}

    async with HttpFetcher(settings) as fetcher:
        for record in records:
            title = find_first(record, ["title", "name", "courseName", "projectName"]) or record.get("business_id") or "item"
            category = find_first(record, ["category", "level1Name", "classifyName", "subjectName", "industryName"]) or "uncategorized"
            professor = find_first(record, ["professor", "teacher", "instructor", "professorName", "teacherName"]) or title
            folder = settings.assets_dir / safe_filename(category) / safe_filename(title)
            urls = find_asset_urls(record)
            record_seen_urls: set[str] = set()
            for url in urls:
                if url in record_seen_urls:
                    continue
                record_seen_urls.add(url)
                hostname = urlparse(url).hostname or ""
                if not settings.is_allowed_asset_host(hostname):
                    stats.pages_failed += 1
                    stats.add_error("asset_host_not_allowed")
                    manifest.append(
                        {
                            "source_url": url,
                            "file": None,
                            "error": "asset_host_not_allowed",
                            "record_title": title,
                            "category": category,
                        }
                    )
                    continue
                stats.pages_requested += 1
                try:
                    if url in response_cache:
                        content, headers = response_cache[url]
                    else:
                        content, headers = await fetcher.request_bytes("GET", url, allow_assets=True)
                        response_cache[url] = (content, headers)
                    stats.pages_succeeded += 1
                    ext = file_extension_from_url(url)
                    filename = _asset_filename(url, title, professor, ext)
                    path = _unique_path(folder / filename)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                    manifest.append(
                        {
                            "source_url": url,
                            "file": str(path),
                            "content_type": headers.get("content-type"),
                            "bytes": len(content),
                            "record_title": title,
                            "category": category,
                        }
                    )
                except CrawlStopped:
                    stats.pages_failed += 1
                    stats.add_error("http_401_or_403_access_control")
                    break
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("附件下载失败: %s", exc)
                    stats.pages_failed += 1
                    stats.add_error("unknown_error")

    write_json(settings.processed_dir / "asset_manifest.json", manifest)
    write_json(settings.reports_dir / "download_assets_stats.json", stats.as_dict())
    LOGGER.info("附件下载完成: files=%s", len(manifest))


def _load_candidate_records(settings: Settings) -> list[dict[str, Any]]:
    normalized = settings.processed_dir / "projects.jsonl"
    if normalized.exists():
        return list(iter_jsonl(normalized) or [])
    records: list[dict[str, Any]] = []
    for path in [settings.raw_dir / "details_raw.jsonl", settings.raw_dir / "list_items.jsonl"]:
        records.extend(list(iter_jsonl(path) or []))
    return records


def _asset_filename(url: str, title: Any, professor: Any, ext: str) -> str:
    lower = url.lower()
    if any(token in lower for token in ["avatar", "head", "professor", "teacher"]):
        base = safe_filename(professor, fallback="professor")
    elif any(token in lower for token in ["poster", "海报", "industryposter"]):
        base = safe_filename(title, fallback="poster")
    else:
        base = safe_filename(title, fallback="asset")
    return f"{base}{ext}"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(2, 1000):
        candidate = path.with_name(f"{stem}-{idx}{suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{stem}-{stable_hash(str(path))}{suffix}")
