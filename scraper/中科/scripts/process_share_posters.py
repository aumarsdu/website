from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

TYPE_SUMMARY = Path("Poster/_classification/type_summary.json")

FAMILY_TYPES: dict[str, set[str]] = {
    "A": {
        "T01",
        "T04",
        "T06",
        "T07",
        "T10",
        "T12",
        "T13",
        "T17",
        "T18",
        "T20",
        "T22",
        "T23",
        "T24",
        "T25",
        "T26",
        "T28",
        "T29",
        "T30",
        "T31",
        "T32",
        "T33",
        "T34",
        "T35",
        "T36",
        "T37",
        "T38",
        "T39",
        "T41",
        "T42",
        "T43",
        "T44",
        "T45",
        "T46",
        "T47",
        "T48",
        "T49",
        "T50",
        "T51",
        "T52",
    },
    "B": {"T02", "T05", "T08", "T27"},
    "C": {"T03", "T09", "T14", "T15"},
    "D": {"T16", "T21", "T40"},
    "E": {"T11", "T19"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mask QR codes and scan-caption text from share posters.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("output_check_20260703/share_posters/assets/posterH5"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("Poster"))
    parser.add_argument("--type-summary", type=Path, default=TYPE_SUMMARY)
    parser.add_argument("--sample-id", help="Only process files whose name contains this id")
    parser.add_argument("--type-ids", nargs="+", help="Process the representative sample for these type IDs")
    parser.add_argument("--limit", type=int, help="Process at most N images")
    parser.add_argument("--force", action="store_true", help="Overwrite existing Finish* files")
    parser.add_argument("--metadata-out", type=Path, help="Write per-file mask boxes as JSON")
    return parser.parse_args()


def image_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and not path.name.startswith("Finish"):
            yield path


def load_type_summary(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def selected_type_samples(type_summary: list[dict[str, Any]], type_ids: list[str]) -> list[Path]:
    by_id = {item["type_id"]: item for item in type_summary}
    missing = [type_id for type_id in type_ids if type_id not in by_id]
    if missing:
        raise SystemExit(f"Unknown type IDs: {', '.join(missing)}")
    return [Path(by_id[type_id]["sample"]) for type_id in type_ids]


def relative_output_path(src: Path, input_dir: Path, output_dir: Path) -> Path:
    rel = src.relative_to(input_dir)
    return output_dir / rel.parent / f"Finish{rel.name}"


def source_name(src: Path, input_dir: Path) -> str:
    try:
        return src.relative_to(input_dir).parts[0]
    except ValueError:
        return src.parent.name


def type_index(type_summary: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    return {(item["source"], item["size"]): item["type_id"] for item in type_summary}


def family_for_type(type_id: str | None, source: str, size: tuple[int, int]) -> str:
    if type_id:
        for family, type_ids in FAMILY_TYPES.items():
            if type_id in type_ids:
                return family

    width, height = size
    ratio = height / width
    if source.startswith("中方") and ratio > 1.7:
        return "D"
    if 1.31 <= ratio <= 1.36:
        return "B"
    if source.startswith("双教授") and 1.36 <= ratio <= 1.42:
        return "C"
    return "A"


def clamp_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    return int(max(0, x1)), int(max(0, y1)), int(min(width, x2)), int(min(height, y2))


def family_config(family: str, width: int, height: int) -> tuple[tuple[int, int, int, int], tuple[float, float], int]:
    min_dim = min(width, height)
    if family == "A":
        return (int(width * 0.68), int(height * 0.70), int(width * 0.98), int(height * 0.96)), (0.13, 0.23), max(5, min_dim // 120)
    if family == "B":
        return (int(width * 0.65), int(height * 0.66), int(width * 0.96), int(height * 0.88)), (0.10, 0.18), max(5, min_dim // 130)
    if family == "C":
        return (int(width * 0.75), int(height * 0.80), int(width * 0.98), int(height * 0.97)), (0.065, 0.13), max(4, min_dim // 150)
    if family == "D":
        return (int(width * 0.04), int(height * 0.77), int(width * 0.32), int(height * 0.95)), (0.15, 0.25), max(4, min_dim // 160)
    if family == "E":
        return (int(width * 0.78), int(height * 0.76), int(width * 0.98), int(height * 0.97)), (0.07, 0.14), max(4, min_dim // 150)
    return (0, 0, width, height), (0.06, 0.25), max(4, min_dim // 150)


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    out = mask.copy()
    step = max(1, radius // 3)
    for dy in range(-radius, radius + 1, step):
        for dx in range(-radius, radius + 1, step):
            if dx == 0 and dy == 0:
                continue
            src = mask[max(0, -dy) : mask.shape[0] - max(0, dy), max(0, -dx) : mask.shape[1] - max(0, dx)]
            dst = out[max(0, dy) : out.shape[0] - max(0, -dy), max(0, dx) : out.shape[1] - max(0, -dx)]
            dst |= src
    return out


def connected_components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    components: list[tuple[int, int, int, int, int]] = []
    for y0 in range(height):
        xs = np.where(mask[y0] & ~seen[y0])[0]
        for x0 in xs:
            if seen[y0, x0] or not mask[y0, x0]:
                continue
            stack = [(y0, int(x0))]
            seen[y0, x0] = True
            min_x = max_x = int(x0)
            min_y = max_y = y0
            count = 0
            while stack:
                y, x = stack.pop()
                count += 1
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                for ny in (y - 1, y, y + 1):
                    for nx in (x - 1, x, x + 1):
                        if ny == y and nx == x:
                            continue
                        if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            components.append((min_x, min_y, max_x + 1, max_y + 1, count))
    return components


def detect_left_qr_box(gray: np.ndarray, width: int, height: int) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = int(width * 0.04), int(height * 0.77), int(width * 0.32), int(height * 0.95)
    dark = gray[y1:y2, x1:x2] < 100
    if dark.size == 0:
        return None

    col_density = dark[int(dark.shape[0] * 0.25) :].mean(axis=0)
    cols = np.where(col_density > 0.12)[0]
    if len(cols) < 20:
        return None
    cx1, cx2 = int(cols.min()), int(cols.max() + 1)
    sub = dark[:, cx1:cx2]
    row_density = sub.mean(axis=1)
    mask = row_density > 0.13
    runs: list[tuple[int, int, float]] = []
    start: int | None = None
    for idx, value in enumerate(mask):
        if value and start is None:
            start = idx
        if (not value or idx == len(mask) - 1) and start is not None:
            end = idx if not value else idx + 1
            if end - start > 20:
                runs.append((start, end, float(row_density[start:end].mean())))
            start = None
    if not runs:
        return None

    target_width = cx2 - cx1
    by1, by2, _ = max(
        runs,
        key=lambda run: (
            min(run[1] - run[0], target_width) / max(run[1] - run[0], target_width),
            run[0],
        ),
    )
    if by2 - by1 < target_width:
        by1 = max(0, by2 - target_width)
    elif by2 - by1 > target_width:
        by2 = min(dark.shape[0], by1 + target_width)
    return x1 + cx1 - 1, y1 + by1 - 1, x1 + cx2 + 1, y1 + by2 + 1


def detect_qr_box_with_opencv(image: Image.Image) -> tuple[int, int, int, int] | None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return None

    arr = np.asarray(image.convert("RGB"))
    detector = cv2.QRCodeDetector()
    found, points = detector.detect(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    if not found or points is None:
        return None

    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if len(pts) < 4:
        return None
    x1, y1 = np.floor(pts.min(axis=0)).astype(int)
    x2, y2 = np.ceil(pts.max(axis=0)).astype(int)
    width, height = image.size
    if x2 <= x1 or y2 <= y1:
        return None
    return clamp_box((x1 - 1, y1 - 1, x2 + 1, y2 + 1), width, height)


def detect_relaxed_bottom_qr_box(gray: np.ndarray, width: int, height: int, family: str) -> tuple[int, int, int, int] | None:
    try:
        import cv2  # type: ignore
    except ImportError:
        cv2 = None  # type: ignore[assignment]

    rois = [
        (int(width * 0.55), int(height * 0.55), int(width * 0.99), int(height * 0.985)),
        (int(width * 0.68), int(height * 0.65), int(width * 0.99), int(height * 0.985)),
    ]
    if family == "D":
        rois.insert(0, (int(width * 0.03), int(height * 0.70), int(width * 0.38), int(height * 0.98)))

    min_side = min(width, height) * 0.035
    max_side = min(width, height) * 0.18
    candidates: list[tuple[float, int, int, int, int]] = []
    for rx1, ry1, rx2, ry2 in rois:
        dark = gray[ry1:ry2, rx1:rx2] < 170
        if dark.size == 0:
            continue
        dilated = dilate(dark, max(2, min(width, height) // 550))
        if cv2 is not None:
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dilated.astype(np.uint8), 8)
            components = [
                (int(stats[label, cv2.CC_STAT_LEFT]), int(stats[label, cv2.CC_STAT_TOP]), int(stats[label, cv2.CC_STAT_LEFT] + stats[label, cv2.CC_STAT_WIDTH]), int(stats[label, cv2.CC_STAT_TOP] + stats[label, cv2.CC_STAT_HEIGHT]), int(stats[label, cv2.CC_STAT_AREA]))
                for label in range(1, num_labels)
            ]
        else:
            components = connected_components(dilated)

        for cx1, cy1, cx2, cy2, _ in components:
            box_width = cx2 - cx1
            box_height = cy2 - cy1
            side = max(box_width, box_height)
            if side < min_side or side > max_side:
                continue
            ratio = box_width / box_height if box_height else 0
            if not 0.62 <= ratio <= 1.62:
                continue

            sub = dark[cy1:cy2, cx1:cx2]
            ys, xs = np.where(sub)
            if len(xs) < 45:
                continue
            ox1, ox2 = int(xs.min()), int(xs.max() + 1)
            oy1, oy2 = int(ys.min()), int(ys.max() + 1)
            dark_width = ox2 - ox1
            dark_height = oy2 - oy1
            dark_side = max(dark_width, dark_height)
            if dark_side < min_side * 0.65 or dark_side > max_side * 1.05:
                continue
            square_score = 1 - abs(dark_width - dark_height) / max(dark_width, dark_height)
            if square_score < 0.72:
                continue
            density = float(sub[oy1:oy2, ox1:ox2].mean())
            if not 0.18 <= density <= 0.86:
                continue

            ax1, ay1 = rx1 + cx1 + ox1 - 1, ry1 + cy1 + oy1 - 1
            ax2, ay2 = rx1 + cx1 + ox2 + 1, ry1 + cy1 + oy2 + 1
            center_x = (ax1 + ax2) / 2 / width
            center_y = (ay1 + ay2) / 2 / height
            position_score = ((1 - center_x) + center_y) / 2 if family == "D" else (center_x + center_y) / 2
            score = square_score * 3 + density * (1 - density) + position_score + dark_side / min(width, height)
            candidates.append((score, ax1, ay1, ax2, ay2))

    if not candidates:
        return None
    _, x1, y1, x2, y2 = max(candidates, key=lambda item: item[0])
    return clamp_box((x1, y1, x2, y2), width, height)


def detect_qr_modules_box(image: Image.Image, family: str) -> tuple[int, int, int, int]:
    width, height = image.size
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    if family == "D":
        left_box = detect_left_qr_box(gray, width, height)
        if left_box:
            return clamp_box(left_box, width, height)

    roi, size_range, radius = family_config(family, width, height)
    rx1, ry1, rx2, ry2 = roi
    dark = gray[ry1:ry2, rx1:rx2] < 115
    dilated = dilate(dark, radius)
    min_side = size_range[0] * min(width, height)
    max_side = size_range[1] * min(width, height)
    candidates: list[tuple[float, int, int, int, int]] = []

    for cx1, cy1, cx2, cy2, _ in connected_components(dilated):
        box_width = cx2 - cx1
        box_height = cy2 - cy1
        side = max(box_width, box_height)
        if side < min_side or side > max_side:
            continue
        ratio = box_width / box_height if box_height else 0
        if not 0.65 <= ratio <= 1.45:
            continue

        sub = dark[cy1:cy2, cx1:cx2]
        ys, xs = np.where(sub)
        if len(xs) < 80:
            continue
        ox1, ox2 = int(xs.min()), int(xs.max() + 1)
        oy1, oy2 = int(ys.min()), int(ys.max() + 1)
        dark_width = ox2 - ox1
        dark_height = oy2 - oy1
        dark_side = max(dark_width, dark_height)
        if dark_side < min_side * 0.75 or dark_side > max_side * 1.05:
            continue
        density = float(sub[oy1:oy2, ox1:ox2].mean())
        if not 0.16 <= density <= 0.72:
            continue

        square_score = 1 - abs(dark_width - dark_height) / max(dark_width, dark_height)
        center_x = (rx1 + cx1 + cx2) / 2 / width
        center_y = (ry1 + cy1 + cy2) / 2 / height
        position_score = ((1 - center_x) + center_y) / 2 if family == "D" else (center_x + center_y) / 2
        score = square_score * 2 + density * (1 - density) + position_score * 0.4 + dark_side / min(width, height) * 0.4
        candidates.append((score, rx1 + cx1 + ox1 - 1, ry1 + cy1 + oy1 - 1, rx1 + cx1 + ox2 + 1, ry1 + cy1 + oy2 + 1))

    if not candidates:
        opencv_box = detect_qr_box_with_opencv(image)
        if opencv_box:
            return opencv_box
        relaxed_box = detect_relaxed_bottom_qr_box(gray, width, height, family)
        if relaxed_box:
            return relaxed_box
        raise ValueError(f"QR box not detected for family {family}")
    _, x1, y1, x2, y2 = max(candidates, key=lambda item: item[0])
    return clamp_box((x1, y1, x2, y2), width, height)


def expand_qr_box(modules_box: tuple[int, int, int, int], image_size: tuple[int, int], family: str) -> tuple[int, int, int, int]:
    width, height = image_size
    x1, y1, x2, y2 = modules_box
    side = max(x2 - x1, y2 - y1)
    ratio = 0.06 if family in {"A", "B", "C"} else 0.12
    pad = max(3, int(side * ratio))
    return clamp_box((x1 - pad, y1 - pad, x2 + pad, y2 + pad), width, height)


def detect_caption_box(image: Image.Image, qr_box: tuple[int, int, int, int], family: str) -> tuple[int, int, int, int] | None:
    if family not in {"A", "C", "E"}:
        return None

    width, height = image.size
    qx1, qy1, qx2, qy2 = qr_box
    side = max(qx2 - qx1, qy2 - qy1)
    search_pad_x = int(side * (0.02 if family == "A" else 0.25))
    search_height = max(18, int(side * (0.24 if family == "A" else 0.46)))
    sx1, sy1, sx2, sy2 = clamp_box((qx1 - search_pad_x, qy2 + 1, qx2 + search_pad_x, qy2 + 1 + search_height), width, height)
    if sx2 <= sx1 or sy2 <= sy1:
        return None

    gray = np.asarray(image.crop((sx1, sy1, sx2, sy2)).convert("L"), dtype=np.uint8)
    dark = gray < 205
    row_counts = dark.sum(axis=1)
    rows = np.where(row_counts > max(1, dark.shape[1] * 0.006))[0]
    if len(rows) < 4:
        return None
    text_rows = dark[int(rows.min()) : int(rows.max()) + 1, :]
    cols = np.where(text_rows.sum(axis=0) > 0)[0]
    if len(cols) < 6:
        return None

    box = (sx1 + int(cols.min()) - 1, sy1 + int(rows.min()) - 1, sx1 + int(cols.max()) + 2, sy1 + int(rows.max()) + 2)
    x1, y1, x2, y2 = clamp_box(box, width, height)
    if x2 - x1 < max(12, side * 0.18) or y2 - y1 > side * 0.4:
        return None
    return x1, y1, x2, y2


def surrounding_samples(
    arr: np.ndarray,
    box: tuple[int, int, int, int],
    margin: int,
) -> tuple[np.ndarray, np.ndarray]:
    height, width = arr.shape[:2]
    x1, y1, x2, y2 = box
    ox1, oy1, ox2, oy2 = clamp_box((x1 - margin, y1 - margin, x2 + margin, y2 + margin), width, height)
    coords: list[np.ndarray] = []
    values: list[np.ndarray] = []

    ring_mask = np.ones((oy2 - oy1, ox2 - ox1), dtype=bool)
    ring_mask[y1 - oy1 : y2 - oy1, x1 - ox1 : x2 - ox1] = False
    yy, xx = np.where(ring_mask)
    if len(xx) == 0:
        return np.empty((0, 2)), np.empty((0, 3))
    absolute_x = xx + ox1
    absolute_y = yy + oy1
    sample_step = max(1, len(xx) // 6000)
    coords.append(np.column_stack((absolute_x[::sample_step], absolute_y[::sample_step])))
    values.append(arr[absolute_y[::sample_step], absolute_x[::sample_step], :3])
    return np.concatenate(coords), np.concatenate(values)


def initial_patch_from_surroundings(arr: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    height, width = arr.shape[:2]
    x1, y1, x2, y2 = box
    margin = max(8, min(width, height) // 80)
    coords, values = surrounding_samples(arr, (x1, y1, x2, y2), margin)
    if len(coords) < 12:
        fill_color = np.median(arr[max(0, y1 - margin) : min(height, y2 + margin), max(0, x1 - margin) : min(width, x2 + margin), :3].reshape(-1, 3), axis=0)
        return np.tile(fill_color.astype(np.uint8), (y2 - y1, x2 - x1, 1))

    design = np.column_stack((coords[:, 0] / max(width, 1), coords[:, 1] / max(height, 1), np.ones(len(coords))))
    yy, xx = np.mgrid[y1:y2, x1:x2]
    target = np.column_stack((xx.reshape(-1) / max(width, 1), yy.reshape(-1) / max(height, 1), np.ones((y2 - y1) * (x2 - x1))))
    patch_channels = []
    for channel in range(3):
        coef, *_ = np.linalg.lstsq(design, values[:, channel].astype(np.float64), rcond=None)
        patch_channels.append((target @ coef).reshape(y2 - y1, x2 - x1))
    return np.stack(patch_channels, axis=2).clip(0, 255).astype(np.uint8)


def diffuse_box_fill(arr: np.ndarray, box: tuple[int, int, int, int]) -> None:
    height, width = arr.shape[:2]
    x1, y1, x2, y2 = box
    ox1, oy1, ox2, oy2 = clamp_box((x1 - 1, y1 - 1, x2 + 1, y2 + 1), width, height)
    if ox2 - ox1 < 3 or oy2 - oy1 < 3:
        return

    region = arr[oy1:oy2, ox1:ox2, :3].astype(np.float32)
    mask = np.zeros(region.shape[:2], dtype=bool)
    mask[y1 - oy1 : y2 - oy1, x1 - ox1 : x2 - ox1] = True
    region[mask] = initial_patch_from_surroundings(arr, (x1, y1, x2, y2)).reshape(-1, 3)

    side = max(x2 - x1, y2 - y1)
    iterations = min(520, max(120, int(side * 1.4)))
    for _ in range(iterations):
        total = np.zeros_like(region)
        count = np.zeros(region.shape[:2], dtype=np.float32)
        total[1:, :, :] += region[:-1, :, :]
        count[1:, :] += 1
        total[:-1, :, :] += region[1:, :, :]
        count[:-1, :] += 1
        total[:, 1:, :] += region[:, :-1, :]
        count[:, 1:] += 1
        total[:, :-1, :] += region[:, 1:, :]
        count[:, :-1] += 1
        updated = total / count[:, :, None]
        region[mask] = updated[mask]

    arr[oy1:oy2, ox1:ox2, :3] = region.clip(0, 255).astype(np.uint8)


def fill_box_from_surroundings(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    width, height = image.size
    x1, y1, x2, y2 = clamp_box(box, width, height)
    if x2 <= x1 or y2 <= y1:
        return

    arr = np.asarray(image.convert("RGB")).copy()
    diffuse_box_fill(arr, (x1, y1, x2, y2))
    image.paste(Image.fromarray(arr[y1:y2, x1:x2, :3], mode="RGB"), (x1, y1))


def fill_box_with_light_background(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    width, height = image.size
    x1, y1, x2, y2 = clamp_box(box, width, height)
    if x2 <= x1 or y2 <= y1:
        return

    arr = np.asarray(image.convert("RGB")).copy()
    margin = max(8, min(width, height) // 90)
    coords, values = surrounding_samples(arr, (x1, y1, x2, y2), margin)
    if len(values) == 0:
        return
    brightness = values[:, :3].mean(axis=1)
    light_values = values[brightness >= 150]
    if len(light_values) < 20:
        light_values = values
    color = np.median(light_values[:, :3], axis=0).clip(0, 255).astype(np.uint8)
    patch = np.tile(color, (y2 - y1, x2 - x1, 1))
    image.paste(Image.fromarray(patch, mode="RGB"), (x1, y1))


def inpaint_boxes(image: Image.Image, boxes: list[tuple[int, int, int, int]], radius: int = 9) -> bool:
    try:
        import cv2  # type: ignore
    except ImportError:
        return False

    width, height = image.size
    arr = np.asarray(image.convert("RGB"))
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    mask = np.zeros((height, width), dtype=np.uint8)
    for box in boxes:
        x1, y1, x2, y2 = clamp_box(box, width, height)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255
    if not np.any(mask):
        return True
    cleaned = cv2.inpaint(bgr, mask, radius, cv2.INPAINT_TELEA)
    rgb = cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB)
    image.paste(Image.fromarray(rgb, mode="RGB"))
    return True


def mask_poster(image: Image.Image, family: str) -> tuple[Image.Image, dict[str, Any]]:
    img = image.convert("RGB")
    modules_box = detect_qr_modules_box(img, family)
    qr_box = expand_qr_box(modules_box, img.size, family)
    caption_box = detect_caption_box(img, qr_box, family)
    boxes = {"family": family, "qr_modules_box": modules_box, "qr_box": qr_box, "caption_box": caption_box}

    if caption_box:
        fill_box_with_light_background(img, caption_box)
    if family == "D":
        if not inpaint_boxes(img, [qr_box]):
            fill_box_from_surroundings(img, qr_box)
    else:
        fill_box_with_light_background(img, qr_box)
    return img, boxes


def save_image(image: Image.Image, src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        image.save(dest, quality=94, optimize=True, subsampling=0)
    elif suffix == ".png":
        image.save(dest, optimize=True)
    elif suffix == ".webp":
        image.save(dest, quality=94, method=6)
    else:
        image.save(dest)


def main() -> int:
    args = parse_args()
    type_summary = load_type_summary(args.type_summary)
    index = type_index(type_summary)

    if args.type_ids:
        selected = selected_type_samples(type_summary, args.type_ids)
    else:
        selected = list(image_files(args.input_dir))
        if args.sample_id:
            selected = [path for path in selected if args.sample_id in path.name]
        if args.limit is not None:
            selected = selected[: args.limit]

    stats: dict[str, Any] = {"input_dir": str(args.input_dir), "output_dir": str(args.output_dir), "processed": 0, "skipped": 0, "failed": 0, "errors": {}}
    metadata: list[dict[str, Any]] = []
    for src in selected:
        dest = relative_output_path(src, args.input_dir, args.output_dir)
        if dest.exists() and dest.stat().st_size > 0 and not args.force:
            stats["skipped"] += 1
            continue
        try:
            with Image.open(src) as image:
                width, height = image.size
                source = source_name(src, args.input_dir)
                type_id = index.get((source, f"{width}x{height}"))
                family = family_for_type(type_id, source, (width, height))
                processed, boxes = mask_poster(image, family)
                save_image(processed, src, dest)
            stats["processed"] += 1
            metadata.append({"source": str(src), "dest": str(dest), "type_id": type_id, "size": f"{width}x{height}", **boxes})
        except Exception as exc:
            stats["failed"] += 1
            name = type(exc).__name__
            stats["errors"][name] = stats["errors"].get(name, 0) + 1
            metadata.append({"source": str(src), "dest": str(dest), "error": f"{name}: {exc}"})

        total_done = stats["processed"] + stats["skipped"] + stats["failed"]
        if total_done % 100 == 0 or total_done == len(selected):
            print(json.dumps({**stats, "total_selected": len(selected), "current": total_done}, ensure_ascii=False), flush=True)

    if args.metadata_out:
        args.metadata_out.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_out.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**stats, "total_selected": len(selected)}, ensure_ascii=False, indent=2))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
