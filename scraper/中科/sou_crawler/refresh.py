from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlparse

from .config import CrawlSettings, ensure_output_dirs
from .fetcher import AsyncFetcher, FetchResult
from .pipeline import ID_KEYS, extract_items, extract_total_pages, item_identity, load_normalized_records, wrap_raw_result
from .scope import HARBOUR_TOPIC_CATEGORY_URL, HARBOUR_TOPIC_DETAIL_URL, HARBOUR_TOPIC_LIST_URL
from .storage import read_json, write_json
from .utils import now_iso, slugify


SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
@dataclass(frozen=True)
class PublicListSource:
    name: str
    endpoint: str
    method: str
    page_param: str
    page_size_param: str
    page_size: int
    body: Mapping[str, Any] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "method": self.method,
            "page_param": self.page_param,
            "page_size_param": self.page_size_param,
            "page_size": self.page_size,
            "body": dict(self.body),
        }


@dataclass(frozen=True)
class PublicTaxonomySource:
    name: str
    endpoint: str
    method: str
    body: Mapping[str, Any] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "method": self.method,
            "body": dict(self.body),
        }


PUBLIC_LIST_SOURCES = (
    PublicListSource(
        name="harbour_topics",
        endpoint=HARBOUR_TOPIC_LIST_URL,
        method="GET",
        page_param="pageNum",
        page_size_param="pageSize",
        page_size=100,
    ),
)

PUBLIC_TAXONOMY_SOURCES = (
    PublicTaxonomySource(
        name="harbour_topic_category",
        endpoint=HARBOUR_TOPIC_CATEGORY_URL,
        method="GET",
    ),
)


async def refresh_public_topics(
    settings: CrawlSettings,
    *,
    snapshot_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Collect a reproducible snapshot from the explicitly approved public endpoints.

    The snapshot is append-only. It is deliberately separate from discovery-driven
    crawling because filters and other supporting endpoints are not project lists.
    """

    ensure_output_dirs(settings)
    if settings.max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if settings.max_details is not None and settings.max_details < 0:
        raise ValueError("max_details must be zero or greater")
    resolved_snapshot_id = validate_snapshot_id(snapshot_id or default_snapshot_id())
    layout = snapshot_layout(settings, resolved_snapshot_id)
    if dry_run:
        return {
            "dry_run": True,
            "snapshot_id": resolved_snapshot_id,
            "max_pages": settings.max_pages,
            "max_details": settings.max_details,
            "list_sources": [source.metadata() for source in PUBLIC_LIST_SOURCES],
            "taxonomy_sources": [source.metadata() for source in PUBLIC_TAXONOMY_SOURCES],
            "detail_source": {"endpoint": HARBOUR_TOPIC_DETAIL_URL, "method": "GET", "query": {"sourceType": 2}},
        }
    ensure_snapshot_is_new(layout)

    stats: dict[str, Any] = {
        "snapshot_id": resolved_snapshot_id,
        "started_at": now_iso(),
        "baseline_records": len(load_normalized_records(settings)),
        "max_pages": settings.max_pages,
        "max_details": settings.max_details,
        "list_sources": {},
        "taxonomy_sources": {},
        "new_records": {},
        "details": {"eligible": 0, "requested": 0, "succeeded": 0, "failed": 0, "truncated": False, "errors": {}},
        "truncated": False,
    }
    baseline_keys = normalized_record_keys(load_normalized_records(settings))
    listed_items: dict[str, list[dict[str, Any]]] = {}

    async with AsyncFetcher(settings) as fetcher:
        for source in PUBLIC_TAXONOMY_SOURCES:
            result = await request_taxonomy(fetcher, source)
            source_stats = {"requested": 1, "succeeded": 0, "failed": 0, "error": None}
            if result.ok and result.json_data is not None:
                write_json(
                    layout["taxonomy"] / f"{source.name}.json",
                    wrap_raw_result(result, source.metadata(), {"snapshot_id": resolved_snapshot_id}),
                )
                source_stats["succeeded"] = 1
            else:
                source_stats["failed"] = 1
                source_stats["error"] = result.error_category or "unknown_error"
            stats["taxonomy_sources"][source.name] = source_stats

        for source in PUBLIC_LIST_SOURCES:
            items, source_stats = await collect_list_source(fetcher, source, settings, layout["lists"] / source.name, resolved_snapshot_id)
            listed_items[source.name] = items
            stats["list_sources"][source.name] = source_stats
            if source_stats["truncated"]:
                stats["truncated"] = True

        for source in PUBLIC_LIST_SOURCES:
            host = urlparse(source.endpoint).netloc
            new_items = [item for item in dedupe_items(listed_items[source.name]) if (host, item_identity(item)) not in baseline_keys]
            stats["new_records"][source.name] = len(new_items)
            if source.name == "harbour_topics":
                await collect_new_harbour_details(
                    fetcher,
                    new_items,
                    settings,
                    layout["details"] / source.name,
                    resolved_snapshot_id,
                    stats["details"],
                )
                if stats["details"]["truncated"]:
                    stats["truncated"] = True
    stats["finished_at"] = now_iso()
    stats["has_failures"] = has_failures(stats)
    write_json(settings.reports_dir / f"refresh_{resolved_snapshot_id}.json", stats)
    return stats


async def backfill_harbour_details(
    settings: CrawlSettings,
    *,
    snapshot_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Resume collection of missing public detail responses for one list snapshot."""

    ensure_output_dirs(settings)
    if settings.max_details is not None and settings.max_details < 0:
        raise ValueError("max_details must be zero or greater")
    resolved_snapshot_id = validate_snapshot_id(snapshot_id)
    listed_identifiers = load_snapshot_topic_ids(settings, resolved_snapshot_id)
    captured_identifiers = captured_harbour_detail_ids(settings)
    missing_identifiers = sorted(listed_identifiers - captured_identifiers)
    scheduled_identifiers = missing_identifiers
    if settings.max_details is not None:
        scheduled_identifiers = scheduled_identifiers[: settings.max_details]
    stats: dict[str, Any] = {
        "snapshot_id": resolved_snapshot_id,
        "started_at": now_iso(),
        "listed": len(listed_identifiers),
        "captured_before": len(captured_identifiers & listed_identifiers),
        "missing_before": len(missing_identifiers),
        "scheduled": len(scheduled_identifiers),
        "requested": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": {},
        "truncated": len(scheduled_identifiers) < len(missing_identifiers),
    }
    if dry_run:
        return {**stats, "dry_run": True, "sample_identifiers": scheduled_identifiers[:10]}

    target_dir = settings.raw_dir / "details" / f"backfill_{resolved_snapshot_id}" / "harbour_topics"
    async with AsyncFetcher(settings) as fetcher:
        await collect_harbour_detail_identifiers(fetcher, scheduled_identifiers, target_dir, resolved_snapshot_id, stats)
    remaining_identifiers = load_snapshot_topic_ids(settings, resolved_snapshot_id) - captured_harbour_detail_ids(settings)
    stats["remaining_after"] = len(remaining_identifiers)
    stats["finished_at"] = now_iso()
    stats["has_failures"] = bool(stats["failed"])
    write_json(settings.reports_dir / f"backfill_details_{resolved_snapshot_id}.json", stats)
    return stats


async def collect_list_source(
    fetcher: AsyncFetcher,
    source: PublicListSource,
    settings: CrawlSettings,
    target_dir: Path,
    snapshot_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "requested": 0,
        "succeeded": 0,
        "failed": 0,
        "records": 0,
        "reported_pages": None,
        "truncated": False,
        "errors": {},
    }
    seen_item_keys: set[str] = set()
    for page_no in range(1, settings.max_pages + 1):
        result = await request_list_page(fetcher, source, page_no)
        stats["requested"] += 1
        if not result.ok or result.json_data is None:
            stats["failed"] += 1
            bump(stats["errors"], result.error_category or "unknown_error")
            break
        write_json(
            target_dir / f"page_{page_no:04d}.json",
            wrap_raw_result(result, source.metadata(), {"snapshot_id": snapshot_id, "page": page_no}),
        )
        stats["succeeded"] += 1
        page_items = [item for item in extract_items(result.json_data) if isinstance(item, dict)]
        total_pages = extract_total_pages(result.json_data)
        if total_pages is not None:
            stats["reported_pages"] = total_pages
        if not page_items:
            if total_pages is None or total_pages >= page_no:
                stats["failed"] += 1
                stats["truncated"] = True
                bump(stats["errors"], "empty_page_payload")
            break
        page_keys = {item_identity(item) for item in page_items}
        if page_keys and page_keys.issubset(seen_item_keys):
            stats["failed"] += 1
            stats["truncated"] = True
            bump(stats["errors"], "duplicate_page_payload")
            break
        seen_item_keys.update(page_keys)
        items.extend(page_items)
        if total_pages is not None and page_no >= total_pages:
            break
        if page_no == settings.max_pages:
            stats["truncated"] = total_pages is None or total_pages > page_no
    stats["records"] = len(dedupe_items(items))
    return items, stats


async def request_list_page(fetcher: AsyncFetcher, source: PublicListSource, page_no: int) -> FetchResult:
    pagination = {source.page_param: page_no, source.page_size_param: source.page_size}
    if source.method == "GET":
        return await fetcher.request("GET", source.endpoint, params=pagination)
    body = dict(source.body)
    body.update(pagination)
    return await fetcher.request("POST", source.endpoint, json_body=body)


async def request_taxonomy(fetcher: AsyncFetcher, source: PublicTaxonomySource) -> FetchResult:
    if source.method == "GET":
        return await fetcher.request("GET", source.endpoint)
    return await fetcher.request("POST", source.endpoint, json_body=dict(source.body))


async def collect_new_harbour_details(
    fetcher: AsyncFetcher,
    items: list[dict[str, Any]],
    settings: CrawlSettings,
    target_dir: Path,
    snapshot_id: str,
    stats: dict[str, Any],
) -> None:
    identifiers = [explicit_identifier(item) for item in dedupe_items(items)]
    identifiers = [identifier for identifier in identifiers if identifier is not None]
    stats["eligible"] = len(identifiers)
    if settings.max_details is not None and len(identifiers) > settings.max_details:
        identifiers = identifiers[: settings.max_details]
        stats["truncated"] = True
    await collect_harbour_detail_identifiers(fetcher, identifiers, target_dir, snapshot_id, stats)


async def collect_harbour_detail_identifiers(
    fetcher: AsyncFetcher,
    identifiers: list[str],
    target_dir: Path,
    snapshot_id: str,
    stats: dict[str, Any],
) -> None:
    for identifier in identifiers:
        url = f"{HARBOUR_TOPIC_DETAIL_URL}/{quote(identifier, safe='')}"
        result = await fetcher.request("GET", url, params={"sourceType": 2})
        stats["requested"] += 1
        if result.ok and result.json_data is not None:
            write_json(
                target_dir / f"{slugify(identifier, 'topic')}.json",
                wrap_raw_result(
                    result,
                    {"name": "harbour_topic_detail", "endpoint": HARBOUR_TOPIC_DETAIL_URL, "method": "GET"},
                    {"snapshot_id": snapshot_id, "identifier": identifier, "sourceType": 2},
                ),
            )
            stats["succeeded"] += 1
        else:
            stats["failed"] += 1
            bump(stats["errors"], result.error_category or "unknown_error")
            if result.error_category in {"http_401_unauthorized", "http_403_forbidden"}:
                break


def load_snapshot_topic_ids(settings: CrawlSettings, snapshot_id: str) -> set[str]:
    source_dir = settings.raw_dir / "lists" / f"refresh_{snapshot_id}" / "harbour_topics"
    if not source_dir.exists():
        raise FileNotFoundError(f"refresh snapshot not found: {source_dir}")
    identifiers: set[str] = set()
    for path in sorted(source_dir.glob("page_*.json")):
        payload = read_json(path)
        for item in extract_items(payload.get("data")):
            if isinstance(item, dict):
                identifiers.add(item_identity(item))
    return identifiers


def captured_harbour_detail_ids(settings: CrawlSettings) -> set[str]:
    """Return only IDs represented by valid public detail payloads."""

    identifiers: set[str] = set()
    details_dir = settings.raw_dir / "details"
    if not details_dir.exists():
        return identifiers
    for path in sorted(details_dir.glob("**/*.json")):
        payload = read_json(path)
        source_url = payload.get("request", {}).get("url") or payload.get("source_api", {}).get("endpoint") or ""
        if not source_url.startswith(HARBOUR_TOPIC_DETAIL_URL + "/"):
            continue
        detail = payload.get("data")
        if isinstance(detail, dict):
            identifiers.update(
                item_identity(item)
                for item in extract_items(detail)
                if isinstance(item, dict)
            )
            for key in ("data", "result", "detail", "item"):
                nested = detail.get(key)
                if isinstance(nested, dict):
                    identifier = explicit_identifier(nested)
                    if identifier is not None:
                        identifiers.add(identifier)
            identifier = explicit_identifier(detail)
            if identifier is not None:
                identifiers.add(identifier)
    return identifiers


def default_snapshot_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def validate_snapshot_id(snapshot_id: str) -> str:
    if not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
        raise ValueError("snapshot_id must use letters, digits, dot, underscore, or hyphen and be at most 64 characters")
    return snapshot_id


def snapshot_layout(settings: CrawlSettings, snapshot_id: str) -> dict[str, Path]:
    name = f"refresh_{snapshot_id}"
    return {
        "lists": settings.raw_dir / "lists" / name,
        "details": settings.raw_dir / "details" / name,
        "taxonomy": settings.raw_dir / "taxonomy" / name,
    }


def ensure_snapshot_is_new(layout: Mapping[str, Path]) -> None:
    conflicts = [str(path) for path in layout.values() if path.exists()]
    if conflicts:
        raise FileExistsError(f"snapshot already exists; choose a new --snapshot-id: {', '.join(conflicts)}")


def normalized_record_keys(records: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for record in records:
        host = urlparse(str(record.get("source_url") or "")).netloc
        identifier = record.get("id") or record.get("uuid")
        if host and identifier not in (None, ""):
            keys.add((host, str(identifier)))
    return keys


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in items:
        identifier = item_identity(item)
        if identifier in seen:
            continue
        seen.add(identifier)
        output.append(item)
    return output


def explicit_identifier(item: dict[str, Any]) -> str | None:
    for key in ID_KEYS:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def has_failures(stats: dict[str, Any]) -> bool:
    taxonomy_failed = any(item["failed"] for item in stats["taxonomy_sources"].values())
    list_failed = any(item["failed"] for item in stats["list_sources"].values())
    return bool(taxonomy_failed or list_failed or stats["details"]["failed"])


def bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1
