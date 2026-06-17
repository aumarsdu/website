from __future__ import annotations

import argparse
from pathlib import Path

from .api_crawler import run_api_crawl
from .config import load_settings
from .endpoint_summary import summarize_network, write_summary
from .html_probe import run_static_probe
from .logging_utils import configure_logging
from .playwright_probe import run_login, run_playwright_probe
from .storage import Storage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openision-crawler")
    parser.add_argument("--project-root", default=".", help="Project root containing config/ and data/.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="Run browser XHR/fetch probe. Requires Playwright.")
    sub.add_parser("static-probe", help="Run stdlib public HTML probe without browser dependencies.")
    sub.add_parser("summarize-endpoints", help="Summarize data/probe/network.jsonl.")
    sub.add_parser("login", help="Manual Playwright login and storage_state save.")
    sub.add_parser("init-db", help="Initialize SQLite schema.")
    sub.add_parser(
        "build-libraries",
        help="Build Helipei program, school, and admission case libraries from normalized crawl data.",
    )
    crawl_api = sub.add_parser("crawl-api", help="Run formal API pagination crawl.")
    crawl_api.add_argument("--target", choices=["all", "filters", "majors", "cases"], default="all")
    crawl_api.add_argument("--page-size", type=int, default=100)
    crawl_api.add_argument("--max-pages", type=int)
    crawl_api.add_argument("--dry-run", action="store_true")
    crawl_api.add_argument("--rate-limit", type=float, help="Fixed delay in seconds between requests.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    settings = load_settings(root)
    output_dir = root / settings.output_dir
    logger = configure_logging(output_dir)
    storage = Storage(output_dir / "openision.sqlite")

    if args.command == "init-db":
        storage.init_db()
        logger.info("initialized %s", output_dir / "openision.sqlite")
    elif args.command == "build-libraries":
        from .libraries.build import build_libraries
        from .libraries.io import read_jsonl

        report = build_libraries(root)
        libraries_dir = output_dir / "libraries"
        storage.init_db()
        storage.upsert_program_library(read_jsonl(libraries_dir / "program_library.jsonl"))
        storage.upsert_school_library(read_jsonl(libraries_dir / "school_library.jsonl"))
        storage.upsert_admission_case_library(read_jsonl(libraries_dir / "admission_case_library.jsonl"))
        logger.info("built libraries and synced SQLite tables: %s", report.get("counts", {}))
    elif args.command == "static-probe":
        run_static_probe(settings, storage, logger)
    elif args.command == "probe":
        run_playwright_probe(settings, storage, logger)
    elif args.command == "login":
        run_login(settings, logger)
    elif args.command == "summarize-endpoints":
        rows = summarize_network(output_dir / "probe" / "network.jsonl")
        write_summary(rows, output_dir / "probe")
        logger.info("wrote endpoint summaries with %d endpoint(s)", len(rows))
    elif args.command == "crawl-api":
        stats = run_api_crawl(
            settings=settings,
            storage=storage,
            logger=logger,
            output_dir=output_dir,
            target=args.target,
            page_size=args.page_size,
            max_pages=args.max_pages,
            dry_run=args.dry_run,
            delay=args.rate_limit,
        )
        for stat in stats:
            logger.info(
                "target=%s pages=%s/%s records=%s duplicates=%s total=%s",
                stat.target,
                stat.pages_succeeded,
                stat.pages_requested,
                stat.records_extracted,
                stat.duplicate_records,
                stat.total_reported,
            )


if __name__ == "__main__":
    main()
