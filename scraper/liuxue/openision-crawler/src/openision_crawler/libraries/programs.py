from __future__ import annotations

from typing import Any

from openision_crawler.libraries.models import Program
from openision_crawler.libraries.normalizers import normalize_fee, text_or_none
from openision_crawler.sanitize import sanitize_url


def _school_id(row: dict[str, Any], school: dict[str, Any]) -> str | None:
    return text_or_none(school.get("id") or row.get("school_id") or row.get("school_source_id") or row.get("school_cn"))


def build_programs(source_rows: list[dict[str, Any]], case_counts: dict[str, int]) -> list[Program]:
    programs: list[Program] = []
    for row in source_rows:
        school_value = row.get("school") if isinstance(row.get("school"), dict) else {}
        school: dict[str, Any] = school_value
        program_id = text_or_none(row.get("id") or row.get("source_id") or row.get("program_id"))
        school_id = _school_id(row, school)
        if not program_id or not school_id:
            continue
        fee_amount, fee_known, tuition_cn = normalize_fee(row.get("fees") or row.get("fee_amount"), row.get("tuition_cn"))
        qs_rank = school.get("qs") if school.get("qs") is not None else row.get("qs")
        try:
            qs_rank_int = int(qs_rank) if qs_rank is not None else None
        except (TypeError, ValueError):
            qs_rank_int = None
        programs.append(
            Program(
                program_id=program_id,
                school_id=school_id,
                school_name_cn=text_or_none(school.get("name") or row.get("school_name") or row.get("school_cn")),
                school_name_en=text_or_none(school.get("name_en") or row.get("school_name_en") or row.get("school_en")),
                country=text_or_none(school.get("country") or row.get("country")),
                qs_rank=qs_rank_int,
                major_name_cn=text_or_none(row.get("major_name_cn")),
                major_name_en=text_or_none(row.get("major_name_en")),
                major_direction=text_or_none(row.get("major_direction")),
                degree_type=text_or_none(row.get("degree_type") or row.get("level_text")),
                duration_cn=text_or_none(row.get("duration_cn")),
                tuition_cn=tuition_cn,
                fee_amount=fee_amount,
                fee_known=fee_known,
                application_requirements_cn=text_or_none(row.get("application_requirements_cn")),
                special_requirements=row.get("special_requirements"),
                language_requirements_detail=row.get("language_requirements_detail") or row.get("language_requirements"),
                application_time=row.get("application_time") or row.get("application_start_cn") or row.get("intake_time_cn"),
                official_url_internal=sanitize_url(text_or_none(row.get("official_url")) or "") or None,
                case_count=case_counts.get(program_id, 0),
                similar_case_count=int(row.get("similar_case_count") or 0),
                updated_at=text_or_none(row.get("updated_at") or row.get("crawled_at")),
            )
        )
    return sorted(programs, key=lambda item: item.program_id)
