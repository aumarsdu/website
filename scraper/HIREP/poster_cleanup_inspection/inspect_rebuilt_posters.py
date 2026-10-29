#!/usr/bin/env python3
"""Build deterministic visual and QR-detection checks for rebuilt posters."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import cv2
from PIL import Image, ImageDraw


def crop_box(method: str, size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    if method == "top_right_dark_tight_ns":
        return (760, 0, width, min(height, 330))
    return (740, max(0, height - 360), width, height)


def plausible_qr(points, width: int, height: int) -> bool:
    coordinates = points.reshape(-1, 2)
    span_x = float(coordinates[:, 0].max() - coordinates[:, 0].min())
    span_y = float(coordinates[:, 1].max() - coordinates[:, 1].min())
    if span_x <= 0 or span_y <= 0:
        return False
    ratio = span_x / span_y
    min_side = min(width, height)
    return 0.72 <= ratio <= 1.28 and min_side * 0.045 <= span_x <= min_side * 0.22 and min_side * 0.045 <= span_y <= min_side * 0.22


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--per-template", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    records = [json.loads(line) for line in (output / "processing_results.jsonl").read_text(encoding="utf-8").splitlines()]
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[str(record["method"])].append(record)
    selected: list[dict[str, object]] = []
    for method, items in sorted(grouped.items()):
        selected.extend(random.Random(f"{args.seed}:{method}").sample(items, min(args.per_template, len(items))))

    reports = output / "_reports"
    reports.mkdir(exist_ok=True)
    full_tiles: list[Image.Image] = []
    regions: list[Image.Image] = []
    detection: list[dict[str, object]] = []
    for index, record in enumerate(selected, 1):
        raw = Path(str(record["raw_source"]))
        finish = output / str(record["output_relative_path"])
        with Image.open(raw) as source, Image.open(finish) as cleaned:
            source_rgb = source.convert("RGB")
            cleaned_rgb = cleaned.convert("RGB")
            width, height = source_rgb.size
            full = cleaned_rgb.copy()
            full.thumbnail((260, 365))
            full_tile = Image.new("RGB", (280, 405), "white")
            full_tile.paste(full, ((280 - full.width) // 2, 8))
            ImageDraw.Draw(full_tile).text((8, 380), f"{index}. {record['method']}", fill="black")
            full_tiles.append(full_tile)
            box = crop_box(str(record["method"]), (width, height))
            pair = Image.new("RGB", (520, 230), "white")
            for column, image in enumerate((source_rgb, cleaned_rgb)):
                crop = image.crop(box)
                crop.thumbnail((240, 185))
                pair.paste(crop, (10 + column * 260, 26))
            draw = ImageDraw.Draw(pair)
            draw.text((10, 6), "Original", fill="black")
            draw.text((270, 6), "Finish", fill="black")
            draw.text((10, 208), f"{index}. {record['method']}", fill="black")
            regions.append(pair)
        image = cv2.imread(str(finish), cv2.IMREAD_COLOR)
        try:
            found, points = cv2.QRCodeDetector().detect(image)
            detected = bool(found and points is not None and plausible_qr(points, image.shape[1], image.shape[0]))
        except cv2.error:
            detected = False
        detection.append({"output_relative_path": record["output_relative_path"], "method": record["method"], "qr_detected": detected})

    def grid(items: list[Image.Image], cell: tuple[int, int], columns: int) -> Image.Image:
        rows = (len(items) + columns - 1) // columns
        canvas = Image.new("RGB", (cell[0] * columns, cell[1] * rows), (245, 245, 245))
        for index, item in enumerate(items):
            canvas.paste(item, ((index % columns) * cell[0], (index // columns) * cell[1]))
        return canvas

    grid(full_tiles, (280, 405), 4).save(reports / "final_random_12_finish.jpg", quality=95)
    grid(regions, (520, 230), 2).save(reports / "final_random_12_before_after.jpg", quality=95)
    report = {"sample_count": len(selected), "by_template": {key: sum(1 for row in selected if row["method"] == key) for key in sorted(grouped)}, "qr_detect_hits": sum(1 for row in detection if row["qr_detected"]), "detection": detection}
    (reports / "inspection_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
