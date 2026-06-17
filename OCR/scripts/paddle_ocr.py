#!/usr/bin/env python3
"""Optional local PaddleOCR runner for difficult posters."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".heic", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地 PaddleOCR 批量识别")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="data/output/paddleocr")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--plain-text-dir", default="data/output/plain_text")
    parser.add_argument("--_api-image", help=argparse.SUPPRESS)
    return parser.parse_args()


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def collect_images(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        return [input_path] if is_image(input_path) else []
    if not input_path.exists():
        raise SystemExit(f"输入路径不存在：{input_path}")
    iterator = input_path.rglob("*") if recursive else input_path.glob("*")
    return sorted([path for path in iterator if path.is_file() and is_image(path)], key=lambda p: str(p))


def safe_stem(path: Path) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", " ", "."} else "_" for ch in path.stem).strip()
    return safe or "image"


def confidence_avg(blocks: list[dict[str, Any]]) -> float:
    if not blocks:
        return 0.0
    return sum(float(block.get("confidence", 0.0)) for block in blocks) / len(blocks)


def normalize_record(image_path: Path, lang: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    avg = confidence_avg(blocks)
    return {
        "file": str(image_path),
        "engine": "paddleocr",
        "lang": lang,
        "plain_text": "\n".join(block["text"] for block in blocks if block.get("text")),
        "blocks": blocks,
        "confidence_avg": avg,
        "needs_review": avg < 0.70 or len(blocks) == 0,
    }


def parse_old_api_result(result: Any) -> list[dict[str, Any]]:
    lines: list[Any] = []
    if isinstance(result, list):
        if result and isinstance(result[0], list) and result[0] and isinstance(result[0][0], list):
            lines = result[0] if result and result[0] and len(result[0][0]) == 2 else result
        else:
            lines = result

    blocks: list[dict[str, Any]] = []
    for item in lines:
        try:
            box = item[0]
            text = item[1][0]
            confidence = float(item[1][1])
        except Exception:
            continue
        blocks.append(
            {
                "text": str(text),
                "confidence": confidence,
                "bounding_box": box,
                "candidates": [{"text": str(text), "confidence": confidence}],
            }
        )
    return blocks


def parse_predict_result(result: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    items = result if isinstance(result, list) else [result]
    for item in items:
        data: Any = None
        if hasattr(item, "json"):
            data = item.json
        elif hasattr(item, "to_json"):
            data = item.to_json()
        elif isinstance(item, dict):
            data = item

        if callable(data):
            data = data()
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = None
        if not isinstance(data, dict):
            continue

        payload = data.get("res", data)
        texts = payload.get("rec_texts") or payload.get("texts") or []
        scores = payload.get("rec_scores") or payload.get("scores") or []
        boxes = payload.get("rec_boxes") or payload.get("dt_polys") or payload.get("boxes") or []
        for index, text in enumerate(texts):
            confidence = float(scores[index]) if index < len(scores) else 0.0
            box = boxes[index] if index < len(boxes) else None
            blocks.append(
                {
                    "text": str(text),
                    "confidence": confidence,
                    "bounding_box": box,
                    "candidates": [{"text": str(text), "confidence": confidence}],
                }
            )
    return blocks


def api_worker(image_path: Path, lang: str) -> int:
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception as exc:
        print(json.dumps({"error": f"paddleocr import failed: {exc}"}, ensure_ascii=False))
        return 2

    try:
        try:
            ocr = PaddleOCR(lang=lang, use_angle_cls=True)
        except TypeError:
            ocr = PaddleOCR(lang=lang)

        blocks: list[dict[str, Any]] = []
        if hasattr(ocr, "ocr"):
            try:
                blocks = parse_old_api_result(ocr.ocr(str(image_path), cls=True))
            except TypeError:
                blocks = parse_old_api_result(ocr.ocr(str(image_path)))
        if not blocks and hasattr(ocr, "predict"):
            blocks = parse_predict_result(ocr.predict(str(image_path)))

        print(json.dumps({"blocks": blocks}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"PaddleOCR Python API failed: {exc}"}, ensure_ascii=False))
        return 3


def run_api_subprocess(image_path: Path, lang: str, timeout: int) -> tuple[bool, list[dict[str, Any]], str]:
    cmd = [sys.executable, __file__, "--input", str(image_path), "--_api-image", str(image_path), "--lang", lang]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return False, [], f"timeout after {timeout}s"

    output = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "{}"
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return False, [], f"API returned non-JSON output: {result.stderr.strip() or output}"

    if result.returncode == 0 and "blocks" in payload:
        return True, payload["blocks"], ""
    return False, [], payload.get("error") or result.stderr.strip() or "PaddleOCR API failed"


def parse_cli_output(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or "OCR" in stripped:
            continue
        if "\t" in stripped:
            parts = stripped.split("\t")
            candidate = parts[-1].strip()
        else:
            candidate = stripped
        if candidate:
            blocks.append(
                {
                    "text": candidate,
                    "confidence": 0.0,
                    "bounding_box": None,
                    "candidates": [{"text": candidate, "confidence": 0.0}],
                }
            )
    return blocks


def run_cli_fallback(image_path: Path, lang: str, timeout: int) -> tuple[bool, list[dict[str, Any]], str]:
    paddleocr = shutil.which("paddleocr")
    if not paddleocr:
        return False, [], "paddleocr CLI not found"

    commands = [
        [paddleocr, "--image_dir", str(image_path), "--lang", lang, "--use_angle_cls", "true"],
        [paddleocr, "ocr", "-i", str(image_path), "--lang", lang],
    ]
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return False, [], f"timeout after {timeout}s"
        if result.returncode == 0:
            blocks = parse_cli_output(result.stdout)
            return True, blocks, ""
    return False, [], "paddleocr CLI fallback failed"


def write_plain_text(record: dict[str, Any], image_path: Path, plain_text_dir: Path) -> None:
    plain_text_dir.mkdir(parents=True, exist_ok=True)
    target = plain_text_dir / f"{safe_stem(image_path)}.paddle.md"
    block_lines = "\n".join(
        f"- [{float(block.get('confidence', 0.0)):.2f}] {block.get('text', '')}" for block in record["blocks"]
    )
    content = (
        f"# {image_path.name}\n\n"
        "engine: paddleocr\n"
        f"confidence_avg: {float(record['confidence_avg']):.3f}\n"
        f"needs_review: {'true' if record['needs_review'] else 'false'}\n\n"
        "## OCR Text\n\n"
        f"{record['plain_text']}\n\n"
        "## Blocks\n\n"
        f"{block_lines}\n"
    )
    target.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args._api_image:
        return api_worker(Path(args._api_image), args.lang)

    has_api = importlib.util.find_spec("paddleocr") is not None
    has_cli = shutil.which("paddleocr") is not None
    if not has_api and not has_cli:
        print(
            "未检测到 PaddleOCR。请先运行：make paddle-install\n"
            "说明：PaddleOCR 是可选增强引擎，默认 Apple Vision OCR 不需要安装它。",
            file=sys.stderr,
        )
        return 2

    images = collect_images(Path(args.input), args.recursive)
    if not images:
        print(f"[WARN] 没有找到支持的图片：{args.input}", file=sys.stderr)
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    plain_text_dir = Path(args.plain_text_dir)
    jsonl_path = out_dir / "results.jsonl"
    csv_path = out_dir / "results.csv"

    with jsonl_path.open("w", encoding="utf-8") as jsonl, csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["file", "engine", "lang", "plain_text", "confidence_avg", "needs_review", "block_count"],
        )
        writer.writeheader()

        for index, image_path in enumerate(images, start=1):
            print(f"[{index}/{len(images)}] Processing {image_path.name}")
            ok, blocks, error = run_api_subprocess(image_path, args.lang, args.timeout) if has_api else (False, [], "API unavailable")
            if not ok:
                print(f"[WARN] {image_path.name} API fallback: {error}", file=sys.stderr)
                ok, blocks, error = run_cli_fallback(image_path, args.lang, args.timeout)
            if not ok:
                print(f"[ERROR] {image_path.name} {error}", file=sys.stderr)
                continue

            record = normalize_record(image_path, args.lang, blocks)
            jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
            writer.writerow(
                {
                    "file": record["file"],
                    "engine": record["engine"],
                    "lang": record["lang"],
                    "plain_text": record["plain_text"],
                    "confidence_avg": f"{float(record['confidence_avg']):.4f}",
                    "needs_review": str(record["needs_review"]).lower(),
                    "block_count": len(record["blocks"]),
                }
            )
            write_plain_text(record, image_path, plain_text_dir)
            if record["blocks"]:
                print(f"[OK] {image_path.name} blocks={len(record['blocks'])} confidence_avg={float(record['confidence_avg']):.2f}")
            else:
                print(f"[WARN] {image_path.name} no text found")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
