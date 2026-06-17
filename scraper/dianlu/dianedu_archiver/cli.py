from __future__ import annotations

import argparse
import asyncio
import sys

from .config import DEFAULT_BASE_URL, DEFAULT_SEARCH_URL, DEFAULT_USER_AGENT, load_settings
from .logging_utils import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dianedu_archiver")
    parser.add_argument("--root-dir", default=".", help="项目输出根目录，默认当前目录。")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--search-url", default=DEFAULT_SEARCH_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--rate-limit", type=float, default=2.0, help="单请求最小间隔秒数，默认 2。")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=2, help="保守限制为 1-3。")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--entry-url", action="append", help="额外发现入口，可多次传入。")
    parser.add_argument("--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)
    for command in [
        "check-site",
        "discover-static",
        "discover-browser",
        "analyze-apis",
        "crawl-routes",
        "crawl-search",
        "crawl-lists",
        "crawl-details",
        "crawl-articles",
        "download-assets",
        "normalize",
        "export",
        "report",
        "build-helipei-summer-db",
        "all",
    ]:
        sub.add_parser(command)
    return parser


async def run_command(args: argparse.Namespace) -> int:
    settings = load_settings(args)
    settings.ensure_dirs()
    if args.command == "check-site":
        from .discovery import check_site

        await check_site(settings)
    elif args.command == "discover-static":
        from .discovery import discover_static

        await discover_static(settings)
    elif args.command == "discover-browser":
        from .discovery import discover_browser

        await discover_browser(settings)
    elif args.command == "analyze-apis":
        from .discovery import analyze_apis

        analyze_apis(settings)
    elif args.command == "crawl-routes":
        from .crawler import crawl_routes

        await crawl_routes(settings)
    elif args.command == "crawl-search":
        from .crawler import crawl_search

        await crawl_search(settings)
    elif args.command == "crawl-lists":
        from .crawler import crawl_lists

        await crawl_lists(settings)
    elif args.command == "crawl-details":
        from .crawler import crawl_details

        await crawl_details(settings)
    elif args.command == "crawl-articles":
        from .crawler import crawl_articles

        await crawl_articles(settings)
    elif args.command == "download-assets":
        from .assets import download_assets

        await download_assets(settings)
    elif args.command == "normalize":
        from .normalize import normalize

        normalize(settings)
    elif args.command == "export":
        from .exporter import export_outputs

        export_outputs(settings)
    elif args.command == "report":
        from .report import build_report

        build_report(settings)
    elif args.command == "build-helipei-summer-db":
        from .helipei_summer import build_helipei_summer_db

        stats = build_helipei_summer_db(settings.db_path, settings.processed_dir / "helipei_summer_programs.sqlite")
        print(stats)
    elif args.command == "all":
        from .assets import download_assets
        from .crawler import crawl_articles, crawl_details, crawl_lists, crawl_routes, crawl_search
        from .discovery import analyze_apis, check_site, discover_browser, discover_static
        from .exporter import export_outputs
        from .normalize import normalize
        from .report import build_report

        await check_site(settings)
        await discover_static(settings)
        await discover_browser(settings)
        analyze_apis(settings)
        await crawl_routes(settings)
        await crawl_search(settings)
        await crawl_lists(settings)
        await crawl_details(settings)
        await crawl_articles(settings)
        await download_assets(settings)
        normalize(settings)
        export_outputs(settings)
        build_report(settings)
    return 0


GLOBAL_FLAGS_WITH_VALUE = {
    "--root-dir",
    "--base-url",
    "--search-url",
    "--user-agent",
    "--rate-limit",
    "--timeout",
    "--retries",
    "--concurrency",
    "--max-pages",
    "--entry-url",
}
GLOBAL_FLAGS = {"--dry-run", "--verbose"}


def normalize_argv(argv: list[str]) -> list[str]:
    """Allow global options before or after the subcommand."""
    front: list[str] = []
    rest: list[str] = []
    idx = 0
    while idx < len(argv):
        token = argv[idx]
        if token in GLOBAL_FLAGS:
            front.append(token)
            idx += 1
        elif token in GLOBAL_FLAGS_WITH_VALUE and idx + 1 < len(argv):
            front.extend([token, argv[idx + 1]])
            idx += 2
        else:
            rest.append(token)
            idx += 1
    return front + rest


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(list(sys.argv[1:] if argv is None else argv)))
    configure_logging(args.verbose)
    return asyncio.run(run_command(args))
