from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sou_crawler.config import DEFAULT_USER_AGENT, PROJECT_ROOT, CrawlConfig
from sou_crawler.full_refresh import (
    RefreshOptions,
    SiteSpec,
    build_domestic_seeds,
    build_sou_tools_seeds,
    crawl_details,
    crawl_list_pages,
    download_assets_for_site,
    record_id_of,
)
from sou_crawler.normalizer import normalize_outputs
from sou_crawler.organizer import organize_assets
from sou_crawler.utils import append_jsonl, iter_jsonl, write_json


DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "incremental"
DEFAULT_BASELINE_ROOTS = [
    PROJECT_ROOT / "output",
    PROJECT_ROOT / "output_domestic",
    PROJECT_ROOT / "output" / "full_refresh" / "20260602-full-refresh",
    PROJECT_ROOT / "output" / "full_refresh" / "20260703-new-check",
    PROJECT_ROOT / "output" / "incremental" / "20260602-082933",
    PROJECT_ROOT / "output" / "incremental" / "20260602-082933" / "new_only",
]


@dataclass(frozen=True)
class IncrementalOptions:
    run_id: str
    output_root: Path
    baseline_roots: list[Path]
    refresh: RefreshOptions
    sites: frozenset[str]
    include_ids: frozenset[str]
    include_only: bool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect only topics not present in prior local crawl outputs."
    )
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
        help="Unique local run identifier.",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--baseline-root", action="append", type=Path, default=None)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--max-details", type=int, default=20000)
    parser.add_argument("--skip-assets", action="store_true")
    parser.add_argument(
        "--site",
        action="append",
        choices=("sou_tools", "domestic"),
        default=None,
        help="Limit the refresh to one or more source sites. Defaults to both sites.",
    )
    parser.add_argument(
        "--include-id",
        action="append",
        default=None,
        metavar="TOPIC_ID",
        help="Also collect a current list ID even when it already exists in the baseline.",
    )
    parser.add_argument(
        "--include-only",
        action="store_true",
        help="With --include-id, collect only the explicitly included current list IDs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned sources and limits without accessing the sites or writing output.",
    )
    args = parser.parse_args(argv)
    if args.include_only and not args.include_id:
        parser.error("--include-only requires at least one --include-id")

    refresh = RefreshOptions(
        run_id=args.run_id,
        output_root=args.output_root,
        user_agent=args.user_agent,
        timeout=args.timeout,
        retries=args.retries,
        rate_limit=args.rate_limit,
        concurrency=args.concurrency,
        max_pages=args.max_pages,
        max_details=args.max_details,
        download_assets=not args.skip_assets,
    )
    options = IncrementalOptions(
        run_id=args.run_id,
        output_root=args.output_root,
        baseline_roots=resolve_baseline_roots(args.baseline_root, args.output_root, args.run_id),
        refresh=refresh,
        sites=frozenset(args.site or ("sou_tools", "domestic")),
        include_ids=frozenset(args.include_id or ()),
        include_only=args.include_only,
    )
    if args.dry_run:
        print_dry_run(options)
        return 0

    asyncio.run(run_incremental(options))
    return 0


async def run_incremental(options: IncrementalOptions) -> None:
    run_dir = options.output_root / options.run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to append to an existing run directory: {run_dir}")
    run_dir.mkdir(parents=True)
    started_at = datetime.now(timezone.utc).isoformat()

    all_specs = [
        SiteSpec(
            name="sou_tools",
            base_url="https://sou-tools.gecacademy.cn/",
            seeds=build_sou_tools_seeds(),
            asset_cache_dirs=asset_cache_dirs("sou_tools", options.baseline_roots),
        ),
        SiteSpec(
            name="domestic",
            base_url="https://domestic.gecacademy.cn/",
            seeds=build_domestic_seeds(),
            asset_cache_dirs=asset_cache_dirs("domestic", options.baseline_roots),
        ),
    ]
    specs = [spec for spec in all_specs if spec.name in options.sites]

    site_reports = []
    for spec in specs:
        site_reports.append(await run_site(spec, run_dir / spec.name, options))

    summary = {
        "run_id": options.run_id,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "baseline_roots": [str(path) for path in options.baseline_roots],
        "sites": site_reports,
        "new_topics_total": sum(int(report["new_topics"]) for report in site_reports),
        "selected_topics_total": sum(int(report["selected_topics"]) for report in site_reports),
        "include_ids": sorted(options.include_ids),
        "included_ids_found": sorted(
            {
                item_id
                for report in site_reports
                for item_id in report["included_ids"]
            }
        ),
    }
    summary["included_ids_missing_from_current_lists"] = sorted(
        options.include_ids - set(summary["included_ids_found"])
    )
    write_json(run_dir / "incremental_summary.json", summary)
    write_summary_markdown(run_dir, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


async def run_site(spec: SiteSpec, site_dir: Path, options: IncrementalOptions) -> dict[str, Any]:
    for name in ("raw", "processed", "reports", "assets"):
        (site_dir / name).mkdir(parents=True, exist_ok=True)

    list_report = await crawl_list_pages(spec, site_dir, options.refresh)
    raw_dir = site_dir / "raw"
    snapshot_records = raw_dir / "current_list_records.jsonl"
    snapshot_responses = raw_dir / "current_list_responses.jsonl"
    shutil.copy2(raw_dir / "list_records.jsonl", snapshot_records)
    shutil.copy2(raw_dir / "list_responses.jsonl", snapshot_responses)

    baseline_ids = collect_baseline_ids(spec.name, options.baseline_roots)
    current_ids = collect_ids(snapshot_records)
    new_ids = current_ids - baseline_ids
    included_ids, selected_ids = select_topic_ids(
        current_ids,
        baseline_ids,
        options.include_ids,
        include_only=options.include_only,
    )
    filter_list_records(snapshot_records, raw_dir / "list_records.jsonl", selected_ids)
    filter_list_responses(snapshot_responses, raw_dir / "list_responses.jsonl", selected_ids)
    current_topics = topic_rows(snapshot_records)
    new_topics = [topic for topic in current_topics if topic["id"] in new_ids]
    selected_topics = topic_rows(raw_dir / "list_records.jsonl")
    write_json(
        site_dir / "reports" / "new_topics.json",
        {
            "site": spec.name,
            "current_topics": len(current_ids),
            "baseline_topics": len(baseline_ids),
            "new_topics": new_topics,
            "included_ids": sorted(included_ids),
            "selected_topics": selected_topics,
        },
    )

    report: dict[str, Any] = {
        "site": spec.name,
        "list": list_report,
        "current_topics": len(current_ids),
        "baseline_topics": len(baseline_ids),
        "new_topics": len(new_ids),
        "new_ids": sorted(new_ids),
        "included_ids": sorted(included_ids),
        "selected_topics": len(selected_ids),
        "details": None,
        "assets": None,
    }
    if not selected_ids:
        return report

    detail_report = await crawl_details(spec, site_dir, options.refresh)
    site_config = CrawlConfig(
        base_url=spec.base_url,
        mobile_base_url="https://sou-m.gecacademy.cn/",
        user_agent=options.refresh.user_agent,
        output_dir=site_dir,
        timeout=options.refresh.timeout,
        retries=options.refresh.retries,
        rate_limit=options.refresh.rate_limit,
        concurrency=options.refresh.concurrency,
        max_pages=options.refresh.max_pages,
        max_details=options.refresh.max_details,
    )
    normalize_outputs(site_config)
    if options.refresh.download_assets:
        asset_report = await download_assets_for_site(spec, site_dir, options.refresh)
    else:
        asset_report = {"skipped": True}
    organize_assets(site_config)
    report["details"] = detail_report
    report["assets"] = asset_report
    return report


def print_dry_run(options: IncrementalOptions) -> None:
    print("incremental-refresh: dry-run")
    print(f"- output directory: {options.output_root / options.run_id}")
    print(f"- baseline roots: {len(options.baseline_roots)}")
    print(f"- targets: {', '.join(sorted(options.sites))}")
    print(f"- explicit include IDs: {len(options.include_ids)}")
    print(f"- max pages: {options.refresh.max_pages}")
    print(f"- rate limit: {options.refresh.rate_limit}s")
    print("- detail, asset, and organize steps run only for newly discovered or explicitly included IDs")


def resolve_baseline_roots(
    explicit_roots: list[Path] | None,
    output_root: Path,
    run_id: str,
) -> list[Path]:
    if explicit_roots:
        return explicit_roots
    roots = list(DEFAULT_BASELINE_ROOTS)
    if output_root.exists():
        for candidate in sorted(output_root.iterdir()):
            if candidate.is_dir() and candidate.name != run_id and candidate not in roots:
                roots.append(candidate)
    return roots


def collect_baseline_ids(site: str, roots: list[Path]) -> set[str]:
    ids: set[str] = set()
    for root in roots:
        for path in list_record_paths(root, site):
            ids.update(collect_ids(path))
    return ids


def list_record_paths(root: Path, site: str) -> list[Path]:
    candidates = [root / "raw" / "list_records.jsonl", root / site / "raw" / "list_records.jsonl"]
    return [path for path in candidates if path.exists()]


def asset_cache_dirs(site: str, roots: list[Path]) -> list[Path]:
    directories: list[Path] = []
    for root in roots:
        for candidate in (root / "assets", root / site / "assets"):
            if candidate.exists() and candidate not in directories:
                directories.append(candidate)
    return directories


def collect_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    for row in iter_jsonl(path):
        record = row.get("record") if isinstance(row, dict) else None
        if isinstance(record, dict):
            course_id = record_id_of(record)
            if course_id:
                ids.add(course_id)
    return ids


def select_topic_ids(
    current_ids: set[str],
    baseline_ids: set[str],
    include_ids: frozenset[str],
    *,
    include_only: bool,
) -> tuple[set[str], set[str]]:
    included_ids = set(include_ids & current_ids)
    if include_only:
        return included_ids, included_ids
    return included_ids, (current_ids - baseline_ids) | included_ids


def filter_list_records(source: Path, destination: Path, allowed_ids: set[str]) -> None:
    write_filtered_jsonl(
        destination,
        [
            row
            for row in iter_jsonl(source)
            if isinstance(row, dict)
            and isinstance(row.get("record"), dict)
            and record_id_of(row["record"]) in allowed_ids
        ],
    )


def filter_list_responses(source: Path, destination: Path, allowed_ids: set[str]) -> None:
    filtered: list[dict[str, Any]] = []
    for row in iter_jsonl(source):
        if not isinstance(row, dict):
            continue
        payload = row.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            continue
        copied = json.loads(json.dumps(row, ensure_ascii=False))
        copied_data = copied["payload"]["data"]
        for key in ("courseList", "levels", "records", "rows", "list", "items"):
            records = copied_data.get(key)
            if isinstance(records, list):
                copied_data[key] = [
                    record
                    for record in records
                    if isinstance(record, dict) and record_id_of(record) in allowed_ids
                ]
        filtered.append(copied)
    write_filtered_jsonl(destination, filtered)


def write_filtered_jsonl(destination: Path, rows: list[dict[str, Any]]) -> None:
    if destination.exists():
        destination.unlink()
    for row in rows:
        append_jsonl(destination, row)


def topic_rows(path: Path) -> list[dict[str, str | None]]:
    topics: list[dict[str, str | None]] = []
    for row in iter_jsonl(path):
        record = row.get("record") if isinstance(row, dict) else None
        if not isinstance(record, dict):
            continue
        course_id = record_id_of(record)
        if course_id:
            topics.append(
                {
                    "id": course_id,
                    "title": text_or_none(record.get("name") or record.get("title")),
                    "teacher": text_or_none(record.get("teacherName") or record.get("teacher")),
                }
            )
    return topics


def text_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def write_summary_markdown(run_dir: Path, summary: dict[str, Any]) -> None:
    lines = ["# Incremental Refresh Summary", ""]
    for report in summary["sites"]:
        details = report.get("details") or {}
        lines.extend(
            [
                f"## {report['site']}",
                "",
                f"- current topics: `{report['current_topics']}`",
                f"- new topics: `{report['new_topics']}`",
                f"- explicit include IDs: `{len(report['included_ids'])}`",
                f"- selected topics: `{report['selected_topics']}`",
                f"- detail missing IDs: `{details.get('detail_missing_ids', 0)}`",
                f"- output: `{run_dir / report['site']}`",
                "",
            ]
        )
    (run_dir / "incremental_summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
