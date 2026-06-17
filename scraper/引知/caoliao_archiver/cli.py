"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .archive import run_archive
from .config import load_config
from .errors import ArchiveError
from .logging_utils import configure_logging
from .public_archive import run_public_archive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caoliao-archive",
        description="Archive one authorized Caoliao H5 live-code page and associated OpenAPI data.",
    )
    parser.add_argument("--config", default="config.example.json", help="Path to JSON config.")
    parser.add_argument("--dry-run", action="store_true", help="Validate scope and print archive plan.")
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Archive public H5 content without OpenAPI credentials.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug JSON logs.")
    parser.add_argument("--entry-url", help="Override entry URL from config.")
    parser.add_argument("--output-dir", help="Override output directory from config.")
    parser.add_argument("--max-pages", type=int, help="Override maximum record pages per form.")
    parser.add_argument("--max-assets", type=int, help="Override maximum asset downloads.")
    parser.add_argument(
        "--max-external-pages",
        type=int,
        help="Override maximum exact-whitelisted external pages.",
    )
    parser.add_argument("--no-assets", action="store_true", help="Do not download discovered assets.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    try:
        config = load_config(args.config)
        overrides: dict[str, Any] = {}
        if args.entry_url:
            overrides["entry_url"] = args.entry_url
        if args.output_dir:
            overrides["output_dir"] = Path(args.output_dir)
        if args.max_pages is not None:
            overrides["max_pages"] = args.max_pages
        if args.max_assets is not None:
            overrides["max_assets"] = args.max_assets
        if args.max_external_pages is not None:
            overrides["max_external_pages"] = args.max_external_pages
        if args.no_assets:
            overrides["download_assets"] = False
        if overrides:
            config = type(config)(**{**asdict(config), **overrides})
            config.assert_qrcode_in_scope()
        if args.public_only:
            result = run_public_archive(config, dry_run=args.dry_run)
        else:
            result = run_archive(config, dry_run=args.dry_run)
    except ArchiveError as exc:
        print(
            json.dumps(
                {"ok": False, "error_category": exc.category, "message": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    print(json.dumps({"ok": True, "result": _jsonable(result)}, ensure_ascii=False, indent=2))
    return 0


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
