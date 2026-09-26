#!/usr/bin/env python3
"""Regenerate the 10 poster cleanup samples with less visible background seams."""

from __future__ import annotations

from pathlib import Path
import importlib.util
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "original_type_samples_manifest.md"
POSTER_CLEANUP_SCRIPT = Path("/Users/liujunliang/.codex/skills/poster-cleanup/scripts/poster_cleanup.py")
_spec = importlib.util.spec_from_file_location("poster_cleanup_skill_script", POSTER_CLEANUP_SCRIPT)
assert _spec and _spec.loader
poster_cleanup = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = poster_cleanup
_spec.loader.exec_module(poster_cleanup)


def sample_paths() -> list[Path]:
    paths: list[Path] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        parts = line.split(" ", 2)
        if len(parts) == 3 and parts[0].rstrip(".").isdigit():
            paths.append(Path(parts[2]))
    return paths


def clamp_rect(rect: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = rect
    return max(0, left), max(0, top), min(width, right), min(height, bottom)


def inpaint_rects(
    image: np.ndarray,
    rects: list[tuple[int, int, int, int]],
    *,
    radius: int,
    method: int,
) -> np.ndarray:
    height, width = image.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    for rect in rects:
        left, top, right, bottom = clamp_rect(rect, width, height)
        mask[top:bottom, left:right] = 255
    return cv2.inpaint(image, mask, radius, method)


def detected_qr_rect(path: Path) -> tuple[int, int, int, int] | None:
    width, height = poster_cleanup.identify_size(path)
    rect = poster_cleanup.detect_qr(path, width, height)
    if not rect:
        return None
    return rect.left, rect.top, rect.right + 1, rect.bottom + 1


def cleanup(path: Path) -> None:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"cannot read {path}")
    height, width = image.shape[:2]
    if height >= 1650:
        cleaned = inpaint_rects(image, [(850, 55, 1032, 246)], radius=3, method=cv2.INPAINT_NS)
    else:
        qr = detected_qr_rect(path)
        if qr is None:
            qr = (850, height - 170, 1035, height - 42) if height <= 1450 else (870, height - 185, 1040, height - 42)
        rects = [(qr[0] - 4, qr[1] - 4, qr[2] + 5, qr[3] + 5)]
        if height > 1450:
            left, _top, right, bottom = qr
            rects.append((left - 2, max(0, bottom - 2), right + 3, min(height, bottom + 40)))
        cleaned = inpaint_rects(image, rects, radius=3, method=cv2.INPAINT_TELEA)
    dest = path.with_name(f"Finish{path.name}")
    if not cv2.imwrite(str(dest), cleaned):
        raise RuntimeError(f"cannot write {dest}")


def main() -> int:
    for path in sample_paths():
        cleanup(path)
    print(f"regenerated={len(sample_paths())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
