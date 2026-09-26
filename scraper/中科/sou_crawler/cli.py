from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from .api_analyzer import analyze_network_logs
from .archive import archive_snapshot_topics, download_snapshot_assets
from .audit import audit_archive, audit_summary
from .cleanup import cleanup_out_of_scope
from .config import AUTHORIZED_DOMAINS, CrawlSettings, DEFAULT_ENTRY_URLS
from .discovery import run_discovery
from .logging_utils import configure_logging
from .pipeline import crawl_details, crawl_lists, download_assets, generate_report, normalize, run_all
from .reconcile import reconcile_site_layout
from .refresh import backfill_harbour_details, refresh_public_topics


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    allowed_domains = set(AUTHORIZED_DOMAINS)
    if args.allowed_domain:
        allowed_domains.update(args.allowed_domain)
    skipped_asset_hosts = set(args.skip_asset_host or [])
    settings = CrawlSettings(
        output_dir=Path(args.output_dir),
        rate_limit=args.rate_limit,
        timeout=args.timeout,
        retries=args.retries,
        concurrency=args.concurrency,
        max_pages=args.max_pages,
        max_details=args.max_details,
        max_assets=args.max_assets,
        allowed_domains=allowed_domains,
        skipped_asset_hosts=skipped_asset_hosts,
    )
    result: Any
    if args.command == "discover":
        result = asyncio.run(
            run_discovery(
                settings,
                entry_urls=args.entry_url or DEFAULT_ENTRY_URLS,
                headed=args.headed,
                interactive=args.interactive,
                wait_ms=args.wait_ms,
                max_body_bytes=args.max_body_bytes,
            )
        )
    elif args.command == "analyze-apis":
        result = analyze_network_logs(settings)
    elif args.command == "crawl-lists":
        result = asyncio.run(crawl_lists(settings, dry_run=args.dry_run))
    elif args.command == "crawl-details":
        result = asyncio.run(crawl_details(settings, dry_run=args.dry_run))
    elif args.command == "refresh-public-topics":
        result = asyncio.run(
            refresh_public_topics(
                settings,
                snapshot_id=args.snapshot_id,
                dry_run=args.dry_run,
            )
        )
    elif args.command == "backfill-details":
        result = asyncio.run(
            backfill_harbour_details(
                settings,
                snapshot_id=args.snapshot_id,
                dry_run=args.dry_run,
            )
        )
    elif args.command == "audit-archive":
        result = audit_summary(audit_archive(settings, snapshot_id=args.snapshot_id))
    elif args.command == "cleanup-out-of-scope":
        if not args.confirm:
            parser.error("cleanup-out-of-scope requires --confirm after reviewing the scope-audit manifest")
        result = cleanup_out_of_scope(settings, snapshot_id=args.snapshot_id)
    elif args.command == "reconcile-site-layout":
        result = reconcile_site_layout(settings)
    elif args.command == "archive-snapshot-topics":
        result = archive_snapshot_topics(
            settings,
            snapshot_id=args.snapshot_id,
            target_dir=Path(args.target_dir),
            dry_run=args.dry_run,
        )
    elif args.command == "download-snapshot-assets":
        result = asyncio.run(
            download_snapshot_assets(
                settings,
                snapshot_id=args.snapshot_id,
                dry_run=args.dry_run,
            )
        )
    elif args.command == "download-assets":
        result = asyncio.run(download_assets(settings, dry_run=args.dry_run))
    elif args.command == "normalize":
        result = normalize(settings)
    elif args.command == "report":
        result = generate_report(settings)
    elif args.command == "all":
        result = asyncio.run(run_all(settings, skip_discovery=args.skip_discovery))
    else:
        parser.error("unknown command")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sou_crawler")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--rate-limit", type=float, default=1.5, help="minimum seconds between requests")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--max-details", type=int, default=200, help="hard cap for new public detail pages")
    parser.add_argument("--max-assets", type=int)
    parser.add_argument("--allowed-domain", action="append", help="explicitly add an authorized API or asset domain")
    parser.add_argument("--skip-asset-host", action="append", help="mark an unreachable asset host as failed and continue")
    parser.add_argument("--verbose", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover")
    discover.add_argument("--entry-url", action="append", help="can be passed multiple times")
    discover.add_argument("--headed", action="store_true")
    discover.add_argument("--interactive", action="store_true", help="pause after each entry for manual clicks/filters")
    discover.add_argument("--wait-ms", type=int, default=6000)
    discover.add_argument("--max-body-bytes", type=int, default=800_000)

    subparsers.add_parser("analyze-apis")

    for command in ("crawl-lists", "crawl-details", "download-assets"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--dry-run", action="store_true")

    refresh = subparsers.add_parser("refresh-public-topics")
    refresh.add_argument("--snapshot-id", help="append-only snapshot identifier, for example 20260730")
    refresh.add_argument("--dry-run", action="store_true")

    backfill = subparsers.add_parser("backfill-details")
    backfill.add_argument("--snapshot-id", required=True, help="refresh snapshot whose public topic details are incomplete")
    backfill.add_argument("--dry-run", action="store_true")

    audit = subparsers.add_parser("audit-archive")
    audit.add_argument("--snapshot-id", required=True, help="refresh snapshot used as the current public list baseline")

    cleanup = subparsers.add_parser("cleanup-out-of-scope")
    cleanup.add_argument("--snapshot-id", required=True, help="scope-audit manifest to validate before deletion")
    cleanup.add_argument("--confirm", action="store_true", help="perform the irreversible local cleanup")

    subparsers.add_parser("reconcile-site-layout")

    archive = subparsers.add_parser("archive-snapshot-topics")
    archive.add_argument("--snapshot-id", required=True, help="refresh snapshot whose newly collected topic directories should be copied")
    archive.add_argument("--target-dir", required=True, help="destination root; preserves category/direction/topic paths")
    archive.add_argument("--dry-run", action="store_true")

    snapshot_assets = subparsers.add_parser("download-snapshot-assets")
    snapshot_assets.add_argument("--snapshot-id", required=True, help="refresh snapshot whose public assets should be downloaded")
    snapshot_assets.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("normalize")
    subparsers.add_parser("report")

    all_parser = subparsers.add_parser("all")
    all_parser.add_argument("--skip-discovery", action="store_true", help="reuse existing discovery logs")
    return parser
