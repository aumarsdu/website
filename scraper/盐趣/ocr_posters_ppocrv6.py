#!/usr/bin/env python3
"""Use local PP-OCRv6 models to OCR every poster in a directory."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any

from PIL import Image
from paddleocr import PaddleOCR


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
MODEL_ROOT = Path.home() / ".paddlex" / "official_models"
DET_MODEL_DIR = MODEL_ROOT / "PP-OCRv6_medium_det"
REC_MODEL_DIR = MODEL_ROOT / "PP-OCRv6_medium_rec"
CSV_COLUMNS = [
    "category",
    "poster_path",
    "poster_file",
    "image_width",
    "image_height",
    "engine",
    "detection_model",
    "recognition_model",
    "status",
    "error",
    "text_block_count",
    "confidence_average",
    "confidence_minimum",
    "poster_text",
    "text_blocks_json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch OCR posters with local PP-OCRv6 models.")
    parser.add_argument("--input", type=Path, required=True, help="Poster root directory")
    parser.add_argument("--root", type=Path, help="Root used for CSV paths and categories; defaults to --input")
    parser.add_argument("--output", type=Path, required=True, help="Output CSV path")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Resumable JSONL checkpoint")
    parser.add_argument("--limit", type=int, help="Only process this many unprocessed posters")
    parser.add_argument("--retry-errors", action="store_true", help="Reprocess checkpoint error records")
    parser.add_argument("--cpu-threads", type=int, default=2, help="Paddle inference CPU threads per process")
    return parser.parse_args()


def collect_images(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda path: str(path),
    )


def load_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                records[record["poster_path"]] = record
            except (json.JSONDecodeError, KeyError) as exc:
                raise RuntimeError(f"Invalid checkpoint at line {line_number}: {exc}") from exc
    return records


def prediction_data(result: Any) -> dict[str, Any]:
    data = getattr(result, "json", result)
    if callable(data):
        data = data()
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise TypeError(f"Unexpected PaddleOCR result type: {type(data).__name__}")
    payload = data.get("res", data)
    if not isinstance(payload, dict):
        raise TypeError("PaddleOCR result has no result payload")
    return payload


def ocr_record(ocr: PaddleOCR, poster: Path, output_root: Path) -> dict[str, Any]:
    relative_path = str(poster.relative_to(output_root))
    category = poster.parent.relative_to(output_root).as_posix()
    with Image.open(poster) as image:
        width, height = image.size

    record: dict[str, Any] = {
        "category": category,
        "poster_path": relative_path,
        "poster_file": poster.name,
        "image_width": width,
        "image_height": height,
        "engine": "PaddleOCR 3.7.0 / PP-OCRv6",
        "detection_model": DET_MODEL_DIR.name,
        "recognition_model": REC_MODEL_DIR.name,
        "status": "ok",
        "error": "",
        "text_block_count": 0,
        "confidence_average": "",
        "confidence_minimum": "",
        "poster_text": "",
        "text_blocks_json": "[]",
    }

    try:
        results = list(ocr.predict(str(poster)))
        if not results:
            raise RuntimeError("PaddleOCR returned no page result")
        payload = prediction_data(results[0])
        texts = payload.get("rec_texts") or []
        scores = payload.get("rec_scores") or []
        boxes = payload.get("rec_polys") or payload.get("dt_polys") or []
        blocks = [
            {
                "text": str(text),
                "confidence": float(scores[index]) if index < len(scores) else None,
                "polygon": boxes[index] if index < len(boxes) else None,
            }
            for index, text in enumerate(texts)
        ]
        confidences = [block["confidence"] for block in blocks if block["confidence"] is not None]
        record.update(
            text_block_count=len(blocks),
            confidence_average=round(fmean(confidences), 6) if confidences else "",
            confidence_minimum=round(min(confidences), 6) if confidences else "",
            poster_text="\n".join(block["text"] for block in blocks),
            text_blocks_json=json.dumps(blocks, ensure_ascii=False, separators=(",", ":")),
        )
    except Exception as exc:
        record.update(status="error", error=f"{type(exc).__name__}: {exc}")
    return record


def append_checkpoint(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    args = parse_args()
    if not args.input.is_dir():
        raise SystemExit(f"Input directory not found: {args.input}")
    if not DET_MODEL_DIR.is_dir() or not REC_MODEL_DIR.is_dir():
        raise SystemExit("Local PP-OCRv6 model directories are missing.")

    input_root = args.input.resolve()
    output_root = (args.root or args.input).resolve()
    if input_root != output_root and output_root not in input_root.parents:
        raise SystemExit("--root must be the input directory or one of its parents.")
    posters = collect_images(input_root)
    checkpoint = load_checkpoint(args.checkpoint)
    pending = [
        poster
        for poster in posters
        if (existing := checkpoint.get(str(poster.relative_to(output_root)))) is None
        or (args.retry_errors and existing.get("status") == "error")
    ]
    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"total={len(posters)} pending={len(pending)} checkpointed={len(checkpoint)}", flush=True)
    if pending:
        ocr = PaddleOCR(
            text_detection_model_dir=str(DET_MODEL_DIR),
            text_recognition_model_dir=str(REC_MODEL_DIR),
            text_recognition_batch_size=64,
            cpu_threads=args.cpu_threads,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        for index, poster in enumerate(pending, start=1):
            record = ocr_record(ocr, poster, output_root)
            append_checkpoint(args.checkpoint, record)
            checkpoint[record["poster_path"]] = record
            print(
                f"[{index}/{len(pending)}] {record['status']} blocks={record['text_block_count']} {record['poster_path']}",
                flush=True,
            )

    ordered_records = [checkpoint[str(poster.relative_to(output_root))] for poster in posters if str(poster.relative_to(output_root)) in checkpoint]
    write_csv(args.output, ordered_records)
    errors = sum(record["status"] != "ok" for record in ordered_records)
    completed_at = datetime.now(timezone.utc).isoformat()
    print(f"written={args.output} rows={len(ordered_records)} errors={errors} completed_at={completed_at}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
