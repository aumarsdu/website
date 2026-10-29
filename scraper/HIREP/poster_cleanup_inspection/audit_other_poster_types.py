#!/usr/bin/env python3
"""Create deterministic source/output audits for non-iVENTURE poster types."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


CURRENT_ROOT = Path("Poster/output_pbl_merged_unique_20260710")
SOURCE_ROOT = Path(".")
REPORT_ROOT = Path("poster_cleanup_inspection/other_types_audit_20260710")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def raw_path_for(current_path: Path) -> Path:
    relative = current_path.relative_to(CURRENT_ROOT)
    source_name = relative.parts[0]
    source_relative = Path(*relative.parts[1:])
    filename = source_relative.name
    return SOURCE_ROOT / source_name / source_relative.parent / filename[len("Finish_") :]


def poster_type(width: int, height: int) -> str:
    if height >= 1650:
        return "top_right_dark_long"
    if height <= 1450:
        return "bottom_white_iventure"
    return "bottom_white_standard"


def choose_samples() -> list[tuple[str, Path, Path, tuple[int, int]]]:
    grouped: dict[str, dict[tuple[int, int], tuple[Path, Path]]] = defaultdict(dict)
    for current in sorted(CURRENT_ROOT.rglob("Finish_*")):
        if not current.is_file() or current.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        raw = raw_path_for(current)
        if not raw.is_file():
            continue
        with Image.open(raw) as image:
            width, height = image.size
        kind = poster_type(width, height)
        if kind != "bottom_white_iventure":
            grouped[kind].setdefault((width, height), (raw, current))

    selected: list[tuple[str, Path, Path, tuple[int, int]]] = []
    for kind in ("bottom_white_standard", "top_right_dark_long"):
        for size, pair in sorted(grouped[kind].items())[:3]:
            selected.append((kind, pair[0], pair[1], size))
    return selected


def crop_box(kind: str, size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    if kind == "top_right_dark_long":
        return (760, 0, width, min(height, 330))
    return (740, max(0, height - 360), width, height)


def main() -> int:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    samples = choose_samples()
    cell_width, cell_height = 650, 300
    sheet = Image.new("RGB", (cell_width * 2, cell_height * len(samples)), "white")
    draw = ImageDraw.Draw(sheet)
    records: list[dict[str, object]] = []
    for index, (kind, raw, current, size) in enumerate(samples):
        box = crop_box(kind, size)
        for column, path in enumerate((raw, current)):
            with Image.open(path) as image:
                crop = image.convert("RGB").crop(box)
                crop.thumbnail((cell_width - 24, cell_height - 54))
                x = column * cell_width + (cell_width - crop.width) // 2
                y = index * cell_height + 36 + (cell_height - 54 - crop.height) // 2
                sheet.paste(crop, (x, y))
                draw.text((column * cell_width + 12, index * cell_height + 12), "Original" if column == 0 else "Finish", fill="black")
        records.append(
            {
                "poster_type": kind,
                "size": list(size),
                "source": str(raw),
                "finish": str(current),
                "crop_box": list(box),
            }
        )
    sheet_path = REPORT_ROOT / "other_types_before_after.png"
    sheet.save(sheet_path)
    (REPORT_ROOT / "sample_manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": len(records), "by_type": {kind: sum(1 for r in records if r["poster_type"] == kind) for kind in sorted({r["poster_type"] for r in records})}, "sheet": str(sheet_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
