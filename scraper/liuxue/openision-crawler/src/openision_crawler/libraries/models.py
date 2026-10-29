from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Program:
    program_id: str
    school_id: str
    school_name_cn: str | None = None
    school_name_en: str | None = None
    country: str | None = None
    qs_rank: int | None = None
    major_name_cn: str | None = None
    major_name_en: str | None = None
    major_direction: str | None = None
    degree_type: str | None = None
    duration_cn: str | None = None
    tuition_cn: str | None = None
    fee_amount: float | None = None
    fee_known: bool = False
    application_requirements_cn: str | None = None
    special_requirements: Any = None
    language_requirements_detail: Any = None
    application_time: Any = None
    official_url_internal: str | None = None
    case_count: int = 0
    similar_case_count: int = 0
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdmissionCase:
    case_id: str
    program_id: str
    target_school_id: str
    target_school_name_cn: str | None = None
    target_school_name_en: str | None = None
    related_major_name_cn: str | None = None
    related_school_name_cn: str | None = None
    source_school_name: str | None = None
    school_tag_normalized: str = "未知背景"
    major_direction: str | None = None
    china_gpa: float | None = None
    gpa_raw: str | None = None
    english_score: str | None = None
    english_score_known: bool = False
    admission_year: int | None = None
    admission_year_valid: bool = False
    experience_summary: str | None = None
    background_tags: list[str] = field(default_factory=list)
    source_url_internal: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class School:
    school_id: str
    school_name_cn: str | None = None
    school_name_en: str | None = None
    country: str | None = None
    qs_rank: int | None = None
    logo_url_internal: str | None = None
    program_count: int = 0
    case_count: int = 0
    major_directions: list[str] = field(default_factory=list)
    top_programs: list[dict[str, Any]] = field(default_factory=list)
    admitted_gpa_distribution: dict[str, Any] = field(default_factory=dict)
    admission_year_range: dict[str, int | None] = field(default_factory=dict)
    source_record_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
