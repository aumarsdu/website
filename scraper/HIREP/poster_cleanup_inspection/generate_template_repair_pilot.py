#!/usr/bin/env python3
"""Generate a before/after pilot for the non-iVENTURE template rules."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

from poster_template_rules import clean


MANIFEST = Path("poster_cleanup_inspection/other_types_audit_20260710/sample_manifest.json")
OUTPUT_DIR = Path("poster_cleanup_inspection/non_iventure_template_pilot")


def crop_box(template: str, width: int, height: int) -> tuple[int, int, int, int]:
    if template.startswith("top_right"):
        return (760, 0, width, min(height, 330))
    return (740, max(0, height - 360), width, height)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for index, item in enumerate(json.loads(MANIFEST.read_text(encoding="utf-8")), 1):
        source = Path(item["source"])
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot read source: {source}")
        result = clean(image)
        output = OUTPUT_DIR / f"sample_{index:02d}_{source.name}"
        if not cv2.imwrite(str(output), result.image, [cv2.IMWRITE_JPEG_QUALITY, 100]):
            raise ValueError(f"Cannot write output: {output}")
        records.append(
            {
                "source": str(source),
                "output": str(output),
                "template": result.template,
                "rects": [list(rect) for rect in result.rects],
                "size": [image.shape[1], image.shape[0]],
            }
        )

    cell_width, cell_height = 620, 285
    sheet = Image.new("RGB", (cell_width * 2, cell_height * len(records)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, record in enumerate(records):
        width, height = record["size"]
        box = crop_box(str(record["template"]), width, height)
        for column, image_path in enumerate((record["source"], record["output"])):
            with Image.open(str(image_path)) as image:
                crop = image.convert("RGB").crop(box)
                crop.thumbnail((cell_width - 24, cell_height - 54))
                x = column * cell_width + (cell_width - crop.width) // 2
                y = row * cell_height + 38 + (cell_height - 54 - crop.height) // 2
                sheet.paste(crop, (x, y))
                draw.text((column * cell_width + 12, row * cell_height + 12), "Original" if column == 0 else "Pilot", fill="black")
        draw.text((12, row * cell_height + cell_height - 16), str(record["template"]), fill="black")
    sheet_path = OUTPUT_DIR / "before_after.png"
    sheet.save(sheet_path)
    (OUTPUT_DIR / "processing_report.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"processed": len(records), "sheet": str(sheet_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
