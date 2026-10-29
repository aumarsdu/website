from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import CrawlConfig
from .crawler import XntjArchiver


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorized public archive crawler for xntj.tv")
    parser.add_argument("command", choices=("discover", "crawl", "report"))
    parser.add_argument("--output", default="archive")
    parser.add_argument("--rate-limit", type=float, default=1.0, help="requests per second, default: 1")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.rate_limit <= 0:
        parser.error("--rate-limit must be greater than zero")
    archiver = XntjArchiver(CrawlConfig(output_dir=Path(args.output), rate_limit=args.rate_limit))
    try:
        if args.command == "discover":
            result = {"discovered_from_sitemap": archiver.discover(), "pending_pages": len(archiver.store.pending_urls())}
        elif args.command == "crawl":
            result = archiver.crawl(max_pages=args.max_pages, dry_run=args.dry_run)
        else:
            result = archiver.store.summary()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        archiver.close()


if __name__ == "__main__":
    main()
