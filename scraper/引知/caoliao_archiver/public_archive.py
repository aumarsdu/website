"""Archive public H5 content when OpenAPI credentials are unavailable."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .config import ArchiveConfig
from .fetcher import HttpFetcher
from .parser import extract_urls_from_html, extract_urls_from_json
from .publicapi import PublicH5Client
from .scheduler import UrlScheduler
from .schema import utc_now_iso
from .storage import ArchiveStorage

LOGGER = logging.getLogger(__name__)


@dataclass
class PublicArchiveStats:
    started_at: str
    finished_at: str | None = None
    target_qrcode_url: str = ""
    public_api_calls: int = 0
    snapshots_saved: int = 0
    pages_requested: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    assets_discovered: int = 0
    assets_downloaded: int = 0
    assets_skipped_over_limit: int = 0
    external_pages_discovered: int = 0
    external_pages_downloaded: int = 0
    external_pages_skipped_over_limit: int = 0
    skipped_out_of_scope_urls: int = 0
    errors: dict[str, int] = field(default_factory=dict)


def run_public_archive(config: ArchiveConfig, *, dry_run: bool = False) -> dict[str, Any]:
    stats = PublicArchiveStats(started_at=utc_now_iso(), target_qrcode_url=config.qrcode_url)
    storage = ArchiveStorage(config.output_dir)
    fetcher = HttpFetcher(
        user_agent=config.user_agent,
        rate_limit_seconds=config.rate_limit_seconds,
        timeout_seconds=config.timeout_seconds,
        retries=config.retries,
    )
    errors: Counter[str] = Counter()

    manifest: dict[str, Any] = {
        "started_at": stats.started_at,
        "mode": "public_h5",
        "entry_url": config.entry_url,
        "qrcode_url": config.qrcode_url,
        "qrcode_route": config.qrcode_route,
        "dry_run": dry_run,
        "scope": {
            "allowed_qrcode_urls": list(config.allowed_qrcode_urls),
            "allowed_resource_hosts": list(config.allowed_resource_hosts),
            "external_page_whitelist": list(config.external_page_whitelist),
        },
        "limits": {
            "assets": config.max_assets,
            "external_pages": config.max_external_pages,
        },
        "outputs": {},
        "known_limitations": [
            "Does not archive form templates or form records; those require OpenAPI credentials.",
            "Does not enumerate other QR codes or crawl platform backends.",
        ],
    }

    if dry_run:
        manifest["plan"] = {
            "public_frontend_api_calls": [
                {
                    "method": "POST",
                    "url": "https://data.caoliao.net/x-llm/api/aicraft/getContentByRoute",
                    "body": {"route": config.qrcode_route},
                }
            ],
            "h5_snapshots": [
                "entry wrapper URL",
                "normalized qrcode URL",
            ],
            "resource_policy": "download only URLs whose host is allowlisted or exact URL is in external_page_whitelist",
        }
        path = storage.write_json("reports/public_dry_run_plan.json", manifest)
        return {"manifest": manifest, "stats": stats, "output": str(path)}

    asset_urls: set[str] = set()
    client = PublicH5Client(fetcher)
    try:
        content = client.get_content_by_route(config.qrcode_route)
        stats.public_api_calls += 1
        manifest["outputs"]["public_content_json"] = str(
            storage.write_json("public/content.json", content.raw)
        )
        manifest["outputs"]["public_content_markdown"] = str(
            storage.write_text("public/content.md", content.markdown)
        )
        manifest["outputs"]["public_headers_html"] = str(
            storage.write_text("public/headers.html", content.headers)
        )
        asset_urls.update(extract_urls_from_json(content.raw))
        asset_urls.update(extract_urls_from_html(content.headers, config.qrcode_url))
    except Exception as exc:  # noqa: BLE001
        _record_error(errors, exc)
        raise

    if config.fetch_h5_snapshot:
        for label, url, relative_path in _snapshot_targets(config):
            try:
                response = fetcher.get(url)
                stats.pages_requested += 1
                stats.pages_succeeded += 1
                storage.write_text(relative_path, response.text)
                stats.snapshots_saved += 1
                asset_urls.update(extract_urls_from_html(response.text, response.url))
                manifest["outputs"][f"{label}_snapshot"] = str(config.output_dir / relative_path)
            except Exception as exc:  # noqa: BLE001
                stats.pages_requested += 1
                stats.pages_failed += 1
                _record_error(errors, exc)
                LOGGER.warning(
                    "public_h5_snapshot_failed",
                    extra={"label": label, "error": exc.__class__.__name__},
                )

    external_page_index = _archive_external_pages(
        config=config,
        storage=storage,
        fetcher=fetcher,
        stats=stats,
        errors=errors,
        asset_urls=asset_urls,
    )
    manifest["outputs"]["external_page_index"] = str(
        storage.write_jsonl("external_pages/index.jsonl", external_page_index)
    )

    asset_urls = {url for url in asset_urls if not config.is_external_page_allowed(url)}
    stats.assets_discovered = len(asset_urls)
    asset_index = _archive_assets(
        config=config,
        storage=storage,
        fetcher=fetcher,
        stats=stats,
        errors=errors,
        asset_urls=asset_urls,
    )
    manifest["outputs"]["asset_index"] = str(storage.write_jsonl("assets/index.jsonl", asset_index))

    stats.finished_at = utc_now_iso()
    stats.errors = dict(errors)
    manifest["outputs"]["summary"] = str(config.output_dir / "reports/public_summary.json")
    summary = {
        "manifest": manifest,
        "stats": stats,
        "completion": _completion_status(stats),
    }
    storage.write_json("reports/public_summary.json", summary)
    return summary


def _archive_external_pages(
    *,
    config: ArchiveConfig,
    storage: ArchiveStorage,
    fetcher: HttpFetcher,
    stats: PublicArchiveStats,
    errors: Counter[str],
    asset_urls: set[str],
) -> list[dict[str, Any]]:
    external_page_urls = {url for url in asset_urls if config.is_external_page_allowed(url)}
    stats.external_pages_discovered = len(external_page_urls)
    external_page_index: list[dict[str, Any]] = []
    if not external_page_urls:
        return external_page_index
    scheduler = UrlScheduler(max_pages=config.max_external_pages, allow_url=config.is_external_page_allowed)
    scheduler.add_many(sorted(external_page_urls))
    stats.external_pages_skipped_over_limit = scheduler.skipped_over_limit
    for url in scheduler:
        try:
            response = fetcher.get(url)
            stats.pages_requested += 1
            stats.pages_succeeded += 1
            relative_path = storage.external_page_path_for(url, response.body)
            storage.write_text(relative_path, response.text)
            asset_urls.update(extract_urls_from_html(response.text, response.url))
            external_page_index.append(
                {
                    "url": url,
                    "status": "downloaded",
                    "path": str(config.output_dir / relative_path),
                    "bytes": len(response.body),
                }
            )
            stats.external_pages_downloaded += 1
        except Exception as exc:  # noqa: BLE001
            stats.pages_requested += 1
            stats.pages_failed += 1
            _record_error(errors, exc)
            external_page_index.append(
                {
                    "url": url,
                    "status": "failed",
                    "error_category": getattr(exc, "category", "unknown_error"),
                }
            )
    return external_page_index


def _archive_assets(
    *,
    config: ArchiveConfig,
    storage: ArchiveStorage,
    fetcher: HttpFetcher,
    stats: PublicArchiveStats,
    errors: Counter[str],
    asset_urls: set[str],
) -> list[dict[str, Any]]:
    asset_index: list[dict[str, Any]] = []
    if not config.download_assets:
        return asset_index
    scheduler = UrlScheduler(max_pages=config.max_assets, allow_url=config.is_resource_allowed)
    scheduler.add_many(sorted(asset_urls))
    skipped_urls = sorted(url for url in asset_urls if not config.is_resource_allowed(url))
    for url in skipped_urls:
        asset_index.append({"url": url, "status": "skipped_out_of_scope"})
    stats.skipped_out_of_scope_urls += scheduler.skipped_out_of_scope
    stats.assets_skipped_over_limit += scheduler.skipped_over_limit
    for url in scheduler:
        try:
            response = fetcher.get(url)
            stats.pages_requested += 1
            stats.pages_succeeded += 1
            content_type = response.headers.get("content-type")
            relative_path = storage.asset_path_for(url, response.body, content_type)
            storage.write_bytes(relative_path, response.body)
            asset_index.append(
                {
                    "url": url,
                    "status": "downloaded",
                    "path": str(config.output_dir / relative_path),
                    "content_type": content_type,
                    "bytes": len(response.body),
                }
            )
            stats.assets_downloaded += 1
        except Exception as exc:  # noqa: BLE001
            stats.pages_requested += 1
            stats.pages_failed += 1
            _record_error(errors, exc)
            asset_index.append(
                {
                    "url": url,
                    "status": "failed",
                    "error_category": getattr(exc, "category", "unknown_error"),
                }
            )
    return asset_index


def _snapshot_targets(config: ArchiveConfig) -> list[tuple[str, str, str]]:
    targets = [("entry", config.entry_url, "html/entry_page.html")]
    if config.qrcode_url != config.entry_url:
        targets.append(("qrcode", config.qrcode_url, "html/qrcode_page.html"))
    return targets


def _completion_status(stats: PublicArchiveStats) -> dict[str, Any]:
    blockers = []
    if stats.pages_failed:
        blockers.append("pages_failed")
    if stats.errors:
        blockers.append("errors_present")
    if stats.assets_skipped_over_limit:
        blockers.append("assets_skipped_over_limit")
    if stats.external_pages_skipped_over_limit:
        blockers.append("external_pages_skipped_over_limit")
    return {"complete": not blockers, "blockers": blockers}


def _record_error(errors: Counter[str], exc: Exception) -> None:
    errors[getattr(exc, "category", "unknown_error")] += 1
