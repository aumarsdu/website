#!/usr/bin/env python3
"""Remove QR codes from the flat iVENTURE bottom-banner poster template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


BASE_SIZE = (1080, 1440)
# Includes the QR quiet zone while excluding the nearby divider and date text.
QR_RECT = (928, 1314, 1032, 1412)
BACKGROUND_SAMPLE = (1035, 1320, 1070, 1408)


def scale_rect(rect: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = rect
    base_width, base_height = BASE_SIZE
    return (
        round(left * width / base_width),
        round(top * height / base_height),
        round(right * width / base_width),
        round(bottom * height / base_height),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True, help="Raw poster to process. Repeat for each file.")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def process(source: Path, output_dir: Path) -> dict[str, object]:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {source}")
    height, width = image.shape[:2]
    if not (1070 <= width <= 1090 and 1430 <= height <= 1450):
        raise ValueError(f"Unexpected template dimensions for {source}: {width}x{height}")

    left, top, right, bottom = scale_rect(QR_RECT, width, height)
    sample_left, sample_top, sample_right, sample_bottom = scale_rect(BACKGROUND_SAMPLE, width, height)
    sample = image[sample_top:sample_bottom, sample_left:sample_right]
    color = np.median(sample.reshape(-1, 3), axis=0).round().astype(np.uint8)
    cleaned = image.copy()
    cleaned[top:bottom, left:right] = color

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"Finish_{source.name}"
    if not cv2.imwrite(str(output), cleaned):
        raise ValueError(f"Cannot write image: {output}")
    return {
        "source": str(source),
        "output": str(output),
        "size": [width, height],
        "qr_rect": {"left": left, "top": top, "right": right, "bottom": bottom},
        "background_bgr": color.tolist(),
    }


def main() -> int:
    args = parse_args()
    results = [process(source, args.output_dir) for source in args.source]
    report = args.output_dir / "processing_report.json"
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"processed": len(results), "report": str(report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
