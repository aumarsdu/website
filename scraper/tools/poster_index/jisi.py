"""集思未来 index builder (需求文档 3.1 / 一期)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from . import common
from .common import SCRAPER_ROOT

SUPPLIER = "集思未来"
ROOT = SCRAPER_ROOT / "集思未来"
MANIFEST = ROOT / "poster" / "_organization_manifest.json"
RECORD_BATCHES = [
    ROOT / "output/full_refresh/20260703-new-check/domestic/processed/records.jsonl",
    ROOT / "output/full_refresh/20260703-new-check/sou_tools/processed/records.jsonl",
]
CORPUS_FIELDS = [
    "introduce", "projectBackground", "courseOutlineDetail", "output", "cycle",
    "suggestSenior", "suggestCollege", "suggestBasics", "teacherDetail",
    "teacherSchoolDetail", "dTeacherDetail", "foundationCourseName",
]


def _load_manifest() -> dict[str, dict[str, Any]]:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_rid: dict[str, dict[str, Any]] = {}
    for entry in entries:
        rid = str(entry.get("record_id") or "")
        if rid and rid not in by_rid:
            by_rid[rid] = entry
    return by_rid


def _load_records() -> tuple[list[dict[str, Any]], dict[str, int]]:
    records = []
    per_file: dict[str, int] = {}
    for path in RECORD_BATCHES:
        count = 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record["_source_file"] = str(path)
                records.append(record)
                count += 1
        per_file[str(path)] = count
    return records, per_file


def _instructors(raw: dict[str, Any]) -> list[str]:
    names = []
    for field in ("teacherNickName", "teacherName", "dTeacherNickName"):
        value = str(raw.get(field) or "").strip()
        if value and value not in names:
            names.append(value)
    return names


def build(root: Path = ROOT) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = _load_manifest()
    records, per_file = _load_records()
    records = common.dedup_keep_latest(
        records, key_fn=lambda r: str((r.get("raw") or {}).get("id") or r.get("id") or ""),
        crawled_fn=lambda r: r.get("crawled_at"),
    )

    # one-pass poster filename index under poster/
    poster_files: list[Path] = []
    for f in (root / "poster").rglob("*"):
        if f.is_file() and common.is_image(f):
            poster_files.append(f)

    items: list[dict[str, Any]] = []
    missing_posters: list[str] = []
    subject_counts: dict[str, int] = {}
    variant_counts = {"processed": 0, "raw": 0}
    with_dates = future = 0
    today = date.today().isoformat()

    for record in records:
        raw = record.get("raw") or {}
        rid = str(raw.get("id") or record.get("id") or "")
        entry = manifest.get(rid)
        candidates = [f for f in poster_files if rid in f.name]
        selected, variant, usable = common.select_poster(candidates, manifest_sha256=(entry or {}).get("sha256"))
        if selected is None:
            missing_posters.append(rid)
            continue

        subject = common.map_subject((entry or {}).get("subject"))
        subject_source = "supplier"
        if subject is None:
            subject = "其他"
            subject_source = "tagged"
        subject_counts[subject] = subject_counts.get(subject, 0) + 1
        variant_counts[variant] = variant_counts.get(variant, 0) + 1

        begins = common.normalize_date(raw.get("schoolBegins"))
        if begins:
            with_dates += 1
            if begins > today:
                future += 1

        items.append(common.build_item(
            supplier=SUPPLIER,
            recordId=rid,
            title=str(raw.get("name") or record.get("name") or ""),
            subject=subject,
            subjectSource=subject_source,
            projectType=str((entry or {}).get("project_type") or ""),
            schoolBegins=begins,
            instructors=_instructors(raw),
            corpus={f: raw.get(f) for f in CORPUS_FIELDS if raw.get(f)},
            posterPath=str(selected),
            posterVariant=variant,
            posterSha256=common.sha256_file(selected),
            posterCandidates=[f for f in usable if f != selected],
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
        "records_per_file": per_file,
        "manifest_entries": len(manifest),
    }
    return items, report
