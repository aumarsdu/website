from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from .config import Settings
from .http_client import ApiClientError, OpenisionApiClient
from .sanitize import dumps_safe, sanitize_json, sanitize_url
from .storage import Storage, utc_now


FILTER_ENDPOINTS = {
    "major_country_options": "/api/v1/major/country_options",
    "major_subject_options": "/api/v1/major/subject_options",
    "major_faculty_options": "/api/v1/major/faculty_options",
    "case_school_tag_options": "/api/v1/case/school_tag_options",
    "case_subject_options": "/api/v1/case/subject_options",
    "school_country_options": "/api/v1/school/country_options",
    "school_sort_options": "/api/v1/school/sort_options",
    "rank_subject_options": "/api/v1/rank_subject/subject_options",
}


def default_major_params(page: int, size: int) -> dict[str, Any]:
    return {
        "search_type": "school_and_major",
        "data": "",
        "page": page,
        "size": size,
        "sort": "qs",
    }


def default_case_params(page: int, size: int) -> dict[str, Any]:
    return {
        "page": page,
        "size": size,
        "search_type": "keyword",
        "data": "",
        "sort": "qs",
    }


@dataclass
class CrawlStats:
    target: str
    pages_requested: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    records_extracted: int = 0
    duplicate_records: int = 0
    total_reported: int | None = None


class JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("w", encoding="utf-8")

    def write(self, value: Any) -> None:
        self._fh.write(dumps_safe(value) + "\n")

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "JsonlWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def sleep_between_requests(settings: Settings, override: float | None) -> None:
    if override is not None:
        time.sleep(max(0, override))
        return
    time.sleep(random.uniform(settings.request_min_delay_seconds, settings.request_max_delay_seconds))


def normalize_major(item: dict[str, Any]) -> dict[str, Any]:
    school = item.get("school") if isinstance(item.get("school"), dict) else {}
    return {
        "source_type": "major",
        "source_id": str(item.get("id") or ""),
        "major_name_cn": item.get("major_name_cn"),
        "major_name_en": item.get("major_name_en"),
        "school_cn": item.get("school_cn") or school.get("name"),
        "school_en": school.get("name_en"),
        "country": school.get("country"),
        "qs": school.get("qs"),
        "major_direction": item.get("major_direction"),
        "faculty": item.get("faculty"),
        "duration_cn": item.get("duration_cn"),
        "tuition_cn": item.get("tuition_cn"),
        "fees": item.get("fees"),
        "official_url": item.get("official_url"),
        "compassedu_url": item.get("compassedu_url"),
        "tags": item.get("tags") or [],
        "similar_case_count": item.get("similar_case_count"),
        "crawled_at": utc_now(),
    }


def normalize_case(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": "case",
        "source_id": str(item.get("id") or ""),
        "title": item.get("title"),
        "student_name": item.get("student_name"),
        "school_name": item.get("school_name"),
        "major_name": item.get("major_name"),
        "base_info": item.get("base_info"),
        "school_tag": item.get("school_tag"),
        "china_gpa": item.get("china_gpa"),
        "time_news": item.get("time_news"),
        "updated_at": item.get("updated_at"),
        "crawled_at": utc_now(),
    }


def extract_items(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int | None, int | None, int | None]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return [], None, None, None
    items = data.get("items")
    if not isinstance(items, list):
        return [], data.get("total"), data.get("page"), data.get("pages")
    return [item for item in items if isinstance(item, dict)], data.get("total"), data.get("page"), data.get("pages")


def crawl_filters(client: OpenisionApiClient, storage: Storage, run_id: int, output_dir: Path, logger, *, delay: float | None = None, settings: Settings) -> CrawlStats:
    stats = CrawlStats("filters")
    raw_dir = output_dir / "raw" / "filters"
    normalized_dir = output_dir / "normalized" / "filters"
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    for name, path in FILTER_ENDPOINTS.items():
        stats.pages_requested += 1
        try:
            response = client.request_json(path)
            storage.save_raw_response(
                run_id=run_id,
                method="GET",
                url=sanitize_url(response.url),
                status_code=response.status_code,
                content_type=response.content_type,
                body_text=response.body_text,
            )
            storage.upsert_endpoint("GET", path, "filter", None)
            safe_payload = sanitize_json(response.json_data)
            (raw_dir / f"{name}.json").write_text(dumps_safe(safe_payload, indent=2), encoding="utf-8")
            data = safe_payload.get("data") if isinstance(safe_payload, dict) else None
            (normalized_dir / f"{name}.json").write_text(dumps_safe(data if data is not None else [], indent=2), encoding="utf-8")
            stats.pages_succeeded += 1
            stats.records_extracted += len(data) if isinstance(data, list) else 0
        except Exception as exc:
            stats.pages_failed += 1
            storage.save_error(run_id=run_id, target="filters", method="GET", url=path, error_type=classify_error(exc), message=str(exc), status_code=getattr(exc, "status_code", None))
            logger.error("filter failed %s: %s", path, exc)
        sleep_between_requests(settings, delay)
    return stats


def crawl_paginated(
    *,
    target: str,
    path: str,
    params_factory,
    normalizer,
    source_type: str,
    client: OpenisionApiClient,
    storage: Storage,
    run_id: int,
    output_dir: Path,
    logger,
    settings: Settings,
    page_size: int,
    max_pages: int | None,
    delay: float | None,
) -> CrawlStats:
    stats = CrawlStats(target)
    raw_path = output_dir / "raw" / f"{target}_list.jsonl"
    normalized_path = output_dir / "normalized" / f"{target}_list.jsonl"
    seen_ids: set[str] = set()
    page = 1
    total_pages: int | None = None
    fetched = 0

    with JsonlWriter(raw_path) as raw_writer, JsonlWriter(normalized_path) as normalized_writer:
        while True:
            if max_pages is not None and page > max_pages:
                break
            if total_pages is not None and page > total_pages:
                break
            params = params_factory(page, page_size)
            stats.pages_requested += 1
            try:
                response = client.request_json(path, params=params)
                body_hash = storage.save_raw_response(
                    run_id=run_id,
                    method="GET",
                    url=sanitize_url(response.url),
                    status_code=response.status_code,
                    content_type=response.content_type,
                    body_text=response.body_text,
                    params=params,
                )
                storage.upsert_endpoint("GET", path, "list", body_hash)
                payload = sanitize_json(response.json_data)
                raw_writer.write({"target": target, "page": page, "params": params, "response": payload})
                items, total, response_page, response_pages = extract_items(payload)
                if stats.total_reported is None and isinstance(total, int):
                    stats.total_reported = total
                    total_pages = response_pages if isinstance(response_pages, int) else math.ceil(total / page_size)
                    logger.info("%s total=%s page_size=%s estimated_pages=%s", target, total, page_size, total_pages)
                if not items:
                    logger.info("%s page=%s returned no items; stopping", target, page)
                    break
                for item in items:
                    source_id = str(item.get("id") or "")
                    if not source_id:
                        source_id = f"{target}:{page}:{len(seen_ids)}"
                    if source_id in seen_ids:
                        stats.duplicate_records += 1
                        continue
                    seen_ids.add(source_id)
                    normalized = normalizer(item)
                    raw_writer.write({"record": item})
                    normalized_writer.write(normalized)
                    storage.upsert_source_record(source_type, source_id, item, normalized)
                    stats.records_extracted += 1
                fetched += len(items)
                stats.pages_succeeded += 1
                if isinstance(total, int) and fetched >= total:
                    break
                page = (response_page + 1) if isinstance(response_page, int) else page + 1
            except Exception as exc:
                stats.pages_failed += 1
                storage.save_error(run_id=run_id, target=target, method="GET", url=path, error_type=classify_error(exc), message=str(exc), status_code=getattr(exc, "status_code", None))
                logger.error("%s page=%s failed: %s", target, page, exc)
                break
            sleep_between_requests(settings, delay)
    return stats


def classify_error(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status == 401:
        return "http_401_unauthorized"
    if status == 403:
        return "http_403_forbidden"
    if status == 404:
        return "http_404_not_found"
    if status == 429:
        return "http_429_rate_limited"
    if isinstance(status, int) and status >= 500:
        return "http_5xx_server_error"
    if isinstance(exc, ApiClientError):
        return "unknown_error"
    return "unknown_error"


def write_crawl_report(output_dir: Path, stats: Iterable[CrawlStats]) -> None:
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    rows = [stat.__dict__ for stat in stats]
    (reports_dir / "crawl_report.json").write_text(dumps_safe({"generated_at": utc_now(), "targets": rows}, indent=2), encoding="utf-8")
    lines = [
        "# Openision API Crawl Report",
        "",
        "| Target | Pages Requested | Pages Succeeded | Pages Failed | Records | Duplicates | Total Reported |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['target']} | {row['pages_requested']} | {row['pages_succeeded']} | {row['pages_failed']} | {row['records_extracted']} | {row['duplicate_records']} | {row['total_reported'] or ''} |"
        )
    lines.extend(
        [
            "",
            "## Compliance",
            "- FC authorization token is acquired in memory and is not written to disk.",
            "- Raw response text is sanitized before persistence.",
            "- No login-only student account data is requested by this crawler.",
        ]
    )
    (reports_dir / "crawl_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_api_crawl(
    *,
    settings: Settings,
    storage: Storage,
    logger,
    output_dir: Path,
    target: str,
    page_size: int,
    max_pages: int | None,
    dry_run: bool,
    delay: float | None,
) -> list[CrawlStats]:
    storage.init_db()
    if dry_run:
        logger.info("dry-run target=%s page_size=%s max_pages=%s", target, page_size, max_pages)
        logger.info("filters=%s", ", ".join(FILTER_ENDPOINTS.values()))
        logger.info("majors=/api/v1/major/smart_search params=%s", default_major_params(1, page_size))
        logger.info("cases=/api/v1/cases params=%s", default_case_params(1, page_size))
        return []

    run_id = storage.start_run(f"crawl-api:{target}", f"page_size={page_size} max_pages={max_pages}")
    client = OpenisionApiClient(settings)
    stats: list[CrawlStats] = []
    try:
        if target in {"all", "filters"}:
            stats.append(crawl_filters(client, storage, run_id, output_dir, logger, delay=delay, settings=settings))
        if target in {"all", "majors"}:
            stats.append(
                crawl_paginated(
                    target="majors",
                    path="/api/v1/major/smart_search",
                    params_factory=default_major_params,
                    normalizer=normalize_major,
                    source_type="major",
                    client=client,
                    storage=storage,
                    run_id=run_id,
                    output_dir=output_dir,
                    logger=logger,
                    settings=settings,
                    page_size=page_size,
                    max_pages=max_pages,
                    delay=delay,
                )
            )
        if target in {"all", "cases"}:
            stats.append(
                crawl_paginated(
                    target="cases",
                    path="/api/v1/cases",
                    params_factory=default_case_params,
                    normalizer=normalize_case,
                    source_type="case",
                    client=client,
                    storage=storage,
                    run_id=run_id,
                    output_dir=output_dir,
                    logger=logger,
                    settings=settings,
                    page_size=page_size,
                    max_pages=max_pages,
                    delay=delay,
                )
            )
        write_crawl_report(output_dir, stats)
        storage.finish_run(run_id, "completed")
    except Exception:
        storage.finish_run(run_id, "failed")
        raise
    return stats
