#!/usr/bin/env python3
"""Process full-refresh single-project posters.

The tool writes Finish-prefixed posters next to the source images. It uses
ImageMagick for image operations and the processed records.jsonl files for
cycle classification.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
TARGET_CYCLES = {
    "3周专业预修与在线科研+2周面授科研+5周在线论文指导",
    "7周在线小组科研+5周论文指导",
    "6周在线小组科研+5周论文指导",
    "4周在线小组科研+2周论文指导",
}


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left + 1

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1

    def draw_arg(self) -> str:
        return f"rectangle {self.left},{self.top} {self.right},{self.bottom}"

    def clamp(self, width: int, height: int) -> "Rect":
        return Rect(
            max(0, min(self.left, width - 1)),
            max(0, min(self.top, height - 1)),
            max(0, min(self.right, width - 1)),
            max(0, min(self.bottom, height - 1)),
        )

    def expand(self, pixels: int, width: int, height: int) -> "Rect":
        return Rect(
            self.left - pixels,
            self.top - pixels,
            self.right + pixels,
            self.bottom + pixels,
        ).clamp(width, height)


@dataclass(frozen=True)
class PosterItem:
    site: str
    source: Path
    record_id: str
    cycle: str
    width: int
    height: int


@dataclass(frozen=True)
class QrDetection:
    qr_rect: Rect
    text_rects: tuple[Rect, ...]
    fill: str


CC_RE = re.compile(r"\s*(\d+):\s+(\d+)x(\d+)\+(\d+)\+(\d+)\s+([\d.]+),([\d.]+)\s+(\d+)")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def identify_size(path: Path) -> tuple[int, int]:
    out = run(["magick", "identify", "-format", "%w %h", str(path)]).stdout
    width, height = out.split()
    return int(width), int(height)


def pixel(path: Path, x: int, y: int) -> str:
    return run(["magick", str(path), "-format", f"%[pixel:p{{{x},{y}}}]", "info:"]).stdout


def parse_rgb(value: str) -> tuple[int, int, int]:
    numbers = re.findall(r"\d+(?:\.\d+)?", value)
    if len(numbers) >= 3:
        return tuple(int(float(part)) for part in numbers[:3])  # type: ignore[return-value]
    return (255, 255, 255)


def choose_background_fill(path: Path, rect: Rect, width: int, height: int) -> str:
    offset = max(8, rect.width // 12)
    points = [
        (rect.left - offset, rect.top + rect.height // 2),
        (rect.right + offset, rect.top + rect.height // 2),
        (rect.left + rect.width // 2, rect.top - offset),
        (rect.left + rect.width // 2, rect.bottom + offset),
        (rect.left - offset, rect.top - offset),
        (rect.right + offset, rect.top - offset),
        (rect.left - offset, rect.bottom + offset),
        (rect.right + offset, rect.bottom + offset),
    ]
    samples: list[tuple[int, str]] = []
    for x, y in points:
        if not (0 <= x < width and 0 <= y < height):
            continue
        value = pixel(path, x, y)
        r, g, b = parse_rgb(value)
        brightness = r + g + b
        samples.append((brightness, value))
    if not samples:
        return pixel(path, max(0, rect.left - 2), min(height - 1, rect.top + rect.height // 2))
    non_white = [sample for sample in samples if sample[0] < 690]
    if non_white:
        return min(non_white, key=lambda sample: sample[0])[1]
    return min(samples, key=lambda sample: sample[0])[1]


def threshold_mean(path: Path, rect: Rect) -> float:
    if rect.width <= 0 or rect.height <= 0:
        return 0.0
    out = run(
        [
            "magick",
            str(path),
            "-crop",
            f"{rect.width}x{rect.height}+{rect.left}+{rect.top}",
            "+repage",
            "-colorspace",
            "Gray",
            "-threshold",
            "82%",
            "-format",
            "%[fx:mean]",
            "info:",
        ]
    ).stdout
    return float(out)


def normalize_cycle(cycle: str) -> str:
    return cycle.replace("＋", "+").strip()


def load_cycles(site_root: Path) -> dict[str, str]:
    records_path = site_root / "processed" / "records.jsonl"
    cycles: dict[str, str] = {}
    with records_path.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            raw = item.get("raw") or {}
            record_id = item.get("id") or item.get("record_key")
            if not record_id:
                continue
            cycles[record_id] = normalize_cycle(str(raw.get("cycle") or item.get("cycle") or ""))
    return cycles


def discover(site_root: Path, site: str) -> list[PosterItem]:
    cycles = load_cycles(site_root)
    posters: list[PosterItem] = []
    for path in sorted((site_root / "posters").iterdir()):
        if path.name.startswith("Finish") or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        record_id = path.name.split("_", 1)[0]
        width, height = identify_size(path)
        posters.append(
            PosterItem(
                site=site,
                source=path,
                record_id=record_id,
                cycle=cycles.get(record_id, ""),
                width=width,
                height=height,
            )
        )
    return posters


def detect_qr_in_crop(path: Path, width: int, height: int, x0: int, y0: int, crop_w: int, crop_h: int) -> Rect | None:
    proc = run(
        [
            "magick",
            str(path),
            "-crop",
            f"{crop_w}x{crop_h}+{x0}+{y0}",
            "+repage",
            "-colorspace",
            "Gray",
            "-threshold",
            "78%",
            "-define",
            "connected-components:verbose=true",
            "-connected-components",
            "8",
            "null:",
        ]
    )
    candidates: list[tuple[float, Rect]] = []
    max_side = min(width, height) * 0.28
    min_side = max(38, min(width, height) * 0.055)
    for line in (proc.stdout + proc.stderr).splitlines():
        match = CC_RE.match(line)
        if not match:
            continue
        _, box_w, box_h, x, y, _, _, area = match.groups()
        box_w_i = int(box_w)
        box_h_i = int(box_h)
        x_i = int(x)
        y_i = int(y)
        area_i = int(area)
        ratio = box_w_i / box_h_i if box_h_i else 0
        if not (0.72 <= ratio <= 1.28):
            continue
        if not (min_side <= box_w_i <= max_side and min_side <= box_h_i <= max_side):
            continue
        if area_i < (box_w_i * box_h_i * 0.22):
            continue
        rect = Rect(x0 + x_i, y0 + y_i, x0 + x_i + box_w_i - 1, y0 + y_i + box_h_i - 1)
        # Favor large QR-like squares near the lower-right corner.
        score = area_i + rect.left * 0.25 + rect.top * 0.25
        candidates.append((score, rect))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def detect_qr(path: Path, width: int, height: int) -> QrDetection | None:
    crop_w = max(320, int(width * 0.45))
    crop_h = max(360, int(height * 0.45))
    x0 = width - crop_w
    y0 = height - crop_h
    rect = detect_qr_in_crop(path, width, height, x0, y0, crop_w, crop_h)
    if rect is None:
        crop_w = width
        crop_h = max(360, int(height * 0.32))
        x0 = 0
        y0 = height - crop_h
        rect = detect_qr_in_crop(path, width, height, x0, y0, crop_w, crop_h)
    if rect is None:
        return None
    rect = rect.expand(max(2, int(rect.width * 0.055)), width, height)

    fill = choose_background_fill(path, rect, width, height)

    side_gap = max(4, rect.width // 35)
    side_w = max(28, int(rect.width * 0.32))
    text_candidates = (
        Rect(rect.left - side_gap - side_w, rect.top, rect.left - side_gap, rect.bottom).clamp(width, height),
        Rect(rect.right + side_gap, rect.top, rect.right + side_gap + side_w, rect.bottom).clamp(width, height),
    )
    text_rects: list[Rect] = []
    for side in text_candidates:
        mean = threshold_mean(path, side)
        # Dark/colored side label with white vertical text normally has a small
        # but noticeable white-pixel ratio. Pure white QR background is skipped.
        if 0.018 <= mean <= 0.42:
            text_rects.append(side)
    return QrDetection(qr_rect=rect, text_rects=tuple(text_rects), fill=fill)


def cycle_kind(cycle: str) -> str:
    normalized = normalize_cycle(cycle)
    if "3周专业预修与在线科研+2周面授科研+5周在线论文指导" in normalized:
        return "cycle_3w_onsite"
    # Some records contain the longer learning-package wording, while the
    # poster renders the shorter user-specified cycle label.
    excluded = "研究助理" in normalized or "独立深度" in normalized
    if not excluded and "7周在线小组科研" in normalized and "论文指导" in normalized:
        return "cycle_7w"
    if not excluded and "6周在线小组科研" in normalized and "5周" in normalized and "论文指导" in normalized:
        return "cycle_6w"
    if not excluded and "4周在线小组科研" in normalized and "2周" in normalized and "论文指导" in normalized:
        return "cycle_4w"
    return "no_target_cycle"


def cycle_rects(item: PosterItem) -> tuple[Rect, ...]:
    kind = cycle_kind(item.cycle)
    if kind == "no_target_cycle":
        return ()
    width = item.width
    height = item.height
    aspect = height / width
    name = item.source.name
    if "探微计划" in name:
        if kind in {"cycle_6w", "cycle_7w"}:
            return (Rect(int(width * 0.245), int(height * 0.530), int(width * 0.750), int(height * 0.585)),)
        if kind == "cycle_4w":
            return (Rect(int(width * 0.245), int(height * 0.530), int(width * 0.800), int(height * 0.585)),)
    if "致理计划" in name and aspect <= 1.42:
        if kind in {"cycle_6w", "cycle_7w"}:
            return (Rect(int(width * 0.315), int(height * 0.405), int(width * 0.770), int(height * 0.470)),)
        if kind == "cycle_4w":
            return (Rect(int(width * 0.315), int(height * 0.405), int(width * 0.875), int(height * 0.470)),)
    if aspect > 1.42:
        if kind in {"cycle_6w", "cycle_7w"}:
            return (Rect(int(width * 0.445), int(height * 0.555), int(width * 0.915), int(height * 0.595)),)
        if kind == "cycle_4w":
            return (Rect(int(width * 0.335), int(height * 0.505), int(width * 0.925), int(height * 0.545)),)
        if kind == "cycle_3w_onsite":
            return (Rect(int(width * 0.20), int(height * 0.625), int(width * 0.92), int(height * 0.675)),)
    if kind in {"cycle_6w", "cycle_7w"}:
        return (Rect(int(width * 0.385), int(height * 0.505), int(width * 0.925), int(height * 0.595)),)
    if kind == "cycle_4w":
        return (Rect(int(width * 0.335), int(height * 0.505), int(width * 0.925), int(height * 0.595)),)
    if kind == "cycle_3w_onsite":
        return (Rect(int(width * 0.18), int(height * 0.455), int(width * 0.92), int(height * 0.505)),)
    return ()


def output_path(source: Path) -> Path:
    return source.with_name(f"Finish{source.name}")


def process_item(item: PosterItem) -> tuple[bool, str]:
    detection = detect_qr(item.source, item.width, item.height)
    if detection is None:
        return False, "qr_not_detected"
    args = ["magick", str(item.source)]
    for rect in (detection.qr_rect, *detection.text_rects):
        args.extend(["-fill", detection.fill, "-draw", rect.draw_arg()])
    for rect in cycle_rects(item):
        args.extend(["-fill", "white", "-draw", rect.clamp(item.width, item.height).draw_arg()])
    args.append(str(output_path(item.source)))
    run(args)
    return True, "processed"


def write_report(items: list[PosterItem], report_path: Path, failures: dict[str, str]) -> None:
    counts: dict[str, int] = {}
    for item in items:
        key = cycle_kind(item.cycle)
        counts[key] = counts.get(key, 0) + 1
    lines = [
        "# Full Refresh Poster Processing Report",
        "",
        f"- poster_count: `{len(items)}`",
        f"- failures: `{len(failures)}`",
        "",
        "## Cycle Types",
        "",
    ]
    for key, count in sorted(counts.items()):
        lines.append(f"- `{key}`: {count}")
    lines.extend(["", "## Failures", ""])
    if failures:
        for path, reason in sorted(failures.items()):
            lines.append(f"- `{path}`: {reason}")
    else:
        lines.append("- none")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def make_inspection(items: list[PosterItem], inspection_dir: Path, seed: int, sample_size: int) -> None:
    rng = random.Random(seed)
    sample = rng.sample(items, min(sample_size, len(items)))
    inspection_dir.mkdir(parents=True, exist_ok=True)
    qr_images: list[Path] = []
    cycle_images: list[Path] = []
    manifest = ["# Random Inspection", "", f"- seed: `{seed}`", f"- sample_size: `{len(sample)}`", ""]
    for index, item in enumerate(sample, 1):
        dest = output_path(item.source)
        detection = detect_qr(item.source, item.width, item.height)
        if detection:
            rect = detection.qr_rect
            margin = max(40, int(rect.width * 0.45))
            crop = Rect(rect.left - margin, rect.top - margin, rect.right + margin, rect.bottom + margin).clamp(
                item.width, item.height
            )
            qr_out = inspection_dir / f"sample_{index:02d}_qr.jpg"
            run(
                [
                    "magick",
                    str(dest),
                    "-crop",
                    f"{crop.width}x{crop.height}+{crop.left}+{crop.top}",
                    "+repage",
                    "-resize",
                    "360x360",
                    str(qr_out),
                ]
            )
            qr_images.append(qr_out)
        cycle_out = inspection_dir / f"sample_{index:02d}_cycle.jpg"
        y = int(item.height * 0.48)
        h = int(item.height * 0.24)
        run(
            [
                "magick",
                str(dest),
                "-crop",
                f"{item.width}x{h}+0+{y}",
                "+repage",
                "-resize",
                "900x",
                str(cycle_out),
            ]
        )
        cycle_images.append(cycle_out)
        manifest.extend(
            [
                f"{index}. `{item.site}/{item.source.name}`",
                f"   - cycle_kind: `{cycle_kind(item.cycle)}`",
                f"   - output: `{dest}`",
            ]
        )
    if qr_images:
        run(["magick", *map(str, qr_images), "+append", str(inspection_dir / f"random_qr_seed_{seed}.jpg")])
    if cycle_images:
        run(["magick", *map(str, cycle_images), "-append", str(inspection_dir / f"random_cycle_seed_{seed}.jpg")])
    (inspection_dir / f"random_manifest_seed_{seed}.md").write_text("\n".join(manifest), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("output/full_refresh/20260703-new-check"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sample-size", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260704)
    parser.add_argument("--limit", type=int, default=0, help="Optional processing limit for debugging.")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers for poster processing.")
    parser.add_argument("--skip-existing", action="store_true", help="Only process sources without a Finish output.")
    parser.add_argument("--only-target-cycle", action="store_true", help="Only process posters with target cycle text.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if shutil.which("magick") is None:
        raise SystemExit("ImageMagick `magick` is required.")
    sites = [("sou_tools", args.base / "sou_tools"), ("domestic", args.base / "domestic")]
    items: list[PosterItem] = []
    for site, root in sites:
        items.extend(discover(root, site))
    if args.limit:
        items = items[: args.limit]
    inspection_dir = args.base / "_poster_processing_inspection"
    failures: dict[str, str] = {}
    if not args.dry_run:
        workers = max(1, int(args.workers))
        process_items = [item for item in items if not (args.skip_existing and output_path(item.source).exists())]
        if args.only_target_cycle:
            process_items = [item for item in process_items if cycle_kind(item.cycle) != "no_target_cycle"]
        if workers == 1:
            for index, item in enumerate(process_items, 1):
                ok, reason = process_item(item)
                if not ok:
                    failures[str(item.source)] = reason
                if index % 100 == 0:
                    print(f"processed {index}/{len(process_items)}")
        else:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(process_item, item): item for item in process_items}
                for index, future in enumerate(as_completed(futures), 1):
                    item = futures[future]
                    try:
                        ok, reason = future.result()
                    except Exception as exc:  # noqa: BLE001 - record per-image failure and continue.
                        ok, reason = False, f"exception:{exc}"
                    if not ok:
                        failures[str(item.source)] = reason
                    if index % 100 == 0:
                        print(f"processed {index}/{len(process_items)}")
    write_report(items, inspection_dir / "processing_report.md", failures)
    if not args.dry_run:
        processed_items = [item for item in items if str(item.source) not in failures]
        make_inspection(processed_items, inspection_dir, args.seed, args.sample_size)
    print(f"classified={len(items)} failures={len(failures)} report={inspection_dir / 'processing_report.md'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
