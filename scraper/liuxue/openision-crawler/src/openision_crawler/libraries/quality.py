from __future__ import annotations

from typing import Any

from openision_crawler.libraries.models import AdmissionCase, Program, School


def _rate(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part / total, 4)


def build_quality_report(programs: list[Program], cases: list[AdmissionCase], schools: list[School]) -> dict[str, Any]:
    program_ids = {item.program_id for item in programs}
    school_ids = {item.school_id for item in schools}
    unknown_fee = sum(1 for item in programs if not item.fee_known)
    invalid_year = sum(1 for item in cases if not item.admission_year_valid)
    unknown_english = sum(1 for item in cases if not item.english_score_known)
    unknown_school_tag = sum(1 for item in cases if item.school_tag_normalized == "未知背景")
    return {
        "counts": {
            "programs": len(programs),
            "cases": len(cases),
            "schools": len(schools),
        },
        "joins": {
            "case_program_join_failures": sum(1 for item in cases if item.program_id not in program_ids),
            "case_school_join_failures": sum(1 for item in cases if item.target_school_id not in school_ids),
        },
        "quality": {
            "unknown_fee_programs": unknown_fee,
            "unknown_fee_program_rate": _rate(unknown_fee, len(programs)),
            "invalid_year_cases": invalid_year,
            "invalid_year_case_rate": _rate(invalid_year, len(cases)),
            "unknown_english_score_cases": unknown_english,
            "unknown_english_score_case_rate": _rate(unknown_english, len(cases)),
            "unknown_school_tag_cases": unknown_school_tag,
            "unknown_school_tag_case_rate": _rate(unknown_school_tag, len(cases)),
        },
    }
