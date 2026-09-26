from __future__ import annotations

from typing import Any
import json
import logging

from .config import Settings
from .storage import iter_jsonl, write_csv, write_json, write_jsonl, write_sqlite
from .utils import canonicalize_url, find_asset_urls, find_first, flatten_json, stable_hash, utc_now

LOGGER = logging.getLogger(__name__)


TITLE_FIELDS = ["title", "name", "courseName", "projectName", "topicName", "productName"]
CATEGORY_FIELDS = ["category", "level1Name", "classifyName", "subjectName", "industryName", "major"]
PROFESSOR_FIELDS = ["professor", "teacher", "instructor", "professorName", "teacherName"]
UNIVERSITY_FIELDS = ["university", "school", "college", "institution"]
DESCRIPTION_FIELDS = ["description", "intro", "introduction", "summary", "content"]
ID_FIELDS = ["id", "uuid", "courseId", "projectId", "courseExtendId", "productPackageId"]


def normalize_data(settings: Settings) -> list[dict[str, Any]]:
    raw_records = _load_raw_records(settings)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in raw_records:
        payload = _payload(raw)
        business_id = find_first(payload, ID_FIELDS) or raw.get("business_id") or stable_hash(json.dumps(payload, ensure_ascii=False))
        key = str(business_id)
        if key in seen:
            continue
        seen.add(key)
        title = find_first(payload, TITLE_FIELDS) or f"project-{business_id}"
        source_url = raw.get("source_url") or find_first(raw, ["source_url", "url"]) or ""
        record = {
            "business_id": str(business_id),
            "title": str(title),
            "category": _string_or_none(find_first(payload, CATEGORY_FIELDS)),
            "professor": _string_or_none(find_first(payload, PROFESSOR_FIELDS)),
            "university": _string_or_none(find_first(payload, UNIVERSITY_FIELDS)),
            "description": _string_or_none(find_first(payload, DESCRIPTION_FIELDS)),
            "source_url": source_url,
            "canonical_url": canonicalize_url(source_url) if source_url else "",
            "crawled_at": raw.get("crawled_at") or utc_now(),
            "asset_urls": find_asset_urls(payload),
            "raw": payload,
        }
        flat = flatten_json(payload)
        for key_name, value in flat.items():
            if key_name not in record and len(str(value)) < 5000:
                record[f"raw.{key_name}"] = value
        normalized.append(record)

    write_jsonl(settings.processed_dir / "projects.jsonl", normalized)
    write_csv(settings.processed_dir / "projects.csv", normalized)
    write_sqlite(settings.processed_dir / "projects.sqlite", normalized)
    write_json(
        settings.processed_dir / "data_quality_summary.json",
        {
            "raw_records": len(raw_records),
            "normalized_records": len(normalized),
            "duplicate_records": len(raw_records) - len(normalized),
            "missing_title": sum(1 for item in normalized if not item.get("title")),
            "records_with_assets": sum(1 for item in normalized if item.get("asset_urls")),
        },
    )
    LOGGER.info("标准化完成: records=%s", len(normalized))
    return normalized


def _load_raw_records(settings: Settings) -> list[dict[str, Any]]:
    details = list(iter_jsonl(settings.raw_dir / "details_raw.jsonl") or [])
    if details:
        return details
    return list(iter_jsonl(settings.raw_dir / "list_items.jsonl") or [])


def _payload(raw: dict[str, Any]) -> dict[str, Any]:
    data = raw.get("data")
    if isinstance(data, dict):
        return data
    nested = raw.get("raw")
    if isinstance(nested, dict):
        return nested
    return raw


def _string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
