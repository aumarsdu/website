#!/usr/bin/env python3
"""Bridge real poster OCR output into the poster_ocr.jsonl contract.

This tool is **not part of the research_facts package** and is never imported by
it. The package stays dependency-free on purpose; OCR engines are heavy and
version-fragile, so they live outside. This script is the documented seam.

Why a separate tool instead of an adapter
-----------------------------------------
PaddleOCR returns polygons, and its output shape changes between major
versions. A bridge script can absorb that churn in one place, while the
extraction rules stay testable without a multi-gigabyte model.

Usage
-----
    # one interpreter that has paddleocr installed
    python posters_to_ocr_jsonl.py \
        --input ../../盐趣/Poster \
        --out   data/real/poster_ocr.jsonl \
        --provider yanxu \
        --limit 8

Then feed the result to the package:

    python -m research_facts ingest \
        --input data/real/poster_ocr.jsonl:poster_ocr
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_MODEL_ROOT = Path.home() / ".paddlex" / "official_models"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="海报根目录")
    parser.add_argument("--out", type=Path, required=True, help="输出 poster_ocr.jsonl")
    parser.add_argument("--provider", required=True, help="供应商标识，进入 record_key 与归组")
    parser.add_argument("--limit", type=int, help="只处理这么多张")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 张（配合 --limit 做分片）")
    parser.add_argument(
        "--external-id-from",
        choices=("filename", "none"),
        default="filename",
        help="external_id 取文件名（默认）还是留空。真实海报通常无编号，"
        "留空则身份退回标题依据并标 review_required。",
    )
    parser.add_argument("--det-model", default="PP-OCRv6_medium_det")
    parser.add_argument("--rec-model", default="PP-OCRv6_medium_rec")
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--source-authority", default="supplier_marketing")
    parser.add_argument("--min-conf", type=float, default=0.0, help="丢弃低于此置信度的块")
    return parser.parse_args(argv)


def collect_images(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda path: str(path),
    )


def _payload(result: Any) -> dict[str, Any]:
    data = getattr(result, "json", result)
    if callable(data):
        data = data()
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise TypeError(f"unexpected OCR result type: {type(data).__name__}")
    payload = data.get("res", data)
    if not isinstance(payload, dict):
        raise TypeError("OCR result has no result payload")
    return payload


def polygon_to_bbox(polygon: Any) -> list[int] | None:
    """Convert an OCR polygon to the ``[x, y, w, h]`` the contract uses."""
    try:
        points = [(float(point[0]), float(point[1])) for point in polygon]
    except (TypeError, ValueError, IndexError):
        return None
    if len(points) < 2:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))]


def ocr_blocks(ocr: Any, image: Path, min_conf: float) -> list[dict[str, Any]]:
    """One OCR page -> the contract's block list. Every detected block is kept.

    Nothing is filtered by position or language here. A background photo of a
    spreadsheet produces text blocks, and those belong in the evidence: the
    package must be able to *see* the noise so a human can judge it, rather
    than have a script quietly drop it.
    """
    results = list(ocr.predict(str(image)))
    if not results:
        raise RuntimeError("OCR returned no page result")
    payload = _payload(results[0])
    texts = payload.get("rec_texts") or []
    scores = payload.get("rec_scores") or []
    polygons = payload.get("rec_polys") or payload.get("dt_polys") or []

    blocks: list[dict[str, Any]] = []
    for index, text in enumerate(texts):
        if index < len(scores) and float(scores[index]) < min_conf:
            continue
        bbox = polygon_to_bbox(polygons[index]) if index < len(polygons) else None
        if bbox is None:
            continue
        blocks.append(
            {
                "text": str(text),
                "bbox": bbox,
                "conf": round(float(scores[index]), 4) if index < len(scores) else None,
            }
        )
    return blocks


def build_engine(det_model: str, rec_model: str, model_root: Path) -> Any:
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "paddleocr 未安装。OCR 依赖不装进 research_facts；\n"
            "请用一个已装 paddleocr 的解释器运行本脚本（Python 3.12 + paddleocr 3.7）。\n"
            f"原始错误：{exc}"
        ) from exc
    return PaddleOCR(
        det_model_dir=str(model_root / det_model),
        rec_model_dir=str(model_root / rec_model),
    )


def external_id_for(path: Path, root: Path, mode: str) -> str | None:
    if mode == "none":
        return None
    # Posters are usually named after the topic, so the filename is a stable
    # local handle -- not a supplier id. It is recorded as the id so records
    # from the same poster batch group together, and the identity basis stays
    # visible in the output.
    return path.relative_to(root).as_posix().rsplit(".", 1)[0][:120]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    images = collect_images(args.input)
    window = images[args.offset : (args.offset + args.limit) if args.limit else None]
    if not window:
        print("没有找到海报图片", file=sys.stderr)
        return 2

    engine = build_engine(args.det_model, args.rec_model, args.model_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    failed = 0
    with args.out.open("w", encoding="utf-8") as handle:
        for image in window:
            document_id = f"poster-{image.stem[:60]}"
            try:
                blocks = ocr_blocks(engine, image, args.min_conf)
            except Exception as exc:  # noqa: BLE001 - one bad poster must not stop the batch
                failed += 1
                print(f"  ! {image.name}: {exc}", file=sys.stderr)
                continue
            record = {
                "document_id": document_id,
                "provider": args.provider,
                "external_id": external_id_for(image, args.input, args.external_id_from),
                "title_hint": None,  # the package picks a headline from the blocks
                "source_authority": args.source_authority,
                "image": image.relative_to(args.input).as_posix(),
                "meta": {
                    "ocr_engine": "PaddleOCR",
                    "det_model": args.det_model,
                    "rec_model": args.rec_model,
                    "block_count": len(blocks),
                },
                "blocks": blocks,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            print(f"  ✓ {document_id}: {len(blocks)} 块", file=sys.stderr)

    print(f"输出 {args.out}：{written} 条，失败 {failed}", file=sys.stderr)
    return 1 if failed and not written else 0


if __name__ == "__main__":
    raise SystemExit(main())
