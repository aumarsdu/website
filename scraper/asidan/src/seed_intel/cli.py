from __future__ import annotations

import argparse
import json
from pathlib import Path

from seed_intel.config import PROJECT_ROOT
from seed_intel.crawler.run_crawl import run_crawl
from seed_intel.db.init_db import init_sqlite_db
from seed_intel.reports.export_report import (
    export_all,
    export_crm_cards,
    export_projects,
    export_topics,
    load_latest_projects,
    write_coverage_report,
    write_quality_report,
    write_scores,
)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seed-intel")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")

    crawl = sub.add_parser("crawl")
    crawl.add_argument("mode", choices=["full", "incremental"])
    crawl.add_argument("--dry-run", action="store_true")
    crawl.add_argument("--max-pages", type=int, default=20)
    crawl.add_argument("--rate-limit", type=float, default=None)
    crawl.add_argument("--timeout", type=float, default=None)
    crawl.add_argument("--retries", type=int, default=None)
    crawl.add_argument("--resume-batch", type=str, default=None)

    parse = sub.add_parser("parse")
    parse.add_argument("kind", choices=["documents"])

    extract = sub.add_parser("extract")
    extract.add_argument("kind", choices=["projects"])

    score = sub.add_parser("score")
    score.add_argument("kind", choices=["projects"])

    generate = sub.add_parser("generate")
    generate.add_argument("kind", choices=["xhs-topics", "crm-cards"])

    sub.add_parser("detect").add_argument("kind", choices=["changes"])
    export = sub.add_parser("export")
    export.add_argument("kind", choices=["all"])
    report = sub.add_parser("report")
    report.add_argument("kind", choices=["coverage", "quality", "changes"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()

    if args.command == "init-db":
        _print_json({"db_path": str(init_sqlite_db(root))})
        return 0

    if args.command == "crawl":
        result = run_crawl(
            mode=args.mode,
            root=root,
            max_pages=args.max_pages,
            rate_limit=args.rate_limit,
            timeout=args.timeout,
            retries=args.retries,
            dry_run=args.dry_run,
            resume_batch_id=args.resume_batch,
        )
        _print_json(result)
        return 0

    records = load_latest_projects(root)

    if args.command == "parse":
        _print_json({"status": "ok", "note": "PDF parsing runs during crawl for downloaded PDFs."})
        return 0
    if args.command == "extract":
        path = export_projects(root, records)
        _print_json({"records": len(records), "projects_csv": str(path)})
        return 0
    if args.command == "score":
        _print_json({"records": len(records), "scores_jsonl": str(write_scores(root, records))})
        return 0
    if args.command == "generate" and args.kind == "xhs-topics":
        _print_json({"records": len(records), "xhs_topics_csv": str(export_topics(root, records))})
        return 0
    if args.command == "generate" and args.kind == "crm-cards":
        _print_json({"records": len(records), "crm_cards_csv": str(export_crm_cards(root, records))})
        return 0
    if args.command == "detect":
        path = root / "data" / "gold" / "reports" / "change_report.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Change Report\n\n- MVP baseline: no previous batch comparison available.\n", encoding="utf-8")
        _print_json({"change_report": str(path)})
        return 0
    if args.command == "export":
        _print_json(export_all(root, records))
        return 0
    if args.command == "report" and args.kind == "coverage":
        _print_json({"coverage_report": str(write_coverage_report(root, records))})
        return 0
    if args.command == "report" and args.kind == "quality":
        _print_json({"quality_report": str(write_quality_report(root, records))})
        return 0
    if args.command == "report" and args.kind == "changes":
        path = root / "data" / "gold" / "reports" / "change_report.md"
        _print_json({"change_report": str(path)})
        return 0
    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
