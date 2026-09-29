"""HIREP index builder (需求文档 3.1 / 二期)."""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from . import common, direction
from .common import SCRAPER_ROOT

SUPPLIER = "HIREP"
ROOT = SCRAPER_ROOT / "HIREP"
OCT_DIR = ROOT / "HIREP-海报处理-2026年10月1日以后"
PROC_POSTER_DIR = ROOT / "HIREP-海报处理-2026年10月1日以后"
SELECTION = ROOT / "HIREP-开课时间-2026年10月1日以后" / "poster_selection_manifest.json"
# 资产字段优先级：行业海报 > 主附件 > 课程横幅 > 缩略图
FIELD_PRIORITY = ["industryPoster", "attachmentId", "courseBanner", "thumbnailId"]


def _load_records() -> list[dict[str, Any]]:
    records = []
    for projects in sorted(ROOT.glob("output_pbl_*/processed/projects.jsonl")):
        with open(projects, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record["_source_file"] = str(projects)
                records.append(record)
    return records


def _processed_by_bid() -> dict[str, Path]:
    """business_id -> 海报处理交付中的去码海报（目录名以 __business_id 结尾）。"""
    by_bid: dict[str, Path] = {}
    if not OCT_DIR.exists():
        return by_bid
    for f in OCT_DIR.rglob("*"):
        if f.is_file() and common.is_image(f) and f.name == "海报.jpg":
            m = re.search(r"__([0-9]{6,})$", f.parent.name)
            if m:
                by_bid.setdefault(m.group(1), f)
    return by_bid


def _load_selection() -> dict[str, dict[str, Any]]:
    """business_id -> copied entry from the October selection manifest."""
    if not SELECTION.exists():
        return {}
    data = json.loads(SELECTION.read_text(encoding="utf-8"))
    by_bid: dict[str, dict[str, Any]] = {}
    for entry in data.get("copied", []):
        bid = str(entry.get("business_id") or "")
        if bid and bid not in by_bid:
            by_bid[bid] = entry
    return by_bid


def _asset_posters_by_bid() -> dict[str, list[Path]]:
    """business_id -> attachment poster candidates from asset manifests."""
    by_bid: dict[str, list[Path]] = {}
    for manifest_path in sorted(ROOT.glob("output_pbl_*/processed/asset_manifest.json")):
        try:
            entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in entries:
            file_path = entry.get("file")
            field = str(entry.get("field") or "")
            if not file_path or field not in FIELD_PRIORITY:
                continue
            bid = str(entry.get("manifest_key", "").split("::", 1)[0])
            if not bid:
                continue
            path = Path(file_path)
            if not path.is_absolute():
                path = ROOT / path
            if path.is_file() and path.stat().st_size > 0 and common.is_image(path):
                by_bid.setdefault(bid, []).append(path)
                processed = path.with_name(f"Finish_{path.name}")
                if processed.is_file() and processed not in by_bid[bid]:
                    by_bid[bid].append(processed)
    return by_bid


def _pick_asset_poster(candidates: list[Path]) -> Path | None:
    # 处理版（Finish 标记）优先（需求：广告内页用去二维码版本）
    for path in candidates:
        if common.is_processed_name(path.name):
            return path
    for field in FIELD_PRIORITY:
        for path in candidates:
            if f"::{field}" in str(path):
                return path
    return candidates[0] if candidates else None


def build(root: Path = ROOT) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = common.dedup_keep_latest(
        _load_records(),
        key_fn=lambda r: str(r.get("business_id") or ""),
        crawled_fn=lambda r: r.get("crawled_at"),
    )
    selection = _load_selection()
    assets = _asset_posters_by_bid()
    processed_by_bid = _processed_by_bid()

    items: list[dict[str, Any]] = []
    missing_posters: list[str] = []
    subject_counts: dict[str, int] = {}
    variant_counts = {"processed": 0, "raw": 0}
    with_dates = future = 0
    today = date.today().isoformat()

    for record in records:
        bid = str(record.get("business_id") or "")
        subject_original = common.map_subject(record.get("category")) or "其他"
        tagged = direction.classify(
            str(record.get("title") or ""),
            corpus=str(record.get("description") or ""),
            override_key=f"{SUPPLIER}:{bid}",
        )
        subject = tagged["subject"]
        subject_counts[subject] = subject_counts.get(subject, 0) + 1

        candidates: list[Path] = []
        variant = "raw"
        processed_copy = processed_by_bid.get(bid)
        if processed_copy is not None:
            candidates = [processed_copy]
            variant = "processed"
        entry = selection.get(bid)
        if not candidates and entry:
            output = Path(str(entry.get("output") or ""))
            if not output.is_absolute():
                output = ROOT / output
            if output.is_file() and output.stat().st_size > 0:
                # 开课时间交付副本为未去码原图，标记 raw（海报处理版缺失时的回退）
                candidates = [output]
                variant = "raw"
        if not candidates:
            picked = _pick_asset_poster(assets.get(bid, []))
            if picked is not None:
                candidates = [picked]
                variant = "processed" if common.is_processed_name(picked.name) else "raw"
        selected = candidates[0] if candidates else None
        if selected is None:
            missing_posters.append(bid)
            continue

        begins = common.normalize_date(record.get("lecture_course_begin_time")) or common.normalize_date(
            record.get("research_course_begin_time")
        )
        if not begins and entry:
            dates = entry.get("opening_dates") or []
            begins = common.normalize_date(dates[0]) if dates else None
        if begins:
            with_dates += 1
            if begins > today:
                future += 1
        variant_counts[variant] = variant_counts.get(variant, 0) + 1

        corpus = {
            k: record.get(k)
            for k in (
                "description", "direction", "major_name", "professor", "professor_position",
                "university", "keywords", "course_difficulty", "teaching_mode",
                "lecture_course_begin_time", "lecture_course_end_time",
                "research_course_begin_time", "research_course_end_time",
            )
            if record.get(k)
        }
        instructors = [str(record.get("professor") or "").strip()]
        items.append(common.build_item(
            supplier=SUPPLIER,
            recordId=bid,
            title=str(record.get("title") or ""),
            subject=subject,
            subjectSource=tagged["directionBasis"]["source"],
            subjectOriginal=subject_original,
            direction=tagged["direction"],
            directionSecondary=tagged["directionSecondary"],
            directionBasis=tagged["directionBasis"],
            projectType="PBL科研课题",
            schoolBegins=begins,
            instructors=[i for i in instructors if i],
            corpus=corpus,
            posterPath=str(selected),
            posterVariant=variant,
            posterSha256=common.sha256_file(selected),
            posterCandidates=[p for p in candidates if p != selected],
            sourceFile=str(record.get("_source_file") or ""),
            crawledAt=record.get("crawled_at"),
        ))

    report = {
        "total_courses": len(records),
        "posters_found": len(items),
        "missing_poster_ids": sorted(missing_posters),
        "with_school_begins": with_dates,
        "school_begins_future": future,
        "subject_distribution": subject_counts,
        "poster_variant_distribution": variant_counts,
        "selection_october_copied": len(selection),
        "october_delivery_exists": OCT_DIR.exists(),
        **direction.summarize(items),
    }
    return items, report
