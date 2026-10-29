"""Template-specific QR removal rules for the HIREP poster set."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class CleanResult:
    image: np.ndarray
    template: str
    rects: tuple[tuple[int, int, int, int], ...]


def scale_rect(rect: tuple[int, int, int, int], width: int, height: int, base: tuple[int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = rect
    base_width, base_height = base
    return (
        round(left * width / base_width),
        round(top * height / base_height),
        round(right * width / base_width),
        round(bottom * height / base_height),
    )


def qr_points(image: np.ndarray) -> np.ndarray | None:
    detector = cv2.QRCodeDetector()
    try:
        found, points = detector.detect(image)
    except cv2.error:
        return None
    return points if found and points is not None else None


def top_right_rect(width: int, height: int, points: np.ndarray | None) -> tuple[int, int, int, int]:
    # Covers the QR, its quiet zone, and the short scan label below it.
    if points is not None:
        coordinates = points.reshape(-1, 2)
        left = max(0, round(float(coordinates[:, 0].min())) - 16)
        top = max(0, round(float(coordinates[:, 1].min())) - 16)
        right = min(width, round(float(coordinates[:, 0].max())) + 17)
        bottom = min(height, round(float(coordinates[:, 1].max())) + 37)
        return left, top, right, bottom
    return scale_rect((872, 54, 1024, 222), width, height, (1080, 1700))


def fill_flat_background(image: np.ndarray, rects: tuple[tuple[int, int, int, int], ...]) -> np.ndarray:
    height, width = image.shape[:2]
    min_top = min(rect[1] for rect in rects)
    max_bottom = max(rect[3] for rect in rects)
    max_right = max(rect[2] for rect in rects)
    sample_left = min(width - 1, max_right + 2)
    sample_right = min(width, sample_left + max(12, round(width * 0.025)))
    sample = image[min_top:max_bottom, sample_left:sample_right]
    # Use a per-row median so subtle vertical footer shading continues naturally.
    row_colors = np.median(sample, axis=1).round().astype(np.uint8)
    cleaned = image.copy()
    for left, top, right, bottom in rects:
        colors = row_colors[top - min_top : bottom - min_top, np.newaxis, :]
        cleaned[top:bottom, left:right] = colors
    return cleaned


def bottom_qr_rects(image: np.ndarray) -> tuple[tuple[int, int, int, int], ...]:
    height, width = image.shape[:2]
    base = (1080, 1520)
    left = scale_rect((850, 1398, 954, 1511), width, height, base)
    right = scale_rect((956, 1398, 1060, 1511), width, height, base)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def dark_density(rect: tuple[int, int, int, int]) -> float:
        x1, y1, x2, y2 = rect
        return float((gray[y1:y2, x1:x2] < 120).mean())

    # A double-code footer contains dense black QR pixels in both fixed slots.
    return (left, right) if dark_density(left) > 0.16 and dark_density(right) > 0.16 else (right,)


def clean(image: np.ndarray) -> CleanResult:
    height, width = image.shape[:2]
    if height <= 1450:
        rect = scale_rect((928, 1314, 1032, 1412), width, height, (1080, 1440))
        return CleanResult(fill_flat_background(image, (rect,)), "bottom_iventure_flat_fill", (rect,))

    if height >= 1650:
        rect = top_right_rect(width, height, None)
        mask = np.zeros((height, width), dtype=np.uint8)
        left, top, right, bottom = rect
        mask[top:bottom, left:right] = 255
        return CleanResult(cv2.inpaint(image, mask, 3, cv2.INPAINT_NS), "top_right_dark_tight_ns", (rect,))

    points = qr_points(image)
    if points is not None and float(points[:, :, 1].mean()) < height * 0.3:
        rect = top_right_rect(width, height, points)
        mask = np.zeros((height, width), dtype=np.uint8)
        left, top, right, bottom = rect
        mask[top:bottom, left:right] = 255
        return CleanResult(cv2.inpaint(image, mask, 3, cv2.INPAINT_NS), "top_right_dark_tight_ns", (rect,))

    rects = bottom_qr_rects(image)
    return CleanResult(fill_flat_background(image, rects), "bottom_standard_flat_fill", rects)
