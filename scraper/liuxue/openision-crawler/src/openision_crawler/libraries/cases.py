from __future__ import annotations

from collections import Counter
from typing import Any

from openision_crawler.libraries.models import AdmissionCase
from openision_crawler.libraries.normalizers import (
    normalize_admission_year,
    normalize_school_tag,
    parse_float,
    text_or_none,
)
from openision_crawler.sanitize import sanitize_url


def count_cases_by_program(source_rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in source_rows:
        program_id = text_or_none(row.get("major_id") or row.get("program_id"))
        if program_id:
            counter[program_id] += 1
    return dict(counter)


def _stringify_score(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return text_or_none("; ".join(str(item) for item in value if item))
    return text_or_none(value)


def _summary(value: Any) -> str | None:
    if isinstance(value, list):
        return text_or_none("；".join(str(item) for item in value if item))
    return text_or_none(value)


def build_cases(source_rows: list[dict[str, Any]]) -> list[AdmissionCase]:
    cases: list[AdmissionCase] = []
    for row in source_rows:
        case_id = text_or_none(row.get("id") or row.get("source_id") or row.get("case_id"))
        program_id = text_or_none(row.get("major_id") or row.get("program_id"))
        school_id = text_or_none(row.get("target_school_id") or row.get("id_univ"))
        if not case_id or not program_id or not school_id:
            continue
        year, year_valid = normalize_admission_year(row.get("admission_year") or row.get("time_news"))
        english_score = _stringify_score(row.get("english_score"))
        source_url = text_or_none(row.get("url") or row.get("source_url") or row.get("school_logo_url") or row.get("related_school_image_url"))
        cases.append(
            AdmissionCase(
                case_id=case_id,
                program_id=program_id,
                target_school_id=school_id,
                target_school_name_cn=text_or_none(row.get("target_school_name")),
                target_school_name_en=text_or_none(row.get("target_school_name_en")),
                related_major_name_cn=text_or_none(row.get("related_major_name_cn") or row.get("major_name")),
                related_school_name_cn=text_or_none(row.get("related_school_name_cn")),
                source_school_name=text_or_none(row.get("school_name")),
                school_tag_normalized=normalize_school_tag(row.get("school_tag")),
                major_direction=text_or_none(row.get("major_direction") or row.get("major_subject")),
                china_gpa=parse_float(row.get("china_gpa") if row.get("china_gpa") is not None else row.get("gpa")),
                gpa_raw=text_or_none(row.get("gpa") if row.get("gpa") is not None else row.get("china_gpa")),
                english_score=english_score,
                english_score_known=english_score is not None,
                admission_year=year,
                admission_year_valid=year_valid,
                experience_summary=_summary(row.get("exp_info") or row.get("base_info")),
                background_tags=[],
                source_url_internal=sanitize_url(source_url or "") or None,
            )
        )
    return sorted(cases, key=lambda item: item.case_id)
