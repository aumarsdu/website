#!/usr/bin/env python3
"""Prepare research-project crawler outputs for database import.

The script reads the latest processed crawler JSONL outputs and writes
database-shaped staging JSONL files. It does not connect to a database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NS = uuid.uuid5(uuid.NAMESPACE_URL, "helipei-research-project-database")

SECRET_KEY_RE = re.compile(
    r"(token|secret|password|cookie|authorization|session|apikey|api_key|access_key|private_key|credential)",
    re.I,
)

SOURCE_CONFIGS = [
    {
        "code": "hirep",
        "name": "HIREP",
        "provider": "HIREP",
        "path": "HIREP/output_pbl_full_refresh_20260602/processed/projects.jsonl",
        "asset_manifest": "HIREP/output_pbl_full_refresh_20260602/processed/asset_manifest.jsonl",
        "batch_code": "hirep_pbl_full_refresh_20260602",
    },
    {
        "code": "jisi_future_sou_tools",
        "name": "集思未来海外",
        "provider": "集思未来",
        "path": "集思未来/output/full_refresh/20260602-full-refresh/sou_tools/processed/records.jsonl",
        "batch_code": "jisi_future_sou_tools_full_refresh_20260602",
    },
    {
        "code": "jisi_future_domestic",
        "name": "集思未来国内",
        "provider": "集思未来",
        "path": "集思未来/output/full_refresh/20260602-full-refresh/domestic/processed/records.jsonl",
        "batch_code": "jisi_future_domestic_full_refresh_20260602",
    },
    {
        "code": "zhongke",
        "name": "中科",
        "provider": "中科",
        "path": "中科/output/processed/projects.jsonl",
        "batch_code": "zhongke_processed_20260602",
    },
]


def stable_id(*parts: Any) -> str:
    key = "|".join("" if p is None else str(p) for p in parts)
    return str(uuid.uuid5(NS, key))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def clean_text_list(values: Any) -> list[str]:
    result: list[str] = []
    for item in as_list(values):
        if isinstance(item, dict):
            for key in ("name", "label", "title", "url", "source_url"):
                text = text_or_none(item.get(key))
                if text:
                    result.append(text)
                    break
        else:
            text = text_or_none(item)
            if text:
                result.append(text)
    return sorted(dict.fromkeys(result))


def sanitize_raw(value: Any, stats: Counter[str]) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if SECRET_KEY_RE.search(str(key)):
                cleaned[key] = "[REDACTED]"
                stats["redacted_fields"] += 1
            else:
                cleaned[key] = sanitize_raw(item, stats)
        return cleaned
    if isinstance(value, list):
        return [sanitize_raw(item, stats) for item in value]
    return value


def norm_key(value: Any) -> str:
    text = text_or_none(value) or ""
    return re.sub(r"\s+", "", text).lower()


def first_present(*values: Any) -> str | None:
    for value in values:
        text = text_or_none(value)
        if text:
            return text
    return None


def raw_get(record: dict[str, Any], *keys: str) -> Any:
    raw = record.get("raw")
    if not isinstance(raw, dict):
        raw = {}
    for key in keys:
        if key in record and record.get(key) not in (None, "", []):
            return record.get(key)
        if key in raw and raw.get(key) not in (None, "", []):
            return raw.get(key)
    return None


def source_record_key(source_code: str, record: dict[str, Any]) -> str:
    candidates = [
        record.get("business_id"),
        record.get("record_key"),
        record.get("id"),
        record.get("uuid"),
        record.get("record_hash"),
        record.get("source_url"),
        record.get("canonical_url"),
        record.get("title"),
        record.get("name"),
    ]
    for value in candidates:
        text = text_or_none(value)
        if text:
            return text
    return json_hash(record)


def title_for(record: dict[str, Any]) -> str | None:
    return first_present(record.get("title"), record.get("name"), raw_get(record, "title", "name"))


def instructor_name_for(record: dict[str, Any]) -> str | None:
    return first_present(
        record.get("professor"),
        record.get("teacher"),
        record.get("teacherName"),
        raw_get(record, "teacherName", "teacherChineseName", "dTeacherNickName", "teacher"),
    )


def institution_name_for(record: dict[str, Any]) -> str | None:
    return first_present(
        record.get("university"),
        record.get("teacherSchool"),
        raw_get(record, "teacherSchool", "teacherChineseSchool", "dTeacherSchool", "schoolName", "university"),
    )


def taxonomy_values(source_code: str, record: dict[str, Any]) -> list[tuple[str, str]]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    pairs: list[tuple[str, str]] = []
    for value in clean_text_list(record.get("category") or raw.get("courseLevel1") or raw.get("topicLingyu")):
        pairs.append(("primary_discipline", value))
    for value in clean_text_list(record.get("categories") or raw.get("types") or raw.get("typeId")):
        pairs.append(("secondary_discipline", value))
    for value in clean_text_list(record.get("direction") or record.get("major_name") or raw.get("directionId") or raw.get("professionId")):
        pairs.append(("specialization", value))
    for value in clean_text_list(record.get("project_type") or raw.get("productType") or raw.get("productTypeNote")):
        pairs.append(("project_type", value))
    return list(dict.fromkeys(pairs))


def asset_type_from_url(url: str | None, role_hint: str | None = None) -> str:
    text = f"{role_hint or ''} {url or ''}".lower()
    if any(word in text for word in ("poster", "haibao", "海报", "summary_poster")):
        return "dn_poster"
    if any(word in text for word in ("avatar", "head", "teacherhead", "头像")):
        return "instructor_avatar"
    if ".pdf" in text:
        return "pdf"
    if any(ext in text for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return "image"
    return "other"


class StagingWriter:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.files: dict[str, Any] = {}
        self.counts: Counter[str] = Counter()
        self.skipped_duplicate_rows: Counter[str] = Counter()
        self.seen_keys: defaultdict[str, set[str]] = defaultdict(set)

    def primary_key(self, table: str, row: dict[str, Any]) -> str | None:
        if table == "asset_links":
            asset_id = row.get("asset_id")
            role = row.get("link_role")
            if row.get("canonical_project_id"):
                return f"asset_project|{asset_id}|{row.get('canonical_project_id')}|{role}"
            if row.get("instructor_id"):
                return f"asset_instructor|{asset_id}|{row.get('instructor_id')}|{role}"
            if row.get("provider_id"):
                return f"asset_provider|{asset_id}|{row.get('provider_id')}|{role}"
            if row.get("source_project_record_id"):
                return f"asset_source_record|{asset_id}|{row.get('source_project_record_id')}|{role}"
        if row.get("id"):
            return str(row["id"])
        if table in {"project_match_profiles"}:
            return str(row.get("canonical_project_id"))
        return None

    def write(self, table: str, row: dict[str, Any]) -> bool:
        primary_key = self.primary_key(table, row)
        if primary_key:
            if primary_key in self.seen_keys[table]:
                self.skipped_duplicate_rows[table] += 1
                return False
            self.seen_keys[table].add(primary_key)
        if table not in self.files:
            self.files[table] = (self.out_dir / f"{table}.jsonl").open("w", encoding="utf-8")
        self.files[table].write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        self.counts[table] += 1
        return True

    def close(self) -> None:
        for handle in self.files.values():
            handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="data_staging/research_db/20260602")
    args = parser.parse_args()

    out_dir = ROOT / args.out_dir
    writer = StagingWriter(out_dir)
    run_started_at = now_iso()
    redaction_stats: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    source_row_counts: Counter[str] = Counter()
    title_to_projects: defaultdict[str, list[str]] = defaultdict(list)
    title_to_project: dict[str, str] = {}
    source_version_by_hash: dict[tuple[str, str], int] = {}
    source_version_next: Counter[str] = Counter()

    providers_written: set[str] = set()
    institutions_written: set[str] = set()
    instructors_written: set[str] = set()
    taxonomy_written: set[str] = set()
    assets_written: set[str] = set()

    for config in SOURCE_CONFIGS:
        source_id = stable_id("source", config["code"])
        provider_id = stable_id("provider", config["provider"])
        batch_id = stable_id("batch", config["batch_code"])
        input_path = ROOT / config["path"]

        writer.write("sources", {
            "id": source_id,
            "code": config["code"],
            "name": config["name"],
            "source_type": "processed_jsonl",
            "base_url": None,
            "notes": "Generated from local crawler processed output.",
            "created_at": run_started_at,
            "updated_at": run_started_at,
        })
        writer.write("ingest_batches", {
            "id": batch_id,
            "source_id": source_id,
            "batch_code": config["batch_code"],
            "input_path": str(input_path.relative_to(ROOT)),
            "input_format": "jsonl",
            "started_at": run_started_at,
            "finished_at": run_started_at,
            "stats_json": {},
            "error_json": {},
            "created_at": run_started_at,
        })
        if provider_id not in providers_written:
            providers_written.add(provider_id)
            writer.write("providers", {
                "id": provider_id,
                "code": norm_key(config["provider"]),
                "name": config["provider"],
                "provider_type": "research_project_supplier",
                "country": None,
                "website_url": None,
                "cooperation_status": "unknown",
                "authorization_status": "unknown",
                "risk_level": "medium",
                "rights_notes": None,
                "is_active": True,
                "created_at": run_started_at,
                "updated_at": run_started_at,
            })

        with input_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                raw_record = json.loads(line)
                record_redaction_stats: Counter[str] = Counter()
                sanitized_record = sanitize_raw(raw_record, record_redaction_stats)
                redaction_stats.update(record_redaction_stats)
                raw_hash = json_hash(sanitized_record)
                key = source_record_key(config["code"], sanitized_record)
                record_id = stable_id("source_project_record", config["code"], key)
                version_id = stable_id("source_project_record_version", config["code"], key, raw_hash)
                version_key = (record_id, raw_hash)
                if version_key not in source_version_by_hash:
                    source_version_next[record_id] += 1
                    source_version_by_hash[version_key] = source_version_next[record_id]
                source_version = source_version_by_hash[version_key]
                project_id = stable_id("canonical_project", config["code"], key)
                title = title_for(sanitized_record)
                source_url = first_present(sanitized_record.get("source_url"), raw_get(sanitized_record, "_source_url"))
                canonical_url = first_present(sanitized_record.get("canonical_url"), source_url)
                crawled_at = text_or_none(sanitized_record.get("crawled_at"))
                source_row_counts[config["code"]] += 1

                writer.write("source_project_records", {
                    "id": record_id,
                    "source_id": source_id,
                    "source_record_key": key,
                    "latest_source_url": source_url,
                    "latest_canonical_url": canonical_url,
                    "latest_title_raw": title,
                    "latest_raw_hash": raw_hash,
                    "latest_version_id": version_id,
                    "record_status": "active",
                    "first_seen_at": crawled_at or run_started_at,
                    "latest_seen_at": crawled_at or run_started_at,
                    "created_at": run_started_at,
                    "updated_at": run_started_at,
                })
                writer.write("source_project_record_versions", {
                    "id": version_id,
                    "source_project_record_id": record_id,
                    "ingest_batch_id": batch_id,
                    "version": source_version,
                    "source_url": source_url,
                    "canonical_url": canonical_url,
                    "title_raw": title,
                    "raw_json": sanitized_record,
                    "raw_hash": raw_hash,
                    "redaction_status": "redacted" if record_redaction_stats["redacted_fields"] else "none",
                    "redaction_reason": "secret_like_key" if record_redaction_stats["redacted_fields"] else None,
                    "tombstoned_at": None,
                    "crawled_at": crawled_at,
                    "created_at": run_started_at,
                })
                writer.write("canonical_projects", {
                    "id": project_id,
                    "provider_id": provider_id,
                    "title": title or f"Untitled {config['code']} {line_number}",
                    "title_normalized": norm_key(title),
                    "project_type": first_present(raw_get(sanitized_record, "productTypeNote", "productType"), "research_project"),
                    "topic_info": first_present(
                        sanitized_record.get("description"),
                        raw_get(sanitized_record, "description", "projectBackground", "courseOutlineDetail", "introduce"),
                    ),
                    "canonical_summary": first_present(
                        sanitized_record.get("description"),
                        raw_get(sanitized_record, "projectBackground", "introduce"),
                    ),
                    "status": "imported",
                    "readiness": "searchable",
                    "primary_source_record_id": record_id,
                    "current_display_profile_id": None,
                    "created_at": run_started_at,
                    "updated_at": run_started_at,
                })
                writer.write("project_source_links", {
                    "id": stable_id("project_source_link", project_id, record_id),
                    "canonical_project_id": project_id,
                    "source_project_record_id": record_id,
                    "link_type": "primary",
                    "confidence": 1.0,
                    "created_at": run_started_at,
                })

                if title:
                    title_to_projects[norm_key(title)].append(project_id)
                    title_to_project.setdefault(title, project_id)

                for link_type, url in (("web_page", source_url), ("canonical", canonical_url)):
                    if url:
                        writer.write("project_links", {
                            "id": stable_id("project_link", project_id, link_type, url),
                            "canonical_project_id": project_id,
                            "link_type": link_type,
                            "url": url,
                            "label": link_type,
                            "rights_notes": "Default internal-search only until rights scope is approved.",
                            "last_verified_at": crawled_at,
                            "valid_until": None,
                            "staleness_status": "unknown",
                            "created_at": run_started_at,
                        })

                duration = first_present(sanitized_record.get("cycle"), raw_get(sanitized_record, "cycle"))
                start_date_text = first_present(sanitized_record.get("schoolBegins"), raw_get(sanitized_record, "schoolBegins", "startTime"))
                writer.write("project_offerings", {
                    "id": stable_id("project_offering", project_id, "default"),
                    "canonical_project_id": project_id,
                    "offering_code": "default",
                    "duration": duration,
                    "start_date_text": start_date_text,
                    "start_date": None,
                    "end_date": None,
                    "delivery_mode": text_or_none(raw_get(sanitized_record, "teachingMode")),
                    "delivery_country": None,
                    "capacity": None,
                    "enrollment_status": text_or_none(raw_get(sanitized_record, "courseJoinStatus", "courseStatusNote")),
                    "price_amount": None,
                    "price_currency": "CNY",
                    "last_verified_at": crawled_at,
                    "valid_until": None,
                    "staleness_status": "unknown",
                    "created_at": run_started_at,
                    "updated_at": run_started_at,
                })

                institution_name = institution_name_for(sanitized_record)
                institution_id = None
                if institution_name:
                    institution_id = stable_id("institution", norm_key(institution_name))
                    if institution_id not in institutions_written:
                        institutions_written.add(institution_id)
                        writer.write("institutions", {
                            "id": institution_id,
                            "name": institution_name,
                            "name_normalized": norm_key(institution_name),
                            "name_en": None,
                            "country": None,
                            "website_url": None,
                            "created_at": run_started_at,
                            "updated_at": run_started_at,
                        })

                instructor_name = instructor_name_for(sanitized_record)
                if instructor_name:
                    instructor_id = stable_id("instructor", norm_key(instructor_name), institution_id or "")
                    if instructor_id not in instructors_written:
                        instructors_written.add(instructor_id)
                        writer.write("instructors", {
                            "id": instructor_id,
                            "name": instructor_name,
                            "name_normalized": norm_key(instructor_name),
                            "institution_id": institution_id,
                            "institution_name_raw": institution_name,
                            "academic_title": first_present(raw_get(sanitized_record, "teacherLevel", "dTeacherLevel", "teacherType")),
                            "country": None,
                            "bio_raw": first_present(raw_get(sanitized_record, "teacherDetail", "dTeacherDetail", "teacherSchoolDetail")),
                            "bio_edited": None,
                            "paper_guidance_scope": None,
                            "avatar_asset_id": None,
                            "usage_rights_status": "unknown",
                            "takedown_requested_at": None,
                            "created_at": run_started_at,
                            "updated_at": run_started_at,
                        })
                    writer.write("project_instructors", {
                        "id": stable_id("project_instructor", project_id, instructor_id, "primary"),
                        "canonical_project_id": project_id,
                        "instructor_id": instructor_id,
                        "role": "primary",
                        "confidence": 0.9,
                        "created_at": run_started_at,
                    })

                for term_type, term_name in taxonomy_values(config["code"], sanitized_record):
                    term_id = stable_id("taxonomy_term", term_type, norm_key(term_name))
                    if term_id not in taxonomy_written:
                        taxonomy_written.add(term_id)
                        writer.write("taxonomy_terms", {
                            "id": term_id,
                            "term_type": term_type,
                            "name": term_name,
                            "name_en": None,
                            "slug": norm_key(term_name),
                            "parent_id": None,
                            "is_active": True,
                            "created_at": run_started_at,
                        })
                    writer.write("project_taxonomy_links", {
                        "id": stable_id("project_taxonomy_link", project_id, term_id),
                        "canonical_project_id": project_id,
                        "taxonomy_term_id": term_id,
                        "term_type": term_type,
                        "confidence": 0.7,
                        "source_type": "source_imported",
                        "created_at": run_started_at,
                    })

                suitable_grades = clean_text_list(raw_get(sanitized_record, "suggestGrade", "suggestSenior", "suggestCollege", "suggestMaster", "suggestMiddle"))
                prerequisites = clean_text_list(raw_get(sanitized_record, "suggestBasics", "foundationCourseName"))
                writer.write("project_match_profiles", {
                    "canonical_project_id": project_id,
                    "suitable_student_directions": clean_text_list(raw_get(sanitized_record, "types", "topicLingyu")),
                    "suitable_grades": suitable_grades,
                    "suitable_majors_cache": clean_text_list(sanitized_record.get("major_name")),
                    "difficulty_level": first_present(raw_get(sanitized_record, "difficulty")),
                    "prerequisite_courses": prerequisites,
                    "programming_requirement": None,
                    "math_requirement": None,
                    "lab_requirement": None,
                    "language_requirement": None,
                    "application_goal_fit": [],
                    "created_at": run_started_at,
                    "updated_at": run_started_at,
                })
                writer.write("project_display_profiles", {
                    "id": stable_id("display_profile", project_id, 1),
                    "canonical_project_id": project_id,
                    "version": 1,
                    "public_slug": None,
                    "status": "draft",
                    "display_title": title,
                    "card_summary": first_present(raw_get(sanitized_record, "projectBackground", "introduce"), sanitized_record.get("description")),
                    "project_summary": first_present(raw_get(sanitized_record, "projectBackground", "introduce"), sanitized_record.get("description")),
                    "topic_information_display": first_present(raw_get(sanitized_record, "courseOutlineDetail"), sanitized_record.get("description")),
                    "research_question": None,
                    "research_method": None,
                    "expected_outputs": first_present(raw_get(sanitized_record, "output")),
                    "instructor_bio_display": None,
                    "suitable_for_display": ", ".join(suitable_grades) if suitable_grades else None,
                    "show_price": False,
                    "published_at": None,
                    "created_at": run_started_at,
                    "updated_at": run_started_at,
                })

                asset_urls = clean_text_list(sanitized_record.get("asset_urls"))
                for asset_url in asset_urls:
                    asset_id = stable_id("asset", asset_url)
                    if asset_id not in assets_written:
                        assets_written.add(asset_id)
                        writer.write("assets", {
                            "id": asset_id,
                            "asset_type": asset_type_from_url(asset_url),
                            "source_url": asset_url,
                            "asset_uri": None,
                            "file_name": None,
                            "content_type": None,
                            "bytes": None,
                            "sha256": None,
                            "manifest_key": None,
                            "usage_rights_status": "unknown",
                            "rights_notes": "Default internal-search only until reviewed.",
                            "takedown_requested_at": None,
                            "takedown_reason": None,
                            "last_verified_at": crawled_at,
                            "valid_until": None,
                            "staleness_status": "unknown",
                            "raw_json": {},
                            "created_at": run_started_at,
                            "updated_at": run_started_at,
                        })
                    writer.write("asset_links", {
                        "id": stable_id("asset_link", asset_id, project_id, "source_asset"),
                        "asset_id": asset_id,
                        "canonical_project_id": project_id,
                        "instructor_id": None,
                        "provider_id": None,
                        "source_project_record_id": record_id,
                        "link_role": asset_type_from_url(asset_url),
                        "is_primary": False,
                        "source_evidence_json": {"source": "record.asset_urls"},
                        "created_at": run_started_at,
                    })

                missing_checks = {
                    "missing_title": not title,
                    "missing_source_url": not source_url,
                    "missing_instructor": not instructor_name,
                    "missing_institution": not institution_name,
                    "missing_taxonomy": not taxonomy_values(config["code"], sanitized_record),
                    "missing_duration": not duration,
                    "missing_start_date": not start_date_text,
                }
                for issue_type, failed in missing_checks.items():
                    if failed:
                        wrote_quality_issue = writer.write("data_quality_issues", {
                            "id": stable_id("quality_issue", project_id, issue_type),
                            "canonical_project_id": project_id,
                            "source_project_record_id": record_id,
                            "issue_type": issue_type,
                            "severity": "medium",
                            "field_name": issue_type.replace("missing_", ""),
                            "description": f"{issue_type} detected during staging preparation.",
                            "status": "open",
                            "created_at": run_started_at,
                            "resolved_at": None,
                        })
                        if wrote_quality_issue:
                            quality_counts[issue_type] += 1

                writer.write("enrichment_tasks", {
                    "id": stable_id("enrichment_task", project_id, "phase_1a_business_fields"),
                    "canonical_project_id": project_id,
                    "task_type": "phase_1a_business_fields",
                    "field_name": "supplier_commercial_sales_fit_claims_rights",
                    "assigned_role": "operations",
                    "assigned_user_id": None,
                    "status": "open",
                    "due_at": None,
                    "created_at": run_started_at,
                    "completed_at": None,
                })

    # HIREP asset manifest can add local file metadata and links by title.
    for config in SOURCE_CONFIGS:
        manifest_rel = config.get("asset_manifest")
        if not manifest_rel:
            continue
        manifest_path = ROOT / manifest_rel
        if not manifest_path.exists():
            continue
        with manifest_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                item = json.loads(line)
                source_url = text_or_none(item.get("source_url"))
                file_path = text_or_none(item.get("file"))
                manifest_key = text_or_none(item.get("manifest_key"))
                asset_key = source_url or file_path or manifest_key
                if not asset_key:
                    continue
                asset_id = stable_id("asset", asset_key)
                if asset_id not in assets_written:
                    assets_written.add(asset_id)
                    writer.write("assets", {
                        "id": asset_id,
                        "asset_type": asset_type_from_url(source_url or file_path, text_or_none(item.get("field"))),
                        "source_url": source_url,
                        "asset_uri": file_path,
                        "file_name": Path(file_path).name if file_path else None,
                        "content_type": text_or_none(item.get("content_type")),
                        "bytes": item.get("bytes"),
                        "sha256": None,
                        "manifest_key": manifest_key,
                        "usage_rights_status": "unknown",
                        "rights_notes": "Default internal-search only until reviewed.",
                        "takedown_requested_at": None,
                        "takedown_reason": None,
                        "last_verified_at": None,
                        "valid_until": None,
                        "staleness_status": "unknown",
                        "raw_json": sanitize_raw(item, redaction_stats),
                        "created_at": run_started_at,
                        "updated_at": run_started_at,
                    })
                project_id = title_to_project.get(text_or_none(item.get("record_title")) or "")
                if project_id:
                    writer.write("asset_links", {
                        "id": stable_id("asset_link", asset_id, project_id, "manifest_asset"),
                        "asset_id": asset_id,
                        "canonical_project_id": project_id,
                        "instructor_id": None,
                        "provider_id": None,
                        "source_project_record_id": None,
                        "link_role": asset_type_from_url(source_url or file_path, text_or_none(item.get("field"))),
                        "is_primary": False,
                        "source_evidence_json": {"source": "asset_manifest", "field": item.get("field")},
                        "created_at": run_started_at,
                    })

    for title_norm, project_ids in title_to_projects.items():
        unique_project_ids = sorted(set(project_ids))
        if len(unique_project_ids) < 2:
            continue
        for left, right in zip(unique_project_ids, unique_project_ids[1:]):
            writer.write("merge_candidates", {
                "id": stable_id("merge_candidate", left, right),
                "left_project_id": left,
                "right_project_id": right,
                "similarity_score": 0.75,
                "evidence_json": {"normalized_title": title_norm, "reason": "same_normalized_title"},
                "status": "open",
                "reviewed_by": None,
                "reviewed_at": None,
                "created_at": run_started_at,
            })

    writer.close()

    manifest = {
        "run_started_at": run_started_at,
        "output_dir": str(out_dir.relative_to(ROOT)),
        "source_configs": SOURCE_CONFIGS,
        "source_row_counts": dict(source_row_counts),
        "table_counts": dict(writer.counts),
        "skipped_duplicate_rows": dict(writer.skipped_duplicate_rows),
        "quality_issue_counts": dict(quality_counts),
        "redaction_stats": dict(redaction_stats),
        "selected_batches": {
            "hirep": "HIREP full refresh, newer and larger than earlier full batch.",
            "jisi_future": "20260602 full_refresh sou_tools + domestic.",
            "zhongke": "Current output/processed batch.",
        },
        "excluded_from_main_import": [
            "older HIREP output_pbl_full_20260602",
            "older 集思未来 output/processed",
            "older 集思未来 output_domestic/processed",
            "引知 archive data: not research-project SKU primary data",
        ],
    }
    (out_dir / "import_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "README.md").write_text(
        "\n".join([
            "# Research DB Staging Export",
            "",
            "This folder contains database-shaped JSONL staging tables generated from local crawler outputs.",
            "",
            "It is not a production database dump and does not connect to PostgreSQL.",
            "",
            "Selected main batches:",
            "",
            "- HIREP: `HIREP/output_pbl_full_refresh_20260602/processed/projects.jsonl`",
            "- 集思未来海外: `集思未来/output/full_refresh/20260602-full-refresh/sou_tools/processed/records.jsonl`",
            "- 集思未来国内: `集思未来/output/full_refresh/20260602-full-refresh/domestic/processed/records.jsonl`",
            "- 中科: `中科/output/processed/projects.jsonl`",
            "",
            "Recommended import order:",
            "",
            "1. `sources`",
            "2. `providers`",
            "3. `ingest_batches`",
            "4. `source_project_records`",
            "5. `source_project_record_versions`",
            "6. `canonical_projects`",
            "7. supporting entities: institutions, instructors, taxonomy_terms, assets",
            "8. link/profile tables",
            "9. quality issues, enrichment tasks, merge candidates",
            "",
            "Import boundary:",
            "",
            "- `source_project_record_versions.raw_json` preserves sanitized raw crawler data.",
            "- `canonical_projects` is deduplicated by source and source record key.",
            "- `source_project_record_versions` can contain more rows than `source_project_records` when duplicate source keys are present.",
            "- `assets` contains metadata only; binary files are not embedded.",
            "- `enrichment_tasks` marks Phase 1A fields that still require operations input: supplier, commercial, sales, customer fit, claims, and rights.",
            "",
            "Unknown asset and content rights are treated as internal-search only until reviewed.",
            "",
            "Use `import_manifest.json` as the machine-readable summary for counts, skipped duplicate rows, and data-quality issue totals.",
        ]),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
