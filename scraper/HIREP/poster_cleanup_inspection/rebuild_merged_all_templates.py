#!/usr/bin/env python3
"""Resumably rebuild the merged poster set using approved template rules."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
from PIL import Image

from poster_template_rules import clean


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def raw_path_for(current_path: Path, current_root: Path, source_root: Path) -> Path:
    relative = current_path.relative_to(current_root)
    source_name = relative.parts[0]
    source_relative = Path(*relative.parts[1:])
    name = source_relative.name
    if not name.startswith("Finish_"):
        raise ValueError(f"Unexpected output name: {current_path}")
    return source_root / source_name / source_relative.parent / name[len("Finish_") :]


def encode(image, suffix: str) -> bytes:
    extension = ".jpg" if suffix.lower() in {".jpg", ".jpeg"} else suffix.lower()
    options = [cv2.IMWRITE_JPEG_QUALITY, 100] if extension == ".jpg" else []
    ok, buffer = cv2.imencode(extension, image, options)
    if not ok:
        raise ValueError(f"Cannot encode output as {extension}")
    return buffer.tobytes()


def read_records(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    records: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            relative = record.get("output_relative_path")
            if isinstance(relative, str):
                records[relative] = record
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, default=Path("Poster/output_pbl_merged_unique_20260710"))
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=800)
    parser.add_argument("--finalize", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    current_root = args.current.resolve()
    source_root = args.source_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    state_path = output_root / "processing_results.jsonl"
    records = read_records(state_path)
    inputs = sorted(
        path
        for path in current_root.rglob("Finish_*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )

    if args.finalize:
        missing = [path.relative_to(current_root).as_posix() for path in inputs if path.relative_to(current_root).as_posix() not in records]
        output_files = [path for path in output_root.rglob("Finish_*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
        method_counts = Counter(str(record.get("method")) for record in records.values())
        hashes = Counter(str(record.get("sha256")) for record in records.values())
        report = {
            "input_count": len(inputs),
            "processed_count": len(records),
            "output_count": len(output_files),
            "missing_count": len(missing),
            "missing_outputs": missing[:100],
            "duplicate_hash_count": sum(count - 1 for count in hashes.values() if count > 1),
            "method_counts": dict(method_counts),
        }
        (output_root / "processing_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0 if not missing else 1

    selected = inputs[args.start : args.start + args.limit]
    with state_path.open("a", encoding="utf-8") as state:
        for index, current in enumerate(selected, args.start + 1):
            relative = current.relative_to(current_root)
            relative_text = relative.as_posix()
            if relative_text in records:
                continue
            raw = raw_path_for(current, current_root, source_root)
            image = cv2.imread(str(raw), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Cannot read raw source: {raw}")
            result = clean(image)
            payload = encode(result.image, current.suffix)
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            with Image.open(raw) as source, Image.open(destination) as output:
                if source.size != output.size:
                    raise ValueError(f"Dimension mismatch: {raw} -> {destination}")
            record = {
                "output_relative_path": relative_text,
                "raw_source": str(raw),
                "method": result.template,
                "rects": [list(rect) for rect in result.rects],
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            state.write(json.dumps(record, ensure_ascii=False) + "\n")
            state.flush()
            if index % 100 == 0:
                print(f"processed={index}/{len(inputs)}", flush=True)
    print(json.dumps({"processed_range": [args.start, args.start + len(selected)], "total": len(inputs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
