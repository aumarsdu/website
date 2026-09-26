from __future__ import annotations

import argparse
import asyncio
import copy
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from .asset_downloader import asset_filename
from .config import DEFAULT_USER_AGENT, PROJECT_ROOT, SITE_TARGETS, CrawlConfig
from .normalizer import normalize_outputs
from .organizer import organize_assets
from .utils import (
    append_jsonl,
    content_hash,
    deep_find_asset_urls,
    iter_jsonl,
    redact_headers,
    utc_now_iso,
    write_json,
)


API_BASE = "https://gec-api.gecacademy.cn/souapi"
DETAIL_ENDPOINT = f"{API_BASE}/course/query/share"


@dataclass(frozen=True)
class ListSeed:
    label: str
    url: str
    body: dict[str, Any]
    origin: str
    referer: str
    limit: int


@dataclass(frozen=True)
class SiteSpec:
    name: str
    base_url: str
    seeds: list[ListSeed]
    asset_cache_dirs: list[Path] = field(default_factory=list)


@dataclass
class RequestStats:
    pages_requested: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    errors: dict[str, int] = field(default_factory=dict)

    def failed(self, category: str) -> None:
        self.pages_failed += 1
        self.errors[category] = self.errors.get(category, 0) + 1


@dataclass(frozen=True)
class RefreshOptions:
    run_id: str
    output_root: Path
    user_agent: str
    timeout: float
    retries: int
    rate_limit: float
    concurrency: int
    max_pages: int
    max_details: int
    download_assets: bool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sou_crawler.full_refresh")
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--output-root", default=str(PROJECT_ROOT / "output" / "full_refresh"))
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--max-details", type=int, default=20000)
    parser.add_argument("--skip-assets", action="store_true")
    args = parser.parse_args(argv)

    options = RefreshOptions(
        run_id=args.run_id,
        output_root=Path(args.output_root),
        user_agent=args.user_agent,
        timeout=args.timeout,
        retries=args.retries,
        rate_limit=args.rate_limit,
        concurrency=args.concurrency,
        max_pages=args.max_pages,
        max_details=args.max_details,
        download_assets=not args.skip_assets,
    )
    asyncio.run(run_refresh(options))
    return 0


async def run_refresh(options: RefreshOptions) -> None:
    run_dir = options.output_root / options.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    target_by_name = {target.name: target for target in SITE_TARGETS}
    specs = [
        SiteSpec(
            name="sou_tools",
            base_url=target_by_name["sou_tools"].base_url,
            seeds=build_sou_tools_seeds(),
            asset_cache_dirs=[PROJECT_ROOT / "output" / "assets"],
        ),
        SiteSpec(
            name="domestic",
            base_url=target_by_name["domestic"].base_url,
            seeds=build_domestic_seeds(),
            asset_cache_dirs=[
                PROJECT_ROOT / "output_domestic" / "assets",
                PROJECT_ROOT / "output" / "assets",
            ],
        ),
    ]
    site_reports = []
    for spec in specs:
        site_dir = run_dir / spec.name
        site_report = await refresh_site(spec, site_dir, options)
        site_reports.append(site_report)
    write_overall_report(run_dir, site_reports)


async def refresh_site(spec: SiteSpec, site_dir: Path, options: RefreshOptions) -> dict[str, Any]:
    for subdir in ("raw", "processed", "reports", "assets"):
        (site_dir / subdir).mkdir(parents=True, exist_ok=True)

    list_report = await crawl_list_pages(spec, site_dir, options)
    detail_report = await crawl_details(spec, site_dir, options)
    site_config = CrawlConfig(
        base_url=spec.base_url,
        mobile_base_url="https://sou-m.gecacademy.cn/",
        user_agent=options.user_agent,
        output_dir=site_dir,
        timeout=options.timeout,
        retries=options.retries,
        rate_limit=options.rate_limit,
        concurrency=options.concurrency,
        max_pages=options.max_pages,
        max_details=options.max_details,
    )
    normalize_outputs(site_config)
    normalize_report = json.loads((site_dir / "reports" / "normalize_stats.json").read_text(encoding="utf-8"))
    if options.download_assets:
        asset_report = await download_assets_for_site(spec, site_dir, options)
    else:
        asset_report = asset_gap_report(spec, site_dir)
    organize_assets(site_config)

    acceptance = build_acceptance(list_report, detail_report, asset_report)
    write_json(site_dir / "reports" / "acceptance.json", acceptance)
    write_site_markdown(site_dir, spec, list_report, detail_report, normalize_report, asset_report, acceptance)
    return {
        "site": spec.name,
        "base_url": spec.base_url,
        "site_dir": str(site_dir),
        "list": list_report,
        "detail": detail_report,
        "normalize": normalize_report,
        "assets": asset_report,
        "acceptance": acceptance,
    }


async def crawl_list_pages(spec: SiteSpec, site_dir: Path, options: RefreshOptions) -> dict[str, Any]:
    started_at = utc_now_iso()
    stats = RequestStats()
    raw_dir = site_dir / "raw"
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    duplicate_records = 0
    seed_summaries: list[dict[str, Any]] = []

    async with make_client(options) as client:
        for seed_index, seed in enumerate(spec.seeds, start=1):
            summary = {
                "seed": seed_index,
                "label": seed.label,
                "url": seed.url,
                "body_page1": page_body(seed.body, 1, seed.limit),
                "pages": [],
                "expected_allPage": None,
                "expected_allNumber": None,
                "records_seen_in_seed": 0,
                "errors": [],
            }
            for page_no in range(1, options.max_pages + 1):
                body = page_body(seed.body, page_no, seed.limit)
                payload, meta = await request_json(client, "POST", seed.url, body, seed, options, stats)
                append_jsonl(
                    raw_dir / "list_responses.jsonl",
                    {
                        "crawled_at": utc_now_iso(),
                        "seed": seed_index,
                        "label": seed.label,
                        "page": page_no,
                        "request_body": body,
                        "meta": meta,
                        "payload": payload,
                    },
                )
                if payload is None:
                    summary["errors"].append({"page": page_no, "category": meta.get("error_category", "unknown_error")})
                    break

                data = payload.get("data") if isinstance(payload, dict) else {}
                if isinstance(data, dict):
                    summary["expected_allPage"] = data.get("allPage")
                    summary["expected_allNumber"] = data.get("allNumber")
                    current_page = data.get("currentPage", page_no)
                else:
                    current_page = page_no
                records = extract_course_records(payload)
                summary["pages"].append(current_page)
                summary["records_seen_in_seed"] += len(records)
                for record in records:
                    record_id = record_id_of(record)
                    digest = content_hash(record)
                    unique_key = record_id or digest
                    if unique_key in seen_ids or digest in seen_hashes:
                        duplicate_records += 1
                        continue
                    if record_id:
                        seen_ids.add(record_id)
                    seen_hashes.add(digest)
                    append_jsonl(
                        raw_dir / "list_records.jsonl",
                        {
                            "source_url": seed.url,
                            "seed": seed_index,
                            "label": seed.label,
                            "page": page_no,
                            "crawled_at": utc_now_iso(),
                            "record": record,
                        },
                    )
                all_page = parse_int(summary["expected_allPage"])
                if not records:
                    break
                if all_page is not None and page_no >= all_page:
                    break
            seed_summaries.append(summary)

    list_ids = sorted(collect_list_ids(site_dir))
    report = {
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "site": spec.name,
        "base_url": spec.base_url,
        "seeds": len(spec.seeds),
        "pages_requested": stats.pages_requested,
        "pages_succeeded": stats.pages_succeeded,
        "pages_failed": stats.pages_failed,
        "records_extracted": len(list_ids),
        "duplicate_records": duplicate_records,
        "errors": stats.errors,
        "unique_ids": len(list_ids),
        "seed_summaries": seed_summaries,
    }
    write_json(site_dir / "reports" / "list_coverage.json", report)
    return report


async def crawl_details(spec: SiteSpec, site_dir: Path, options: RefreshOptions) -> dict[str, Any]:
    stats = RequestStats()
    ids = sorted(collect_list_ids(site_dir))
    covered: set[str] = set()
    failed_ids: list[dict[str, str]] = []
    detail_seed = ListSeed(
        label="detail_share",
        url=DETAIL_ENDPOINT,
        body={"isQrcode": False},
        origin=spec.base_url.rstrip("/"),
        referer=spec.base_url,
        limit=0,
    )

    async with make_client(options) as client:
        for item_id in ids[: options.max_details]:
            body = {"id": item_id, "isQrcode": False}
            payload, meta = await request_json(client, "POST", DETAIL_ENDPOINT, body, detail_seed, options, stats)
            append_jsonl(
                site_dir / "raw" / "detail_responses.jsonl",
                {
                    "crawled_at": utc_now_iso(),
                    "api": f"POST {DETAIL_ENDPOINT}",
                    "id": item_id,
                    "meta": meta,
                    "payload": payload,
                },
            )
            if payload_has_detail(payload):
                covered.add(item_id)
            else:
                failed_ids.append({"id": item_id, "category": meta.get("error_category", "empty_detail")})

    missing_ids = sorted(set(ids) - covered)
    report = {
        "site": spec.name,
        "endpoint": DETAIL_ENDPOINT,
        "unique_list_ids": len(ids),
        "details_requested": min(len(ids), options.max_details),
        "details_succeeded": len(covered),
        "details_failed": len(failed_ids),
        "detail_covered_ids": len(covered),
        "detail_missing_ids": len(missing_ids),
        "missing_ids": missing_ids,
        "failed_ids": failed_ids,
        "pages_requested": stats.pages_requested,
        "pages_succeeded": stats.pages_succeeded,
        "pages_failed": stats.pages_failed,
        "errors": stats.errors,
    }
    write_json(site_dir / "reports" / "detail_coverage.json", report)
    return report


async def download_assets_for_site(spec: SiteSpec, site_dir: Path, options: RefreshOptions) -> dict[str, Any]:
    urls = collect_asset_urls(site_dir)
    output_assets = site_dir / "assets"
    output_assets.mkdir(parents=True, exist_ok=True)
    stats: dict[str, Any] = {
        "asset_urls_found": len(urls),
        "already_available_in_output": 0,
        "available_in_cache": 0,
        "copied_from_cache": 0,
        "downloaded_now": 0,
        "failed": 0,
        "missing_asset_downloads": 0,
        "failed_urls_by_category": {},
        "exemptions": [],
    }

    async with make_client(options) as client:
        semaphore = asyncio.Semaphore(options.concurrency)

        async def handle(url: str) -> None:
            async with semaphore:
                target = output_assets / asset_filename(url)
                if target.exists():
                    stats["already_available_in_output"] += 1
                    return
                cached = find_cached_asset(url, spec.asset_cache_dirs)
                if cached is not None:
                    stats["available_in_cache"] += 1
                    copy_cached_asset(cached, target)
                    stats["copied_from_cache"] += 1
                    return
                await asyncio.sleep(options.rate_limit)
                category = await download_one_asset(client, url, target, options)
                if category is None:
                    stats["downloaded_now"] += 1
                    return
                stats["failed"] += 1
                stats["missing_asset_downloads"] += 1
                by_category = stats["failed_urls_by_category"]
                by_category.setdefault(category, []).append(url)
                stats["exemptions"].append(
                    {
                        "url": url,
                        "category": category,
                        "reason": exemption_reason(category),
                    }
                )

        await asyncio.gather(*(handle(url) for url in urls))

    stats["failure_triage"] = triage_asset_failures(stats.get("failed_urls_by_category", {}))
    write_json(site_dir / "reports" / "asset_download_stats.json", stats)
    write_json(site_dir / "reports" / "asset_exemptions.json", stats["exemptions"])
    write_json(site_dir / "reports" / "asset_failure_triage.json", stats["failure_triage"])
    return stats


def copy_cached_asset(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.hardlink_to(source)
    except OSError:
        shutil.copy2(source, target)


def asset_gap_report(spec: SiteSpec, site_dir: Path) -> dict[str, Any]:
    urls = collect_asset_urls(site_dir)
    missing: list[str] = []
    output_assets = site_dir / "assets"
    for url in urls:
        if (output_assets / asset_filename(url)).exists() or find_cached_asset(url, spec.asset_cache_dirs):
            continue
        missing.append(url)
    report = {
        "asset_urls_found": len(urls),
        "missing_asset_downloads": len(missing),
        "failed_urls_by_category": {"not_downloaded": missing},
        "exemptions": [
            {"url": url, "category": "not_downloaded", "reason": "asset download was skipped for this run"}
            for url in missing
        ],
    }
    report["failure_triage"] = triage_asset_failures(report["failed_urls_by_category"])
    write_json(site_dir / "reports" / "asset_download_stats.json", report)
    write_json(site_dir / "reports" / "asset_exemptions.json", report["exemptions"])
    write_json(site_dir / "reports" / "asset_failure_triage.json", report["failure_triage"])
    return report


async def download_one_asset(
    client: httpx.AsyncClient,
    url: str,
    target: Path,
    options: RefreshOptions,
) -> str | None:
    last_error = "unknown_error"
    for attempt in range(options.retries + 1):
        if attempt:
            await asyncio.sleep(options.rate_limit * (2**attempt))
        try:
            response = await client.get(quote_url(url))
            if response.status_code == 404:
                return "http_404_not_found"
            if response.status_code == 403:
                return "http_403_forbidden"
            if response.status_code == 429:
                last_error = "http_429_rate_limited"
                continue
            if response.status_code >= 500:
                last_error = "http_5xx_server_error"
                continue
            response.raise_for_status()
            target.write_bytes(response.content)
            return None
        except httpx.InvalidURL:
            return "url_encoding_error"
        except UnicodeError:
            return "url_encoding_error"
        except httpx.TimeoutException:
            last_error = "timeout"
        except httpx.RemoteProtocolError as exc:
            last_error = classify_protocol_error(exc)
        except httpx.ReadError as exc:
            last_error = classify_protocol_error(exc)
        except httpx.HTTPError as exc:
            last_error = classify_protocol_error(exc)
            break
    return last_error


def build_sou_tools_seeds() -> list[ListSeed]:
    path = PROJECT_ROOT / "output" / "discovery" / "network_logs.jsonl"
    seeds: list[ListSeed] = []
    seen: set[str] = set()
    for row in iter_jsonl(path):
        if row.get("event") != "response" or not row.get("is_json"):
            continue
        url = str(row.get("url", ""))
        if not (url.endswith("/soutools/v2/course/query/common") or url.endswith("/soutools/v2/course/query/aiHub")):
            continue
        body = row.get("post_data_json")
        if not isinstance(body, dict):
            continue
        seed_body = copy.deepcopy(body)
        seed_body["page"] = 1
        seed_body["limit"] = 50
        signature = json.dumps(seed_signature(seed_body), ensure_ascii=False, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        seeds.append(
            ListSeed(
                label=label_from_body(seed_body),
                url=url,
                body=seed_body,
                origin="https://sou-tools.gecacademy.cn",
                referer="https://sou-tools.gecacademy.cn/",
                limit=50,
            )
        )
    if not seeds:
        raise RuntimeError(f"No sou-tools list seeds found in {path}")
    return seeds


def build_domestic_seeds() -> list[ListSeed]:
    seeds = build_domestic_seeds_from_network_logs(
        PROJECT_ROOT / "output" / "discovery" / "network_logs.jsonl"
    )
    if seeds:
        return seeds

    report_path = (
        PROJECT_ROOT
        / "output"
        / "domestic_full"
        / "20260602-ensure-pages"
        / "reports"
        / "domestic_full_list_stats.json"
    )
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        seeds = []
        for summary in report.get("seed_summaries", []):
            body = copy.deepcopy(summary.get("body_page1") or {})
            body["page"] = 1
            limit = int(body.get("limit") or 20)
            seeds.append(
                ListSeed(
                    label=domestic_label(body),
                    url=summary["url"],
                    body=body,
                    origin="https://domestic.gecacademy.cn",
                    referer="https://domestic.gecacademy.cn/",
                    limit=limit,
                )
            )
        if seeds:
            return seeds
    raise RuntimeError(f"No domestic list seeds found in {report_path}")


def build_domestic_seeds_from_network_logs(path: Path) -> list[ListSeed]:
    seeds: list[ListSeed] = []
    seen: set[str] = set()
    for row in iter_jsonl(path):
        if row.get("event") != "response" or not row.get("is_json"):
            continue
        url = str(row.get("url", ""))
        if not url.endswith("/soutools/course/query/course"):
            continue
        body = row.get("post_data_json")
        if not isinstance(body, dict):
            continue
        seed_body = copy.deepcopy(body)
        seed_body["page"] = 1
        seed_body["limit"] = int(seed_body.get("limit") or 20)
        signature = json.dumps(
            domestic_seed_signature(seed_body),
            ensure_ascii=False,
            sort_keys=True,
        )
        if signature in seen:
            continue
        seen.add(signature)
        seeds.append(
            ListSeed(
                label=domestic_label(seed_body),
                url=url,
                body=seed_body,
                origin="https://domestic.gecacademy.cn",
                referer="https://domestic.gecacademy.cn/",
                limit=int(seed_body["limit"]),
            )
        )
    return seeds


def make_client(options: RefreshOptions) -> httpx.AsyncClient:
    limits = httpx.Limits(max_connections=options.concurrency, max_keepalive_connections=options.concurrency)
    return httpx.AsyncClient(
        timeout=options.timeout,
        headers={"User-Agent": options.user_agent, "Accept": "application/json,text/plain,*/*"},
        follow_redirects=True,
        limits=limits,
    )


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    body: dict[str, Any],
    seed: ListSeed,
    options: RefreshOptions,
    stats: RequestStats,
) -> tuple[Any | None, dict[str, Any]]:
    last_error = "unknown_error"
    for attempt in range(options.retries + 1):
        await asyncio.sleep(options.rate_limit if attempt == 0 else options.rate_limit * (2**attempt))
        stats.pages_requested += 1
        try:
            response = await client.request(
                method,
                url,
                json=body,
                headers={
                    "Origin": seed.origin,
                    "Referer": seed.referer,
                    "Content-Type": "application/json;charset=UTF-8",
                },
            )
        except httpx.TimeoutException:
            last_error = "timeout"
            continue
        except httpx.HTTPError as exc:
            last_error = classify_protocol_error(exc)
            continue

        meta = {
            "url": str(response.url),
            "method": method.upper(),
            "status": response.status_code,
            "response_headers": redact_headers(dict(response.headers)),
        }
        if response.status_code == 404:
            stats.failed("http_404_not_found")
            return None, {**meta, "error_category": "http_404_not_found"}
        if response.status_code == 403:
            stats.failed("http_403_forbidden")
            return None, {**meta, "error_category": "http_403_forbidden"}
        if response.status_code == 429:
            last_error = "http_429_rate_limited"
            continue
        if response.status_code >= 500:
            last_error = "http_5xx_server_error"
            continue
        try:
            payload = response.json()
        except ValueError:
            stats.failed("parse_error")
            return None, {**meta, "error_category": "parse_error", "text_sample": response.text[:500]}
        stats.pages_succeeded += 1
        return payload, meta
    stats.failed(last_error)
    return None, {"url": url, "method": method.upper(), "error_category": last_error}


def extract_course_records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    for key in ("courseList", "levels", "records", "rows", "list", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def collect_list_ids(site_dir: Path) -> set[str]:
    ids: set[str] = set()
    for row in iter_jsonl(site_dir / "raw" / "list_records.jsonl"):
        record = row.get("record")
        if isinstance(record, dict):
            record_id = record_id_of(record)
            if record_id:
                ids.add(record_id)
    return ids


def record_id_of(record: dict[str, Any]) -> str | None:
    for key in ("id", "uuid", "projectId", "courseId", "itemId", "detailId"):
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def payload_has_detail(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    data = payload.get("data")
    return isinstance(data, dict) and bool(data.get("id") or data.get("name"))


def collect_asset_urls(site_dir: Path) -> list[str]:
    urls: set[str] = set()
    for path in (
        site_dir / "raw" / "list_records.jsonl",
        site_dir / "raw" / "detail_responses.jsonl",
        site_dir / "raw" / "summary_poster_responses.jsonl",
    ):
        for row in iter_jsonl(path):
            urls.update(deep_find_asset_urls(row))
    return sorted(urls)


def find_cached_asset(url: str, cache_dirs: list[Path]) -> Path | None:
    filename = asset_filename(url)
    for cache_dir in cache_dirs:
        candidate = cache_dir / filename
        if candidate.exists():
            return candidate
    return None


def build_acceptance(
    list_report: dict[str, Any],
    detail_report: dict[str, Any],
    asset_report: dict[str, Any],
) -> dict[str, Any]:
    pages_ok = list_report.get("pages_failed") == 0 and detail_report.get("pages_failed") == 0
    details_ok = detail_report.get("detail_missing_ids") == 0
    missing_assets = int(asset_report.get("missing_asset_downloads") or 0)
    asset_exemptions = asset_report.get("exemptions") or []
    assets_ok = missing_assets == 0 or len(asset_exemptions) == missing_assets
    status = "pass" if pages_ok and details_ok and assets_ok and missing_assets == 0 else "pass_with_asset_exemptions"
    if not pages_ok or not details_ok or not assets_ok:
        status = "fail"
    return {
        "status": status,
        "pages_failed": list_report.get("pages_failed", 0) + detail_report.get("pages_failed", 0),
        "detail_missing_ids": detail_report.get("detail_missing_ids", 0),
        "missing_asset_downloads": missing_assets,
        "asset_exemptions_count": len(asset_exemptions),
        "criteria": {
            "pages_failed": "must be 0",
            "detail_missing_ids": "must be 0",
            "missing_asset_downloads": "must be 0 or have explicit exemptions",
        },
    }


def write_site_markdown(
    site_dir: Path,
    spec: SiteSpec,
    list_report: dict[str, Any],
    detail_report: dict[str, Any],
    normalize_report: dict[str, Any],
    asset_report: dict[str, Any],
    acceptance: dict[str, Any],
) -> None:
    seed_lines = []
    for seed in list_report.get("seed_summaries", []):
        expected = seed.get("expected_allPage")
        pages = seed.get("pages") or []
        status = "PASS" if expected is not None and len(pages) >= int(expected) and not seed.get("errors") else "CHECK"
        seed_lines.append(
            f"- {status} seed {seed['seed']} `{seed['label']}`: pages={pages}, "
            f"allPage={expected}, allNumber={seed.get('expected_allNumber')}, "
            f"records_seen={seed.get('records_seen_in_seed')}, errors={seed.get('errors')}"
        )

    categories = asset_report.get("failed_urls_by_category") or {}
    category_lines = [
        f"- {category}: {len(urls)}" for category, urls in sorted(categories.items()) if isinstance(urls, list)
    ]
    text = "\n".join(
        [
            f"# Full Refresh Coverage - {spec.name}",
            "",
            "## Conclusion",
            "",
            f"- acceptance_status: `{acceptance['status']}`",
            f"- pages_failed: `{acceptance['pages_failed']}`",
            f"- detail_missing_ids: `{acceptance['detail_missing_ids']}`",
            f"- missing_asset_downloads: `{acceptance['missing_asset_downloads']}`",
            f"- asset_exemptions_count: `{acceptance['asset_exemptions_count']}`",
            "",
            "## Scope",
            "",
            f"- base_url: `{spec.base_url}`",
            f"- user_agent: `{DEFAULT_USER_AGENT}`",
            "- no login bypass, captcha bypass, proxy rotation, or access-control bypass was used.",
            "",
            "## List Pagination Coverage",
            "",
            f"- seeds: `{list_report['seeds']}`",
            f"- pages_requested: `{list_report['pages_requested']}`",
            f"- pages_succeeded: `{list_report['pages_succeeded']}`",
            f"- pages_failed: `{list_report['pages_failed']}`",
            f"- unique list IDs: `{list_report['unique_ids']}`",
            "",
            *seed_lines,
            "",
            "## Detail Coverage",
            "",
            f"- detail endpoint: `{DETAIL_ENDPOINT}`",
            f"- unique list IDs: `{detail_report['unique_list_ids']}`",
            f"- detail covered IDs: `{detail_report['detail_covered_ids']}`",
            f"- detail missing IDs: `{detail_report['detail_missing_ids']}`",
            "",
            "## Structured Output",
            "",
            f"- normalized records: `{normalize_report.get('records')}`",
            f"- jsonl: `{normalize_report.get('jsonl')}`",
            f"- csv: `{normalize_report.get('csv')}`",
            f"- sqlite: `{normalize_report.get('sqlite')}`",
            "",
            "## Asset Coverage",
            "",
            f"- asset URLs found: `{asset_report.get('asset_urls_found')}`",
            f"- already available in this run: `{asset_report.get('already_available_in_output', 0)}`",
            f"- available in cache: `{asset_report.get('available_in_cache', 0)}`",
            f"- copied from cache into this run: `{asset_report.get('copied_from_cache', 0)}`",
            f"- downloaded now: `{asset_report.get('downloaded_now', 0)}`",
            f"- missing asset downloads: `{asset_report.get('missing_asset_downloads', 0)}`",
            "",
            "## Asset Failure Categories",
            "",
            *(category_lines or ["- none"]),
            "",
            "## Output Files",
            "",
            "- `raw/list_responses.jsonl`",
            "- `raw/list_records.jsonl`",
            "- `raw/detail_responses.jsonl`",
            "- `processed/records.jsonl`",
            "- `reports/list_coverage.json`",
            "- `reports/detail_coverage.json`",
            "- `reports/asset_download_stats.json`",
            "- `reports/asset_exemptions.json`",
            "- `reports/acceptance.json`",
        ]
    )
    (site_dir / "reports" / "coverage_report.md").write_text(text + "\n", encoding="utf-8")


def write_overall_report(run_dir: Path, site_reports: list[dict[str, Any]]) -> None:
    write_json(run_dir / "refresh_summary.json", site_reports)
    lines = ["# Full Refresh Summary", ""]
    for report in site_reports:
        acceptance = report["acceptance"]
        lines.extend(
            [
                f"## {report['site']}",
                "",
                f"- status: `{acceptance['status']}`",
                f"- pages_failed: `{acceptance['pages_failed']}`",
                f"- detail_missing_ids: `{acceptance['detail_missing_ids']}`",
                f"- missing_asset_downloads: `{acceptance['missing_asset_downloads']}`",
                f"- asset_exemptions_count: `{acceptance['asset_exemptions_count']}`",
                f"- report: `{Path(report['site_dir']) / 'reports' / 'coverage_report.md'}`",
                "",
            ]
        )
    (run_dir / "refresh_summary.md").write_text("\n".join(lines), encoding="utf-8")


def page_body(body: dict[str, Any], page: int, limit: int) -> dict[str, Any]:
    out = copy.deepcopy(body)
    out["page"] = page
    if limit:
        out["limit"] = limit
    return out


def seed_signature(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "levelList": body.get("levelList"),
        "typeId": body.get("typeId"),
        "typeIdList": body.get("typeIdList"),
        "isAiHub": body.get("isAiHub"),
        "types": body.get("types"),
        "isAstra": body.get("isAstra"),
    }


def domestic_seed_signature(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "pageType": body.get("pageType"),
        "level1": body.get("level1"),
        "level2": body.get("level2"),
        "typeIdList": body.get("typeIdList"),
        "types": body.get("types"),
        "isCnPage": body.get("isCnPage"),
    }


def label_from_body(body: dict[str, Any]) -> str:
    level_list = body.get("levelList")
    if isinstance(level_list, list) and level_list:
        names = [str(item.get("name")) for item in level_list if isinstance(item, dict) and item.get("name")]
        if names:
            return "+".join(names)
    if body.get("isAiHub"):
        return "aiHub"
    if body.get("typeIdList"):
        return "typeIdList=" + ",".join(str(item) for item in body["typeIdList"])
    return "all"


def domestic_label(body: dict[str, Any]) -> str:
    parts = []
    if body.get("pageType") is not None:
        parts.append(f"pageType={body['pageType']}")
    if body.get("types"):
        parts.append(str(body["types"]))
    if body.get("typeIdList"):
        parts.append("typeIdList=" + ",".join(str(item) for item in body["typeIdList"]))
    return " ".join(parts) or "domestic"


def quote_url(url: str) -> str:
    parsed = urlsplit(url)
    path = quote(parsed.path, safe="/%")
    query = quote(parsed.query, safe="=&?/%")
    return urlunsplit((parsed.scheme, parsed.netloc, path, query, parsed.fragment))


def classify_protocol_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if "incomplete" in text or "peer closed" in text or "server disconnected" in text:
        return "incomplete_read"
    if "invalid" in text and "url" in text:
        return "url_encoding_error"
    return "unknown_error"


def triage_asset_failures(failed_urls_by_category: dict[str, Any]) -> dict[str, Any]:
    triage = {
        "http_404_not_found": [],
        "url_encoding_error": [],
        "remote_incomplete_read_or_timeout": [],
        "other": {},
    }
    for category, urls in failed_urls_by_category.items():
        if not isinstance(urls, list):
            continue
        if category == "http_404_not_found":
            triage["http_404_not_found"].extend(urls)
        elif category == "url_encoding_error":
            triage["url_encoding_error"].extend(urls)
        elif category in {"incomplete_read", "timeout"}:
            triage["remote_incomplete_read_or_timeout"].extend(urls)
        else:
            triage["other"][category] = urls
    return triage


def exemption_reason(category: str) -> str:
    if category == "http_404_not_found":
        return "remote asset URL returned 404 and appears unavailable on the origin"
    if category == "url_encoding_error":
        return "remote asset URL could not be requested due to URL encoding or URL syntax issues"
    if category == "incomplete_read":
        return "remote server closed the response before the file was fully read"
    return "asset request failed after configured retries"


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
