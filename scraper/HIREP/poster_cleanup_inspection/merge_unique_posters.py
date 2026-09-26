#!/usr/bin/env python3
"""Merge Finish-prefixed posters by exact content while preserving provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_SOURCES = (
    "output_pbl_new_20260703",
    "output_pbl_full_refresh_20260602",
    "output_pbl_full_20260602",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_paths(source: Path) -> list[Path]:
    return sorted(
        path
        for path in source.rglob("Finish_*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poster-dir", type=Path, default=Path("Poster"))
    parser.add_argument(
        "--destination-name",
        default="output_pbl_merged_unique_20260710",
        help="Name of the newly created directory under --poster-dir.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=list(DEFAULT_SOURCES),
        help="Source directory names in duplicate-preference order.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="Optional pilot cap. Use only with a separate destination name.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    poster_dir = args.poster_dir.resolve()
    destination = poster_dir / args.destination_name
    if destination.exists():
        raise SystemExit(f"Destination already exists: {destination}")

    source_dirs = [(name, poster_dir / name) for name in args.sources]
    missing = [str(path) for _, path in source_dirs if not path.is_dir()]
    if missing:
        raise SystemExit(f"Missing source directories: {', '.join(missing)}")

    destination.mkdir(parents=True)
    manifest_path = destination / "merge_manifest.jsonl"
    seen_hashes: dict[str, dict[str, str]] = {}
    mode_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    duplicate_counts: Counter[str] = Counter()
    source_total = 0
    stopped_early = False

    with manifest_path.open("w", encoding="utf-8") as manifest:
        for source_name, source_dir in source_dirs:
            for source_path in image_paths(source_dir):
                if args.max_files is not None and source_total >= args.max_files:
                    stopped_early = True
                    break
                source_total += 1
                relative_path = source_path.relative_to(source_dir)
                content_hash = sha256(source_path)
                record = {
                    "source_directory": source_name,
                    "source_relative_path": relative_path.as_posix(),
                    "sha256": content_hash,
                }
                existing = seen_hashes.get(content_hash)
                if existing is not None:
                    duplicate_counts[source_name] += 1
                    record.update(
                        {
                            "action": "duplicate_skipped",
                            "kept_source_directory": existing["source_directory"],
                            "kept_relative_path": existing["source_relative_path"],
                        }
                    )
                else:
                    target_path = destination / source_name / relative_path
                    record["output_relative_path"] = target_path.relative_to(destination).as_posix()
                    mode = link_or_copy(source_path, target_path)
                    record.update({"action": "kept", "storage_mode": mode})
                    seen_hashes[content_hash] = {
                        "source_directory": source_name,
                        "source_relative_path": relative_path.as_posix(),
                    }
                    mode_counts[mode] += 1
                    source_counts[source_name] += 1
                manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
            if stopped_early:
                break

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "destination": str(destination),
        "source_priority": args.sources,
        "source_files_scanned": source_total,
        "unique_files_kept": len(seen_hashes),
        "duplicates_skipped": source_total - len(seen_hashes),
        "kept_by_source": dict(source_counts),
        "duplicates_by_source": dict(duplicate_counts),
        "storage_modes": dict(mode_counts),
        "pilot_limited": args.max_files is not None,
        "stopped_early": stopped_early,
    }
    (destination / "merge_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
