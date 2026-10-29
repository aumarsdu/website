#!/usr/bin/env python3
"""Clean QR regions for the confirmed poster batch.

The script preserves source posters and writes Finish-prefixed outputs next to
each source image. It uses the refined sample strategy:
- bottom white-bar posters: tight QR mask with small-radius Telea inpainting;
- tall dark posters: top-right fixed QR area with small-radius NS inpainting.
"""

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


ROOT = Path("output_pbl_new_20260703/assets")
INSPECTION_DIR = Path("poster_cleanup_inspection/full_run_20260707")
POSTER_CLEANUP_SCRIPT = Path("/Users/liujunliang/.codex/skills/poster-cleanup/scripts/poster_cleanup.py")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


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
    return sorted(
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and not p.name.startswith("Finish")
        and p.suffix.lower() in IMAGE_SUFFIXES
        and ("海报" in p.name or "poster" in p.name.lower())
    )


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


def detect_qr_rect(path: Path, width: int, height: int) -> tuple[int, int, int, int] | None:
    rect = poster_cleanup.detect_qr(path, width, height)
    if not rect:
        return None
    return rect.left, rect.top, rect.right + 1, rect.bottom + 1


def classify(width: int, height: int) -> str:
    if height >= 1650:
        return "top_right_dark_long"
    if height <= 1450:
        return "bottom_white_iventure"
    return "bottom_white_standard"


def mask_plan(path: Path, width: int, height: int) -> tuple[str, str, list[tuple[str, tuple[int, int, int, int]]], int, int]:
    poster_type = classify(width, height)
    if poster_type == "top_right_dark_long":
        rect = scale_rect((850, 55, 1032, 246), width, height, (1080, 1700))
        return poster_type, "template_top_right_ns", [("qr-and-scan-text", rect)], 3, cv2.INPAINT_NS

    qr = detect_qr_rect(path, width, height)
    method = "detected_bottom_telea"
    if qr is None:
        method = "fallback_bottom_telea"
        if poster_type == "bottom_white_iventure":
            qr = scale_rect((845, 1190, 1038, 1385), width, height, (1080, 1440))
        else:
            qr = scale_rect((845, 1330, 1045, 1495), width, height, (1080, 1520))

    left, top, right, bottom = qr
    rects: list[tuple[str, tuple[int, int, int, int]]] = [
        ("qr", (left - 4, top - 4, right + 5, bottom + 5))
    ]
    if poster_type == "bottom_white_standard":
        rects.append(("scan-text", (left - 2, max(0, bottom - 2), right + 3, min(height, bottom + 40))))
    return poster_type, method, rects, 3, cv2.INPAINT_TELEA


def inpaint(path: Path) -> ProcessResult:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return ProcessResult(str(path), None, 0, 0, "unknown", "none", [], "failed", "cannot_read_image")
    height, width = image.shape[:2]
    poster_type, method, rects, radius, cv_method = mask_plan(path, width, height)
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
        return ProcessResult(str(path), None, width, height, poster_type, method, [], "failed", "empty_mask")

    cleaned = cv2.inpaint(image, mask, radius, cv_method)
    output = path.with_name(f"Finish{path.name}")
    if not cv2.imwrite(str(output), cleaned):
        return ProcessResult(str(path), None, width, height, poster_type, method, rect_log, "failed", "cannot_write_output")
    return ProcessResult(str(path), str(output), width, height, poster_type, method, rect_log, "ok")


def make_contact_sheet(results: list[ProcessResult], filename: str, *, seed: int, sample_size: int) -> None:
    ok_results = [r for r in results if r.status == "ok" and r.output]
    rng = random.Random(seed)
    selected = rng.sample(ok_results, min(sample_size, len(ok_results)))
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
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % cols) * 300, (i // cols) * 430))
    sheet.save(INSPECTION_DIR / filename, quality=92)


def verify_dimensions(results: list[ProcessResult]) -> dict[str, object]:
    mismatches: list[dict[str, object]] = []
    for result in results:
        if result.status != "ok" or not result.output:
            continue
        with Image.open(result.source) as source, Image.open(result.output) as output:
            if source.size != output.size:
                mismatches.append({"source": result.source, "output": result.output, "source_size": source.size, "output_size": output.size})
    return {"checked": sum(1 for r in results if r.status == "ok"), "mismatch_count": len(mismatches), "mismatches": mismatches}


def main() -> int:
    INSPECTION_DIR.mkdir(parents=True, exist_ok=True)
    posters = source_posters()
    results = [inpaint(path) for path in posters]
    counts = Counter(r.status for r in results)
    type_counts = Counter(r.poster_type for r in results)
    method_counts = Counter(r.method for r in results)
    dimension_check = verify_dimensions(results)
    report = {
        "source_count": len(posters),
        "output_count": counts["ok"],
        "failure_count": counts["failed"],
        "status_counts": dict(counts),
        "type_counts": dict(type_counts),
        "method_counts": dict(method_counts),
        "dimension_check": dimension_check,
        "failures": [asdict(r) for r in results if r.status != "ok"],
        "fallbacks": [asdict(r) for r in results if r.method.startswith("fallback")],
    }
    (INSPECTION_DIR / "processing_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (INSPECTION_DIR / "processing_results.jsonl").write_text(
        "\n".join(json.dumps(asdict(r), ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )
    make_contact_sheet(results, "random_sample_40_finish.jpg", seed=20260707, sample_size=40)
    print(f"source_count={len(posters)} output_count={counts['ok']} failures={counts['failed']}")
    print(f"type_counts={dict(type_counts)}")
    print(f"method_counts={dict(method_counts)}")
    print(f"dimension_mismatches={dimension_check['mismatch_count']}")
    return 0 if counts["failed"] == 0 and dimension_check["mismatch_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
