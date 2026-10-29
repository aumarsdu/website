"""Top-level archive orchestration."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ArchiveConfig
from .errors import ArchiveError
from .fetcher import HttpFetcher
from .openapi import CaoliaoOpenApiClient
from .parser import extract_tpl_ids, extract_urls_from_html, extract_urls_from_json
from .scheduler import UrlScheduler
from .schema import utc_now_iso
from .storage import ArchiveStorage

LOGGER = logging.getLogger(__name__)


@dataclass
class ArchiveStats:
    started_at: str
    finished_at: str | None = None
    target_qrcode_url: str = ""
    snapshots_saved: int = 0
    pages_requested: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    records_extracted: int = 0
    duplicate_records: int = 0
    assets_discovered: int = 0
    assets_downloaded: int = 0
    assets_skipped_over_limit: int = 0
    external_pages_discovered: int = 0
    external_pages_downloaded: int = 0
    external_pages_skipped_over_limit: int = 0
    skipped_out_of_scope_urls: int = 0
    errors: dict[str, int] = field(default_factory=dict)


def run_archive(config: ArchiveConfig, *, dry_run: bool = False) -> dict[str, Any]:
    stats = ArchiveStats(started_at=utc_now_iso(), target_qrcode_url=config.qrcode_url)
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
        "entry_url": config.entry_url,
        "qrcode_url": config.qrcode_url,
        "dry_run": dry_run,
        "scope": {
            "allowed_qrcode_urls": list(config.allowed_qrcode_urls),
            "allowed_resource_hosts": list(config.allowed_resource_hosts),
            "external_page_whitelist": list(config.external_page_whitelist),
        },
        "limits": {
            "record_pages_per_form": config.max_pages,
            "record_page_size": config.records_page_size,
            "assets": config.max_assets,
            "external_pages": config.max_external_pages,
        },
        "outputs": {},
    }

    if dry_run:
        manifest["plan"] = {
            "official_api_calls": [
                "qrcodes/getContent",
                "qrcodes/getOperation",
                "forms/getTemplate for operation element_type=2",
                "record/getRecords filtered by tpl_id and qrcode.id",
            ],
            "resource_policy": "download only URLs whose host is allowlisted or exact URL is in external_page_whitelist",
            "record_page_size": config.records_page_size,
            "max_pages": config.max_pages,
            "max_assets": config.max_assets,
            "max_external_pages": config.max_external_pages,
            "h5_snapshots": [
                "entry wrapper URL",
                "normalized qrcode URL",
            ],
        }
        path = storage.write_json("reports/dry_run_plan.json", manifest)
        return {"manifest": manifest, "stats": stats, "output": str(path)}

    if not config.api_key:
        raise ArchiveError(
            f"Missing API key. Set environment variable {config.api_key_env}; value will not be logged."
        )

    client = CaoliaoOpenApiClient(fetcher, config.api_key)
    api_content: dict[str, Any] | None = None
    operations: list[dict[str, Any]] = []
    form_templates: dict[int, dict[str, Any]] = {}

    try:
        api_content = client.get_content(config.qrcode_url)
        manifest["outputs"]["qrcode_content"] = str(
            storage.write_json("api/qrcode_content.json", api_content)
        )
        LOGGER.info("qrcode_content_archived")
    except Exception as exc:  # noqa: BLE001 - summarize and keep report usable.
        _record_error(errors, exc)
        raise

    try:
        operations = client.get_operations(config.qrcode_url)
        manifest["outputs"]["qrcode_operations"] = str(
            storage.write_json("api/qrcode_operations.json", operations)
        )
        LOGGER.info("qrcode_operations_archived", extra={"count": len(operations)})
    except Exception as exc:  # noqa: BLE001
        _record_error(errors, exc)
        LOGGER.warning("qrcode_operations_failed", extra={"error": exc.__class__.__name__})

    tpl_ids = extract_tpl_ids(operations)
    for tpl_id in tpl_ids:
        try:
            template = client.get_form_template(tpl_id)
            form_templates[tpl_id] = template
            storage.write_json(f"api/form_templates/{tpl_id}.json", template)
            LOGGER.info("form_template_archived", extra={"tpl_id": tpl_id})
        except Exception as exc:  # noqa: BLE001
            _record_error(errors, exc)
            LOGGER.warning(
                "form_template_failed",
                extra={"tpl_id": tpl_id, "error": exc.__class__.__name__},
            )

    if config.include_records:
        qrcode_id = _extract_qrcode_id(api_content)
        for tpl_id in tpl_ids:
            rows = []
            seen_record_ids: set[str] = set()
            try:
                for row in client.iter_records(
                    tpl_id=tpl_id,
                    qrcode_id=qrcode_id,
                    page_size=config.records_page_size,
                    max_pages=config.max_pages,
                ):
                    record_id = _record_identity(row)
                    if record_id and record_id in seen_record_ids:
                        stats.duplicate_records += 1
                        continue
                    if record_id:
                        seen_record_ids.add(record_id)
                    rows.append(
                        {
                            "source_qrcode_url": config.qrcode_url,
                            "tpl_id": tpl_id,
                            "crawled_at": utc_now_iso(),
                            "record": row,
                        }
                    )
                stats.records_extracted += len(rows)
                storage.write_jsonl(f"api/records/{tpl_id}.jsonl", rows)
                LOGGER.info(
                    "records_archived",
                    extra={"tpl_id": tpl_id, "records_extracted": len(rows)},
                )
            except Exception as exc:  # noqa: BLE001
                _record_error(errors, exc)
                LOGGER.warning(
                    "records_failed",
                    extra={"tpl_id": tpl_id, "error": exc.__class__.__name__},
                )

    asset_urls = set()
    if api_content is not None:
        asset_urls.update(extract_urls_from_json(api_content))
    asset_urls.update(extract_urls_from_json(operations))
    asset_urls.update(extract_urls_from_json(form_templates))

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
                    "h5_snapshot_failed",
                    extra={"label": label, "error": exc.__class__.__name__},
                )

    external_page_urls = {
        url for url in asset_urls if config.is_external_page_allowed(url)
    }
    stats.external_pages_discovered = len(external_page_urls)
    external_page_index: list[dict[str, Any]] = []
    if external_page_urls:
        external_scheduler = UrlScheduler(
            max_pages=config.max_external_pages,
            allow_url=config.is_external_page_allowed,
        )
        external_scheduler.add_many(sorted(external_page_urls))
        stats.external_pages_skipped_over_limit = external_scheduler.skipped_over_limit
        for url in external_scheduler:
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
    manifest["outputs"]["external_page_index"] = str(
        storage.write_jsonl("external_pages/index.jsonl", external_page_index)
    )

    asset_urls = {
        url for url in asset_urls if not config.is_external_page_allowed(url)
    }
    stats.assets_discovered = len(asset_urls)
    asset_index: list[dict[str, Any]] = []
    if config.download_assets:
        scheduler = UrlScheduler(
            max_pages=config.max_assets,
            allow_url=config.is_resource_allowed,
        )
        scheduler.add_many(sorted(asset_urls))
        skipped_urls = sorted(
            url for url in asset_urls if not config.is_resource_allowed(url)
        )
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
    manifest["outputs"]["asset_index"] = str(storage.write_jsonl("assets/index.jsonl", asset_index))

    stats.finished_at = utc_now_iso()
    stats.errors = dict(errors)
    manifest["outputs"]["summary"] = str(config.output_dir / "reports/summary.json")
    summary = {
        "manifest": manifest,
        "stats": stats,
        "completion": _completion_status(stats),
    }
    storage.write_json("reports/summary.json", summary)
    return summary


def _snapshot_targets(config: ArchiveConfig) -> list[tuple[str, str, str]]:
    targets = [("entry", config.entry_url, "html/entry_page.html")]
    if config.qrcode_url != config.entry_url:
        targets.append(("qrcode", config.qrcode_url, "html/qrcode_page.html"))
    return targets


def _completion_status(stats: ArchiveStats) -> dict[str, Any]:
    blockers = []
    if stats.pages_failed:
        blockers.append("pages_failed")
    if stats.errors:
        blockers.append("errors_present")
    if stats.assets_skipped_over_limit:
        blockers.append("assets_skipped_over_limit")
    if stats.external_pages_skipped_over_limit:
        blockers.append("external_pages_skipped_over_limit")
    return {
        "complete": not blockers,
        "blockers": blockers,
    }


def _extract_qrcode_id(content: dict[str, Any] | None) -> int | None:
    if not content:
        return None
    meta = content.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("id"), int):
        return meta["id"]
    return None


def _record_identity(record: dict[str, Any]) -> str | None:
    for key in ("id", "record_id", "uuid", "url"):
        value = record.get(key)
        if value is not None:
            return str(value)
    return None


def _record_error(errors: Counter[str], exc: Exception) -> None:
    errors[getattr(exc, "category", "unknown_error")] += 1
