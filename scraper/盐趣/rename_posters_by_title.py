#!/usr/bin/env python3
"""Plan and apply title-based renames for the local Poster image set."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
CJK_RE = re.compile(r"[\u3400-\u9fff]")
TOPIC_MARKERS = ("专题", "课题")
GENERIC_TITLES = {"经济商科课题", "理工科课题", "人文社科课题", "计算机课题"}
INVALID_FILENAME_CHARS = re.compile(r"[\x00-\x1f/\\:*?\"<>|]")
SUBJECT_TAG_TERMS = {
    "金融学",
    "金融工程",
    "量化金融",
    "财务分析",
    "公司金融",
    "投资学",
    "会计与金融",
    "市场营销",
    "品牌管理",
    "管理学",
    "计量经济学",
    "统计学",
    "量化投资",
    "商业分析",
    "数据分析",
    "电子信息",
    "微电子学",
    "集成电路设计",
    "低功耗计算",
    "半导体",
    "材料化学",
    "纳米复合材料",
    "生物材料",
    "聚合物",
    "车辆工程",
    "智慧交通",
    "能源与动力工程",
    "新能源电池",
    "机械工程",
    "计算机科学",
    "深度学习",
    "机器学习",
    "人工智能",
    "计算机视觉",
    "生物学",
    "生物信息学",
    "基因组学",
    "DNA测序",
    "基因编辑",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rename Poster images from their OCR title.")
    parser.add_argument("--poster-dir", type=Path, default=Path("Poster"))
    parser.add_argument(
        "--ocr-csv",
        type=Path,
        default=Path("盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv"),
    )
    parser.add_argument("--mapping-csv", type=Path, default=Path("Poster/海报改名映射_PP-OCRv6.csv"))
    parser.add_argument("--apply", action="store_true", help="Actually rename files; default is preview only")
    return parser.parse_args()


def polygon_y(block: dict[str, Any]) -> float:
    polygon = block.get("polygon") or []
    ys = [float(point[1]) for point in polygon if isinstance(point, list) and len(point) > 1]
    return min(ys) if ys else 10**9


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text))


def looks_like_subject_tags(text: str) -> bool:
    compact = re.sub(r"[\s|、，,·]+", "", text)
    if len(compact) < 4:
        return False
    remainder = compact
    for term in sorted(SUBJECT_TAG_TERMS, key=len, reverse=True):
        remainder = remainder.replace(term, "")
    return not remainder


def first_cjk_index(blocks: list[dict[str, Any]]) -> int:
    for index, block in enumerate(blocks):
        if polygon_y(block) >= 240 and has_cjk(str(block.get("text", ""))):
            return index
    return 0


def title_from_record(record: dict[str, Any]) -> str:
    blocks = [block for block in json.loads(record["text_blocks_json"]) if block.get("text")]
    topic_indices = [
        index
        for index, block in enumerate(blocks)
        if polygon_y(block) >= 240 and any(marker in str(block["text"]) for marker in TOPIC_MARKERS)
    ]
    header_index = topic_indices[0] if topic_indices else first_cjk_index(blocks)
    header = str(blocks[header_index]["text"]).strip()
    if header in GENERIC_TITLES:
        return header

    header_y = polygon_y(blocks[header_index])
    parts = [header]
    saw_long_title_line = False
    subject_cluster_started = False
    for block in blocks[header_index + 1 :]:
        text = str(block["text"]).strip()
        block_y = polygon_y(block)
        if subject_cluster_started or block_y > 1200 or block_y - header_y > 900:
            continue
        if not text or not has_cjk(text) or "更新于" in text:
            continue
        text = re.sub(r"日XLMUSDT,?3$", "", text)
        text = re.sub(r"全\d+$", "", text)
        if not text:
            continue
        if len(text) <= 2 and saw_long_title_line and block_y - header_y > 700:
            continue
        if saw_long_title_line and looks_like_subject_tags(text):
            subject_cluster_started = True
            continue

        nearby = [
            candidate
            for candidate in blocks[header_index + 1 :]
            if has_cjk(str(candidate.get("text", "")))
            and abs(polygon_y(candidate) - block_y) <= 35
        ]
        short_subject_cluster = len(nearby) >= 2 and all(
            len(str(candidate["text"])) <= 8
            and not re.match(r"^\s*[-—一]", str(candidate["text"]))
            for candidate in nearby
        )
        if short_subject_cluster and saw_long_title_line:
            subject_cluster_started = True
            continue

        parts.append(text)
        saw_long_title_line = saw_long_title_line or len(text) >= 10

    title = "".join(parts[1:])
    if title:
        separator = "" if header.endswith(("：", ":")) else "："
        title = f"{header}{separator}{title}"
    else:
        title = header
    title = title.replace("：：", "：").replace("一一", "一—")
    title = re.sub(r"(^|：)Al\+", r"\1AI+", title)
    return title


def load_ocr_records(path: Path) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    by_file = {record["poster_file"]: record for record in records}
    by_header: dict[str, dict[str, Any]] = {}
    for record in records:
        blocks = [block for block in json.loads(record["text_blocks_json"]) if block.get("text")]
        for block in blocks[:3]:
            text = str(block["text"]).strip()
            if has_cjk(text) and text not in by_header:
                by_header[text] = record
    return {"by_file": by_file, "by_header": by_header}


def record_for_file(path: Path, indexes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    base_name = path.name[6:] if path.name.startswith("Finish") else path.name
    record = indexes["by_file"].get(base_name)
    if record is not None:
        return record
    stem = path.stem
    record = indexes["by_header"].get(stem)
    if record is not None:
        return record
    raise KeyError(f"No OCR record for {path.name}")


def safe_title(title: str) -> str:
    title = unicodedata.normalize("NFC", title).replace("\n", "").replace("\r", "").strip()
    title = INVALID_FILENAME_CHARS.sub(" ", title)
    title = re.sub(r"\s+", " ", title).strip(" .")
    if not title:
        raise ValueError("OCR title is empty after filename normalization")
    # Keep a margin below macOS' 255-byte filename limit.
    encoded = title.encode("utf-8")
    if len(encoded) > 220:
        title = encoded[:217].decode("utf-8", errors="ignore").rstrip() + "…"
    return title


def build_plan(poster_dir: Path, indexes: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    images = sorted(
        path for path in poster_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise RuntimeError(f"No poster images found in {poster_dir}")

    rows: list[dict[str, str]] = []
    for image in images:
        record = record_for_file(image, indexes)
        rows.append(
            {
                "old_path": str(image),
                "old_name": image.name,
                "base_name": image.name[6:] if image.name.startswith("Finish") else image.name,
                "record_key": record["poster_file"],
                "title": safe_title(title_from_record(record)),
                "is_finish": "true" if image.name.startswith("Finish") else "false",
            }
        )

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["title"]].append(row)
    for title, group in groups.items():
        poster_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in group:
            poster_groups[row["record_key"]].append(row)
        ordered_groups = sorted(poster_groups.values(), key=lambda items: min(item["old_name"] for item in items))
        for group_index, poster_group in enumerate(ordered_groups, start=1):
            group_title = title if group_index == 1 else f"{title}（{group_index}）"
            for row in poster_group:
                finish_suffix = "（Finish）" if row["is_finish"] == "true" and len(poster_group) > 1 else ""
                row["new_name"] = f"{group_title}{finish_suffix}{Path(row['old_name']).suffix}"

    new_names = [row["new_name"] for row in rows]
    if len(set(new_names)) != len(new_names):
        raise RuntimeError("Rename plan contains duplicate target names")
    return rows


def write_mapping(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["old_name", "new_name", "title", "is_finish"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def apply_plan(rows: list[dict[str, str]], poster_dir: Path) -> None:
    targets = {poster_dir / row["new_name"] for row in rows}
    sources = {Path(row["old_path"]) for row in rows}
    conflicts = [target for target in targets if target.exists() and target not in sources]
    if conflicts:
        raise RuntimeError(f"Target filename already exists outside plan: {conflicts[0].name}")

    temporary: list[tuple[Path, Path]] = []
    for index, row in enumerate(rows):
        source = Path(row["old_path"])
        temp = poster_dir / f".__ocr_rename_tmp_{index:04d}{source.suffix}"
        if temp.exists():
            raise RuntimeError(f"Temporary path already exists: {temp.name}")
        source.rename(temp)
        temporary.append((temp, poster_dir / row["new_name"]))
    for temp, target in temporary:
        temp.rename(target)


def main() -> int:
    args = parse_args()
    poster_dir = args.poster_dir.resolve()
    indexes = load_ocr_records(args.ocr_csv.resolve())
    rows = build_plan(poster_dir, indexes)
    write_mapping(args.mapping_csv.resolve(), rows)
    print(f"planned={len(rows)} unique_targets={len({row['new_name'] for row in rows})}")
    for row in rows[:12]:
        print(f"{row['old_name']} -> {row['new_name']}")
    if args.apply:
        apply_plan(rows, poster_dir)
        print(f"renamed={len(rows)}")
    else:
        print("preview_only=true; pass --apply to rename files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
