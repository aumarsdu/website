#!/usr/bin/env python3
"""Classify and redact crawled summary posters.

This local tool uses ImageMagick only. It does not modify source posters; all
processed files are written under the output root with a ``Finish`` prefix.
"""

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    def draw_arg(self) -> str:
        return f"rectangle {self.left},{self.top} {self.right},{self.bottom}"


@dataclass(frozen=True)
class PosterRule:
    kind: str
    qr_rect: Rect
    qr_fill_sample: tuple[int, int]
    text_rects: tuple[Rect, ...] = ()
    notes: str = ""


DEFAULT_NORMAL_RULE = PosterRule(
    kind="normal_orange_cycle_text",
    qr_rect=Rect(1145, 1115, 1382, 1352),
    qr_fill_sample=(1140, 1233),
    text_rects=(
        Rect(565, 2170, 965, 2240),
        Rect(565, 2248, 965, 2316),
    ),
    notes="Orange summary poster; remove QR and target cycle text rows.",
)

RULES_BY_NAME = {
    "2026暑期线下营地项目_汇总海报_1.png": PosterRule(
        kind="onsite_orange_qr_only",
        qr_rect=Rect(1095, 1043, 1385, 1332),
        qr_fill_sample=(1090, 1187),
        notes="Orange onsite poster; target cycle text not present in visible info row.",
    ),
    "专业选修课程_汇总海报_1.png": PosterRule(
        kind="blue_course_qr_only",
        qr_rect=Rect(2356, 2295, 2809, 2747),
        qr_fill_sample=(2351, 2521),
        notes="Blue course poster; no listed target cycle text.",
    ),
    "职业通途计划_汇总海报_1.png": PosterRule(
        kind="career_orange_qr_only",
        qr_rect=Rect(1145, 1023, 1382, 1260),
        qr_fill_sample=(1140, 1141),
        notes="Career poster; no listed target cycle text.",
    ),
}


RESEARCH_QR_RULE = PosterRule(
    kind="research_assistant_qr_only",
    qr_rect=Rect(1117, 1123, 1354, 1360),
    qr_fill_sample=(1112, 1241),
    notes="Research assistant series; cycle rows contain non-target RA wording.",
)


NORMAL_CYCLE_TEXT_POSTERS = {
    "人文社科_汇总海报_1.png",
    "全球华人导师-香港_汇总海报_1.png",
    "全球华人导师-香港_汇总海报_2.png",
    "理工科_汇总海报_1.png",
    "计算机与人工智能_汇总海报_1.png",
    "金融商科_汇总海报_1.png",
}


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def magick_pixel(path: Path, x: int, y: int) -> str:
    return run(["magick", str(path), "-format", f"%[pixel:p{{{x},{y}}}]", "info:"]).stdout


def identify_size(path: Path) -> tuple[int, int]:
    out = run(["magick", "identify", "-format", "%w %h", str(path)]).stdout
    width, height = out.split()
    return int(width), int(height)


def discover_posters(input_root: Path) -> list[Path]:
    posters = [
        path
        for path in input_root.glob("*/_汇总海报/*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    return sorted(posters)


def classify(path: Path) -> PosterRule:
    if path.name in RULES_BY_NAME:
        return RULES_BY_NAME[path.name]
    if "研助起航系列" in path.parts:
        return RESEARCH_QR_RULE
    if path.name in NORMAL_CYCLE_TEXT_POSTERS:
        return DEFAULT_NORMAL_RULE
    return PosterRule(
        kind="normal_orange_qr_only",
        qr_rect=DEFAULT_NORMAL_RULE.qr_rect,
        qr_fill_sample=DEFAULT_NORMAL_RULE.qr_fill_sample,
        notes="Fallback orange summary poster; QR only.",
    )


def output_path(src: Path, input_root: Path, output_root: Path) -> Path:
    rel = src.relative_to(input_root)
    return output_root / rel.parent / f"Finish{src.name}"


def process_one(src: Path, dest: Path, rule: PosterRule) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fill = magick_pixel(src, *rule.qr_fill_sample)
    args = ["magick", str(src), "-fill", fill, "-draw", rule.qr_rect.draw_arg()]
    for rect in rule.text_rects:
        args.extend(["-fill", "white", "-draw", rect.draw_arg()])
    args.append(str(dest))
    run(args)


def write_classification_report(
    posters: list[Path],
    input_root: Path,
    output_root: Path,
    report_path: Path,
) -> None:
    counts: dict[str, int] = {}
    lines = [
        "# Poster Processing Classification",
        "",
        f"- source_root: `{input_root}`",
        f"- output_root: `{output_root}`",
        f"- poster_count: `{len(posters)}`",
        "",
        "## Types",
        "",
    ]
    for src in posters:
        rule = classify(src)
        counts[rule.kind] = counts.get(rule.kind, 0) + 1
    for kind, count in sorted(counts.items()):
        lines.append(f"- `{kind}`: {count}")
    lines.extend(["", "## Files", ""])
    for src in posters:
        rule = classify(src)
        dest = output_path(src, input_root, output_root)
        text_action = "remove target cycle text" if rule.text_rects else "no target cycle text"
        lines.extend(
            [
                f"### {src.relative_to(input_root)}",
                f"- type: `{rule.kind}`",
                f"- output: `{dest}`",
                f"- qr_rect: `{rule.qr_rect}`",
                f"- text_action: {text_action}",
                f"- notes: {rule.notes}",
                "",
            ]
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def crop_for_qr(path: Path, rule: PosterRule) -> str:
    rect = rule.qr_rect
    margin = 80
    left = max(0, rect.left - margin)
    top = max(0, rect.top - margin)
    width = (rect.right - rect.left) + margin * 2
    height = (rect.bottom - rect.top) + margin * 2
    return f"{width}x{height}+{left}+{top}"


def crop_for_cycle(path: Path) -> str:
    name = path.name.removeprefix("Finish")
    if name == "专业选修课程_汇总海报_1.png":
        return "3125x900+0+4300"
    if name == "职业通途计划_汇总海报_1.png":
        return "1500x300+0+1880"
    return "1502x360+0+2100"


def make_contact_sheet(images: list[Path], dest: Path, columns: int = 4) -> None:
    rows: list[Path] = []
    for index in range(0, len(images), columns):
        row = dest.parent / f"{dest.stem}_row_{index // columns:02d}.jpg"
        run(["magick", *map(str, images[index : index + columns]), "+append", str(row)])
        rows.append(row)
    if rows:
        run(["magick", *map(str, rows), "-append", str(dest)])


def build_random_inspection(
    posters: list[Path],
    input_root: Path,
    output_root: Path,
    inspection_dir: Path,
    sample_size: int,
    seed: int,
) -> list[Path]:
    rng = random.Random(seed)
    sample = rng.sample(posters, k=min(sample_size, len(posters)))
    inspection_dir.mkdir(parents=True, exist_ok=True)

    qr_crops: list[Path] = []
    cycle_crops: list[Path] = []
    manifest_lines = [
        "# Random Poster Inspection",
        "",
        f"- seed: `{seed}`",
        f"- sample_size: `{len(sample)}`",
        "",
        "## Samples",
        "",
    ]
    for index, src in enumerate(sample, start=1):
        rule = classify(src)
        dest = output_path(src, input_root, output_root)
        manifest_lines.extend(
            [
                f"{index}. `{src.relative_to(input_root)}`",
                f"   - type: `{rule.kind}`",
                f"   - output: `{dest}`",
            ]
        )
        qr_crop = inspection_dir / f"sample_{index:02d}_qr.jpg"
        cycle_crop = inspection_dir / f"sample_{index:02d}_cycle.jpg"
        run(
            [
                "magick",
                str(dest),
                "-crop",
                crop_for_qr(dest, rule),
                "+repage",
                "-resize",
                "320x320",
                str(qr_crop),
            ]
        )
        run(
            [
                "magick",
                str(dest),
                "-crop",
                crop_for_cycle(dest),
                "+repage",
                "-resize",
                "1000x",
                "-gravity",
                "north",
                "-extent",
                "1000x220",
                str(cycle_crop),
            ]
        )
        qr_crops.append(qr_crop)
        cycle_crops.append(cycle_crop)

    make_contact_sheet(qr_crops, inspection_dir / f"random_qr_seed_{seed}.jpg")
    make_contact_sheet(cycle_crops, inspection_dir / f"random_cycle_seed_{seed}.jpg", columns=1)
    (inspection_dir / f"random_manifest_seed_{seed}.md").write_text(
        "\n".join(manifest_lines),
        encoding="utf-8",
    )
    return sample


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("output_domestic/organized_by_site"),
        help="Root containing category/_汇总海报 source posters.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("poster"),
        help="Output root for Finish-prefixed posters.",
    )
    parser.add_argument(
        "--inspection-dir",
        type=Path,
        default=Path("poster/_inspection"),
        help="Directory for classification report and random inspection sheets.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only classify and write report.")
    parser.add_argument("--sample-size", type=int, default=5, help="Random inspection sample size.")
    parser.add_argument("--seed", type=int, default=20260704, help="Random inspection seed.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if shutil.which("magick") is None:
        raise SystemExit("ImageMagick `magick` is required.")

    input_root = args.input_root
    output_root = args.output_root
    inspection_dir = args.inspection_dir
    posters = discover_posters(input_root)
    if not posters:
        raise SystemExit(f"No posters found under {input_root}")

    report_path = inspection_dir / "classification_report.md"
    write_classification_report(posters, input_root, output_root, report_path)
    print(f"classified={len(posters)} report={report_path}")

    if args.dry_run:
        return 0

    for src in posters:
        process_one(src, output_path(src, input_root, output_root), classify(src))

    sample = build_random_inspection(
        posters=posters,
        input_root=input_root,
        output_root=output_root,
        inspection_dir=inspection_dir,
        sample_size=args.sample_size,
        seed=args.seed,
    )
    print(f"processed={len(posters)} output_root={output_root}")
    print(f"random_sample={len(sample)} seed={args.seed} inspection_dir={inspection_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
