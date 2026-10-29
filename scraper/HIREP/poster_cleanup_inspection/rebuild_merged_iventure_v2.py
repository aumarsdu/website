#!/usr/bin/env python3
"""Rebuild the merged poster set with the corrected iVENTURE rule."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
BASE_SIZE = (1080, 1440)
QR_RECT = (928, 1314, 1032, 1412)
BACKGROUND_SAMPLE = (1035, 1320, 1070, 1408)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scale_rect(rect: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = rect
    base_width, base_height = BASE_SIZE
    return (
        round(left * width / base_width),
        round(top * height / base_height),
        round(right * width / base_width),
        round(bottom * height / base_height),
    )


def corrected_iventure_jpeg(source: Path) -> bytes:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read raw source: {source}")
    height, width = image.shape[:2]
    if not (1070 <= width <= 1090 and 1430 <= height <= 1450):
        raise ValueError(f"Unexpected iVENTURE dimensions: {source} -> {width}x{height}")

    left, top, right, bottom = scale_rect(QR_RECT, width, height)
    sample_left, sample_top, sample_right, sample_bottom = scale_rect(BACKGROUND_SAMPLE, width, height)
    sample = image[sample_top:sample_bottom, sample_left:sample_right]
    background = np.median(sample.reshape(-1, 3), axis=0).round().astype(np.uint8)
    image[top:bottom, left:right] = background
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 100])
    if not ok:
        raise ValueError(f"Cannot encode corrected image: {source}")
    return encoded.tobytes()


def raw_path_for(current_path: Path, current_root: Path, source_root: Path) -> Path:
    relative = current_path.relative_to(current_root)
    source_name = relative.parts[0]
    source_relative = Path(*relative.parts[1:])
    filename = source_relative.name
    if not filename.startswith("Finish_"):
        raise ValueError(f"Unexpected output filename: {current_path}")
    return source_root / source_name / source_relative.parent / filename[len("Finish_") :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, default=Path("Poster/output_pbl_merged_unique_20260710"))
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def existing_hashes(current_root: Path) -> dict[str, str]:
    manifest = current_root / "merge_manifest.jsonl"
    if not manifest.is_file():
        return {}
    hashes: dict[str, str] = {}
    with manifest.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            output = record.get("output_relative_path")
            content_hash = record.get("sha256")
            if record.get("action") == "kept" and isinstance(output, str) and isinstance(content_hash, str):
                hashes[output] = content_hash
    return hashes


def main() -> int:
    args = parse_args()
    current_root = args.current.resolve()
    source_root = args.source_root.resolve()
    output_root = args.output.resolve()
    if output_root.exists():
        raise SystemExit(f"Output already exists: {output_root}")
    output_root.mkdir(parents=True)

    current_files = sorted(
        path
        for path in current_root.rglob("Finish_*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    current_hashes = existing_hashes(current_root)
    seen: dict[str, str] = {}
    status_counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    records: list[dict[str, object]] = []

    for current_path in current_files:
        relative = current_path.relative_to(current_root)
        raw_path = raw_path_for(current_path, current_root, source_root)
        method = "kept_existing"
        output_bytes: bytes | None = None
        if raw_path.is_file():
            try:
                raw_size = Image.open(raw_path).size
            except (OSError, ValueError):
                raw_size = None
            if raw_size == (1080, 1440):
                output_bytes = corrected_iventure_jpeg(raw_path)
                method = "iventure_flat_background_fill"
        if output_bytes is None:
            content_hash = current_hashes.get(relative.as_posix()) or sha256_file(current_path)
        else:
            content_hash = sha256_bytes(output_bytes)

        existing = seen.get(content_hash)
        record: dict[str, object] = {
            "current_relative_path": relative.as_posix(),
            "raw_source": str(raw_path),
            "method": method,
            "sha256": content_hash,
        }
        if existing is not None:
            status_counts["duplicate_skipped"] += 1
            record.update({"action": "duplicate_skipped", "kept_output_relative_path": existing})
        else:
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if output_bytes is None:
                os.link(current_path, destination)
                storage_mode = "hardlink"
            else:
                destination.write_bytes(output_bytes)
                storage_mode = "encoded_jpeg"
            seen[content_hash] = relative.as_posix()
            status_counts["kept"] += 1
            method_counts[method] += 1
            record.update({"action": "kept", "output_relative_path": relative.as_posix(), "storage_mode": storage_mode})
        records.append(record)

    manifest = output_root / "merge_manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_root": str(current_root),
        "source_root": str(source_root),
        "output_root": str(output_root),
        "current_files_scanned": len(current_files),
        "unique_files_kept": len(seen),
        "duplicates_skipped": status_counts["duplicate_skipped"],
        "method_counts": dict(method_counts),
        "status_counts": dict(status_counts),
    }
    (output_root / "merge_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
