#!/usr/bin/env python3
"""Clean all HIREP poster images into the central Poster folder."""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
from PIL import Image, ImageDraw


ROOT = Path(".").resolve()
OUTPUT_ROOT = ROOT / "Poster"
REPORT_DIR = OUTPUT_ROOT / "_reports"
POSTER_CLEANUP_SCRIPT = Path("/Users/liujunliang/.codex/skills/poster-cleanup/scripts/poster_cleanup.py")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
EXCLUDE_DIRS = {"Poster", "poster_cleanup_inspection", ".venv", ".pytest_cache", "__pycache__"}


_spec = importlib.util.spec_from_file_location("poster_cleanup_skill_script", POSTER_CLEANUP_SCRIPT)
assert _spec and _spec.loader
poster_cleanup = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = poster_cleanup
_spec.loader.exec_module(poster_cleanup)


@dataclass
class ProcessResult:
    source: str
    output: str | None
    width: int
    height: int
    poster_type: str
    method: str
    rects: list[dict[str, int | str]]
    status: str
    error: str | None = None


def source_posters() -> list[Path]:
    posters: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        if path.name.startswith("Finish") or path.name.startswith("Finish_"):
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if "海报" not in path.name and "poster" not in path.name.lower():
            continue
        posters.append(path)
    return sorted(posters)


def output_path_for(source: Path) -> Path:
    relative_parent = source.relative_to(ROOT).parent
    return OUTPUT_ROOT / relative_parent / f"Finish_{source.name}"


def clamp_rect(rect: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = rect
    return max(0, left), max(0, top), min(width, right), min(height, bottom)


def scale_rect(rect: tuple[int, int, int, int], width: int, height: int, base: tuple[int, int]) -> tuple[int, int, int, int]:
    base_w, base_h = base
    left, top, right, bottom = rect
    return (
        round(left * width / base_w),
        round(top * height / base_h),
        round(right * width / base_w),
        round(bottom * height / base_h),
    )


def classify(width: int, height: int) -> str:
    if height >= 1650:
        return "top_right_dark_long"
    if height <= 1450:
        return "bottom_white_iventure"
    return "bottom_white_standard"


def detect_qr_rect(path: Path, width: int, height: int) -> tuple[int, int, int, int] | None:
    rect = poster_cleanup.detect_qr(path, width, height)
    if not rect:
        return None
    return rect.left, rect.top, rect.right + 1, rect.bottom + 1


def mask_plan(path: Path, width: int, height: int) -> tuple[str, str, list[tuple[str, tuple[int, int, int, int]]], int, int]:
    poster_type = classify(width, height)
    if poster_type == "top_right_dark_long":
        rect = scale_rect((850, 55, 1032, 246), width, height, (1080, 1700))
        return poster_type, "template_top_right_ns", [("qr-and-scan-text", rect)], 3, cv2.INPAINT_NS

    if poster_type == "bottom_white_iventure":
        rect = scale_rect((845, 1190, 1038, 1385), width, height, (1080, 1440))
        return poster_type, "template_bottom_iventure_telea", [("qr", rect)], 3, cv2.INPAINT_TELEA

    if 1500 <= height <= 1540 and 1070 <= width <= 1090:
        qr = scale_rect((845, 1325, 1048, 1496), width, height, (1080, 1520))
        left, _top, right, bottom = qr
        scan_text = (left - 2, max(0, bottom - 2), right + 3, min(height, bottom + 40))
        return poster_type, "template_bottom_standard_telea", [("qr", qr), ("scan-text", scan_text)], 3, cv2.INPAINT_TELEA

    qr = detect_qr_rect(path, width, height)
    if qr:
        left, _top, right, bottom = qr
        rects = [("qr", (left - 4, qr[1] - 4, right + 5, bottom + 5))]
        if poster_type == "bottom_white_standard":
            rects.append(("scan-text", (left - 2, max(0, bottom - 2), right + 3, min(height, bottom + 40))))
        return poster_type, "detected_fallback_telea", rects, 3, cv2.INPAINT_TELEA

    return poster_type, "failed_no_qr_plan", [], 3, cv2.INPAINT_TELEA


def process_one(source: Path) -> ProcessResult:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        return ProcessResult(str(source), None, 0, 0, "unknown", "none", [], "failed", "cannot_read_image")
    height, width = image.shape[:2]
    poster_type, method, rects, radius, cv_method = mask_plan(source, width, height)
    if not rects:
        return ProcessResult(str(source), None, width, height, poster_type, method, [], "failed", "no_mask_plan")

    mask = cv2.UMat(height, width, cv2.CV_8UC1).get()
    mask[:, :] = 0
    rect_log: list[dict[str, int | str]] = []
    for label, rect in rects:
        left, top, right, bottom = clamp_rect(rect, width, height)
        if right <= left or bottom <= top:
            continue
        mask[top:bottom, left:right] = 255
        rect_log.append({"label": label, "left": left, "top": top, "right": right, "bottom": bottom})
    if not rect_log:
        return ProcessResult(str(source), None, width, height, poster_type, method, [], "failed", "empty_mask")

    cleaned = cv2.inpaint(image, mask, radius, cv_method)
    output = output_path_for(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), cleaned):
        return ProcessResult(str(source), None, width, height, poster_type, method, rect_log, "failed", "cannot_write_output")
    return ProcessResult(str(source), str(output), width, height, poster_type, method, rect_log, "ok")


def verify_dimensions(results: list[ProcessResult]) -> dict[str, object]:
    mismatches: list[dict[str, object]] = []
    for result in results:
        if result.status != "ok" or not result.output:
            continue
        with Image.open(result.source) as source, Image.open(result.output) as output:
            if source.size != output.size:
                mismatches.append(
                    {
                        "source": result.source,
                        "output": result.output,
                        "source_size": list(source.size),
                        "output_size": list(output.size),
                    }
                )
    return {"checked": sum(1 for r in results if r.status == "ok"), "mismatch_count": len(mismatches), "mismatches": mismatches}


def make_contact_sheet(results: list[ProcessResult], filename: str, *, seed: int, sample_size: int) -> None:
    ok_results = [r for r in results if r.status == "ok" and r.output]
    selected = random.Random(seed).sample(ok_results, min(sample_size, len(ok_results)))
    thumbs: list[Image.Image] = []
    for index, result in enumerate(selected, 1):
        path = Path(result.output or "")
        with Image.open(path) as image:
            image = image.convert("RGB")
            thumb = image.copy()
            thumb.thumbnail((260, 360))
            canvas = Image.new("RGB", (300, 430), "white")
            canvas.paste(thumb, ((300 - thumb.width) // 2, 18))
            draw = ImageDraw.Draw(canvas)
            draw.text((10, 388), f"{index}. {result.width}x{result.height}", fill="black")
            draw.text((10, 406), result.poster_type[:36], fill="black")
            thumbs.append(canvas)
    if not thumbs:
        return
    cols = 5
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 300, rows * 430), (245, 245, 245))
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((index % cols) * 300, (index // cols) * 430))
    sheet.save(REPORT_DIR / filename, quality=92)


def make_region_sheet(results: list[ProcessResult], filename: str, *, seed: int, sample_size: int) -> None:
    ok_results = [r for r in results if r.status == "ok" and r.output]
    selected = random.Random(seed).sample(ok_results, min(sample_size, len(ok_results)))
    thumbs: list[Image.Image] = []
    for index, result in enumerate(selected, 1):
        pair = Image.new("RGB", (520, 240), "white")
        for col, image_path in enumerate([result.source, result.output or ""]):
            with Image.open(image_path) as image:
                image = image.convert("RGB")
                width, height = image.size
                if height >= 1650:
                    box = (800, 0, width, min(height, 300))
                elif height <= 1450:
                    box = (740, max(0, height - 360), width, height)
                else:
                    box = (740, max(0, height - 320), width, height)
                crop = image.crop(box)
                crop.thumbnail((240, 190))
                pair.paste(crop, (10 + col * 260, 18))
        draw = ImageDraw.Draw(pair)
        draw.text((10, 210), f"{index}. {result.width}x{result.height} {result.poster_type}", fill="black")
        thumbs.append(pair)
    if not thumbs:
        return
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 520, rows * 240), (245, 245, 245))
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((index % cols) * 520, (index // cols) * 240))
    sheet.save(REPORT_DIR / filename, quality=94)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    posters = source_posters()
    results: list[ProcessResult] = []
    for index, source in enumerate(posters, 1):
        results.append(process_one(source))
        if index % 500 == 0:
            print(f"processed={index}/{len(posters)}", flush=True)

    status_counts = Counter(r.status for r in results)
    type_counts = Counter(r.poster_type for r in results)
    method_counts = Counter(r.method for r in results)
    dimension_check = verify_dimensions(results)
    report = {
        "source_count": len(posters),
        "output_count": status_counts["ok"],
        "failure_count": status_counts["failed"],
        "status_counts": dict(status_counts),
        "type_counts": dict(type_counts),
        "method_counts": dict(method_counts),
        "dimension_check": dimension_check,
        "output_root": str(OUTPUT_ROOT),
        "failures": [asdict(r) for r in results if r.status != "ok"],
    }
    (REPORT_DIR / "processing_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "processing_results.jsonl").write_text(
        "\n".join(json.dumps(asdict(r), ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )
    make_contact_sheet(results, "random_sample_60_finish.jpg", seed=20260707, sample_size=60)
    make_region_sheet(results, "random_sample_60_qr_region_before_after.jpg", seed=20260707, sample_size=60)

    print(f"source_count={len(posters)} output_count={status_counts['ok']} failures={status_counts['failed']}")
    print(f"type_counts={dict(type_counts)}")
    print(f"method_counts={dict(method_counts)}")
    print(f"dimension_mismatches={dimension_check['mismatch_count']}")
    return 0 if status_counts["failed"] == 0 and dimension_check["mismatch_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
