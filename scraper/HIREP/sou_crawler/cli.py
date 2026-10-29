from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import load_settings
from .logging_utils import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sou_crawler")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--user-agent", default="AuthorizedResearchCrawler/1.0")
    parser.add_argument("--rate-limit", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--entry-url", action="append", help="Override discovery entry URL. Can be supplied multiple times.")
    parser.add_argument(
        "--known-projects",
        action="append",
        default=[],
        help="Historical projects.jsonl used by crawl-pbl-incremental and audit-pbl. Can be supplied multiple times.",
    )
    parser.add_argument("--trust-env", action="store_true", help="Allow httpx to read proxy and SSL settings from environment variables.")
    parser.add_argument("--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover")
    sub.add_parser("analyze-apis")
    sub.add_parser("crawl-lists")
    sub.add_parser("crawl-details")
    sub.add_parser("download-assets")
    sub.add_parser("crawl-pbl")
    sub.add_parser("crawl-pbl-incremental")
    sub.add_parser("audit-pbl")
    sub.add_parser("normalize")
    sub.add_parser("report")
    sub.add_parser("all")
    return parser


async def run_command(args: argparse.Namespace) -> int:
    settings = load_settings(args)
    settings.ensure_dirs()

    if args.command == "discover":
        from .discovery import discover_network

        await discover_network(settings)
    elif args.command == "analyze-apis":
        from .api_analysis import analyze_network_logs

        analyze_network_logs(settings)
    elif args.command == "crawl-lists":
        from .crawler import crawl_lists

        await crawl_lists(settings)
    elif args.command == "crawl-details":
        from .crawler import crawl_details

        await crawl_details(settings)
    elif args.command == "download-assets":
        from .assets import download_assets

        await download_assets(settings)
    elif args.command == "crawl-pbl":
        from .pbl_crawler import crawl_pbl

        await crawl_pbl(settings)
    elif args.command == "crawl-pbl-incremental":
        from .pbl_crawler import crawl_pbl_incremental

        await crawl_pbl_incremental(settings, [Path(path) for path in args.known_projects])
    elif args.command == "audit-pbl":
        from .pbl_audit import audit_pbl_coverage

        await audit_pbl_coverage(settings, [Path(path) for path in args.known_projects])
    elif args.command == "normalize":
        from .normalize import normalize_data

        normalize_data(settings)
    elif args.command == "report":
        from .report import build_report

        build_report(settings)
    elif args.command == "all":
        from .api_analysis import analyze_network_logs
        from .assets import download_assets
        from .crawler import crawl_details, crawl_lists
        from .discovery import discover_network
        from .normalize import normalize_data
        from .report import build_report

        await discover_network(settings)
        analyze_network_logs(settings)
        await crawl_lists(settings)
        await crawl_details(settings)
        await download_assets(settings)
        normalize_data(settings)
        build_report(settings)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    return asyncio.run(run_command(args))
