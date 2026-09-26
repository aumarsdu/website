from __future__ import annotations

import argparse
import asyncio

from .config import CrawlConfig, ensure_output_dirs
from .logging_utils import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sou_crawler")
    parser.add_argument(
        "command",
        choices=[
            "discover",
            "analyze-apis",
            "crawl-lists",
            "crawl-details",
            "download-assets",
            "organize-assets",
            "normalize",
            "report",
            "all",
        ],
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--user-agent", default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--retries", type=int, default=None)
    parser.add_argument("--rate-limit", type=float, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--max-details", type=int, default=None)
    parser.add_argument("--discovery-wait-ms", type=int, default=None)
    parser.add_argument("--headed", action="store_true", help="Run Playwright with a visible browser window.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> CrawlConfig:
    config = CrawlConfig()
    updates = {}
    for name in (
        "user_agent",
        "timeout",
        "retries",
        "rate_limit",
        "concurrency",
        "max_pages",
        "max_details",
        "discovery_wait_ms",
    ):
        value = getattr(args, name)
        if value is not None:
            updates[name] = value
    if args.output_dir:
        from pathlib import Path

        updates["output_dir"] = Path(args.output_dir)
    return CrawlConfig(**{**config.__dict__, **updates})


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    config = config_from_args(args)
    ensure_output_dirs(config)

    if args.command == "discover":
        if args.dry_run:
            print("discover entries:")
            for entry in config.discovery_entries:
                print(f"- {entry}")
            return 0
        from .discovery import discover_apis

        asyncio.run(discover_apis(config, headless=not args.headed))
        return 0
    if args.command == "analyze-apis":
        from .classifier import analyze_network_logs, write_api_outputs

        signatures = analyze_network_logs(config)
        write_api_outputs(config, signatures)
        print(f"analyzed {len(signatures)} API candidates")
        return 0
    if args.command == "crawl-lists":
        from .crawler import crawl_lists

        asyncio.run(crawl_lists(config, dry_run=args.dry_run))
        return 0
    if args.command == "crawl-details":
        from .crawler import crawl_details

        asyncio.run(crawl_details(config, dry_run=args.dry_run))
        return 0
    if args.command == "download-assets":
        from .crawler import download_assets

        asyncio.run(download_assets(config, dry_run=args.dry_run))
        return 0
    if args.command == "organize-assets":
        from .organizer import organize_assets

        organize_assets(config)
        return 0
    if args.command == "normalize":
        from .normalizer import normalize_outputs

        normalize_outputs(config)
        return 0
    if args.command == "report":
        from .reporter import generate_report

        generate_report(config)
        return 0
    if args.command == "all":
        if args.dry_run:
            print("all: dry-run will show discovery entries and candidate crawl plans where available")
            for entry in config.discovery_entries:
                print(f"- {entry}")
            return 0
        from .classifier import analyze_network_logs, write_api_outputs
        from .crawler import crawl_details, crawl_lists, download_assets
        from .discovery import discover_apis
        from .normalizer import normalize_outputs
        from .organizer import organize_assets
        from .reporter import generate_report

        asyncio.run(discover_apis(config, headless=not args.headed))
        signatures = analyze_network_logs(config)
        write_api_outputs(config, signatures)
        asyncio.run(crawl_lists(config))
        asyncio.run(crawl_details(config))
        asyncio.run(download_assets(config))
        organize_assets(config)
        normalize_outputs(config)
        generate_report(config)
        return 0
    parser.error("unreachable command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
