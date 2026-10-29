from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Evidence(BaseModel):
    field_name: str
    value: str | None = None
    evidence_text: str | None = None
    source_url: str
    confidence: float = Field(ge=0.0, le=1.0)
    extractor: str


class ProjectRecord(BaseModel):
    project_uid: str | None = None
    project_name: str | None = None
    project_name_en: str | None = None
    category: str | None = None
    subcategory: str | None = None
    target_grade: str | None = None
    target_age: str | None = None
    target_student_profile: str | None = None
    delivery_mode: str | None = None
    location: str | None = None
    country: str | None = None
    city: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    application_deadline: str | None = None
    organizer: str | None = None
    partner_institution: str | None = None
    certificate: str | None = None
    output_result: str | None = None
    price: str | None = None
    currency: str | None = None
    price_notes: str | None = None
    application_requirement: str | None = None
    academic_requirement: str | None = None
    language_requirement: str | None = None
    description: str | None = None
    highlights: str | None = None
    admissions_value: str | None = None
    suitable_for: str | None = None
    not_suitable_for: str | None = None
    risks: str | None = None
    contact_info: str | None = None
    pdf_links: list[str] = Field(default_factory=list)
    image_links: list[str] = Field(default_factory=list)
    source_url: str
    source_title: str | None = None
    source_domain: str | None = None
    extraction_method: str
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    needs_human_review: bool = False
    crawled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str | None = None


class ParsedPage(BaseModel):
    source_url: str
    title: str | None = None
    h1: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    language: str | None = None
    body_text: str
    clean_html: str
    markdown: str
    links: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    asset_urls: list[str] = Field(default_factory=list)
    pdf_urls: list[str] = Field(default_factory=list)
    structured_data_json_ld: list[dict[str, Any]] = Field(default_factory=list)


class CrawlStats(BaseModel):
    started_at: datetime
    finished_at: datetime | None = None
    target_domain: str = "www.seedasdan.com"
    pages_requested: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    records_extracted: int = 0
    duplicate_records: int = 0
    error_categories: dict[str, int] = Field(default_factory=dict)
