from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sou_crawler.storage import iter_jsonl, write_json


POSTER_FIELDS = {"attachmentId", "industryPoster"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy PBL posters from an asset manifest without overwriting existing files.")
    parser.add_argument("--output-dir", required=True, help="PBL output directory containing processed/asset_manifest.jsonl.")
    parser.add_argument("--destination", required=True, help="Destination directory for the copied poster tree.")
    parser.add_argument("--dry-run", action="store_true", help="Report planned copies without creating files.")
    args = parser.parse_args()

    output_dir = resolve_path(args.output_dir)
    destination = resolve_path(args.destination)
    stats = copy_posters(output_dir, destination, dry_run=args.dry_run)
    if not args.dry_run:
        write_json(output_dir / "reports" / "copy_posters_report.json", stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def copy_posters(output_dir: Path, destination: Path, *, dry_run: bool) -> dict[str, Any]:
    assets_dir = output_dir / "assets"
    manifest_path = output_dir / "processed" / "asset_manifest.jsonl"
    copied = 0
    skipped_existing = 0
    missing_source = 0
    invalid_path = 0
    planned = 0
    seen_sources: set[Path] = set()

    for item in iter_jsonl(manifest_path) or []:
        if item.get("field") not in POSTER_FIELDS:
            continue
        source = Path(str(item.get("file") or ""))
        if not source.is_absolute():
            source = PROJECT_ROOT / source
        if source in seen_sources:
            continue
        seen_sources.add(source)
        if not source.is_file():
            missing_source += 1
            continue
        try:
            relative_path = source.relative_to(assets_dir)
        except ValueError:
            invalid_path += 1
            continue
        target = destination / relative_path
        if target.exists():
            skipped_existing += 1
            continue
        planned += 1
        if dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1

    return {
        "output_dir": str(output_dir),
        "destination": str(destination),
        "poster_fields": sorted(POSTER_FIELDS),
        "unique_poster_sources": len(seen_sources),
        "planned": planned,
        "copied": copied,
        "skipped_existing": skipped_existing,
        "missing_source": missing_source,
        "invalid_path": invalid_path,
        "dry_run": dry_run,
    }


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
