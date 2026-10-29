"""Pure record-shaping helpers for the PBL crawler.

Extracted from pbl_crawler so the network/layout pipeline stays separate;
pbl_crawler re-exports these names for backward compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .storage import iter_jsonl
from .utils import canonicalize_url, stable_hash, utc_now


def _records_from_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = data.get("data", {}) if isinstance(data, dict) else {}
    records = payload.get("courseList", {}).get("records", [])
    if not records or not isinstance(records, list):
        records = payload.get("records", [])
    return [item for item in records if isinstance(item, dict)]


def _dedupe_pbl_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep one deterministic, most-complete list item per public course ID."""
    unique: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for record in records:
        business_id = str(record.get("courseExtendId") or record.get("courseId") or "").strip()
        key = business_id or f"raw:{stable_hash(json.dumps(record, ensure_ascii=False, sort_keys=True))}"
        existing = unique.get(key)
        if existing is None:
            unique[key] = record
            continue
        duplicates += 1
        if _pbl_record_score(record) > _pbl_record_score(existing):
            unique[key] = record
    return list(unique.values()), duplicates


def _pbl_record_score(record: dict[str, Any]) -> int:
    fields = (
        "courseExtendNameCn",
        "courseNameCn",
        "productPackageId",
        "h5Type",
        "majorMax",
        "direction",
        "professorName",
        "researchName",
        "attachmentId",
        "thumbnailId",
        "courseBanner",
        "industryPoster",
    )
    return sum(value not in (None, "") for value in (record.get(field) for field in fields))


def _known_business_ids(paths: list[Path]) -> set[str]:
    """Load stable PBL business IDs from previous normalized project outputs."""
    business_ids: set[str] = set()
    seen_paths: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        for project in iter_jsonl(path) or []:
            business_id = str(project.get("business_id") or "").strip()
            if business_id:
                business_ids.add(business_id)
    return business_ids


def _new_projects(projects: list[dict[str, Any]], known_business_ids: set[str]) -> list[dict[str, Any]]:
    return [
        project
        for project in projects
        if str(project.get("business_id") or "").strip() not in known_business_ids
    ]


def _normalize_projects(records: list[dict[str, Any]], major_map: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in records:
        business_id = str(item.get("courseExtendId") or item.get("courseId") or "")
        title = str(item.get("courseExtendNameCn") or item.get("courseNameCn") or business_id)
        major = major_map.get(str(item.get("majorMax") or ""))
        category = (major or {}).get("parent_name") or str(item.get("direction") or "uncategorized")
        source_url = (
            "https://pbl.hirepglobal.com/Professor"
            f"?courseExtendId={item.get('courseExtendId')}"
            f"&productPackageId={item.get('productPackageId')}"
            f"&h5Type={item.get('h5Type')}"
        )
        assets = [
            {"field": field, "attachment_id": str(item[field])}
            for field in ("attachmentId", "thumbnailId", "courseBanner", "industryPoster")
            if item.get(field)
        ]
        record = {
            "business_id": business_id,
            "title": title,
            "title_en": item.get("courseNameEn") or item.get("courseExtendNameEn"),
            "category": category,
            "direction": item.get("direction"),
            "major_id": item.get("majorMax"),
            "major_name": (major or {}).get("name"),
            "professor": item.get("professorName") or item.get("researchName"),
            "professor_position": item.get("professorPosition") or item.get("researchPositionCn"),
            "university": item.get("collegeName") or item.get("researchTakeOfficeSchool"),
            "description": item.get("researchIntroduceCn") or item.get("researchDirection"),
            "keywords": _split_keywords(item.get("keywords")),
            "course_difficulty": item.get("courseDifficulty"),
            "teaching_mode": item.get("teachingMode"),
            "first_course_begin_time": item.get("firstCourseBeginTime"),
            "lecture_course_begin_time": item.get("lectureCourseBeginTime"),
            "lecture_course_end_time": item.get("lectureCourseEndTime"),
            "research_course_begin_time": item.get("researchCourseBeginTime"),
            "research_course_end_time": item.get("researchCourseEndTime"),
            "source_url": source_url,
            "canonical_url": canonicalize_url(source_url),
            "crawled_at": utc_now(),
            "asset_urls": [],
            "assets": assets,
            "raw": item,
        }
        out.append(record)
    return out


def _split_keywords(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def _decorate_record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_url": "https://pbl.hirepglobal.com/customizePoster",
        "crawled_at": utc_now(),
        "business_id": str(item.get("courseExtendId") or item.get("courseId") or ""),
        "raw": item,
    }

