"""Field registry and runtime settings for the research fact input package.

The six canonical fields below are the contract of this package. Every one of
them is intentionally narrow: this layer records what a source document
*states*, and nothing else. It never infers a value, and it never promotes a
supplier marketing sentence into a verified fact.

Field names and risk levels follow the workspace design docs:

* ``canonical_projects.title`` / ``project_display_profiles.display_title``
* ``instructors.name``
* ``project_offerings.start_date_text``
* ``project_offerings.duration``
* ``project_match_profiles.suitable_student_directions`` / ``suitable_grades``
* ``project_deliverable_claims.claim_text``

Risk levels follow design doc section 8.2 (low / medium / high).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Canonical field registry
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    """Definition of one canonical fact field."""

    name: str
    label_zh: str
    risk_level: str
    design_target: str
    multi_line: bool = False
    note: str = ""

    @property
    def is_high_risk(self) -> bool:
        return self.risk_level == "high"


CANONICAL_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        name="project_title",
        label_zh="课题名",
        risk_level="low",
        design_target="canonical_projects.title",
        note="Poster short titles and web long titles are different strings, not a conflict of fact.",
    ),
    FieldSpec(
        name="instructor",
        label_zh="导师",
        risk_level="high",
        design_target="instructors.name",
        note="Never derived from a biography; an absent name stays missing.",
    ),
    FieldSpec(
        name="start_date",
        label_zh="日期",
        risk_level="low",
        design_target="project_offerings.start_date_text",
        note="A season or year without day/month keeps its precision instead of being filled in.",
    ),
    FieldSpec(
        name="duration",
        label_zh="周期",
        risk_level="low",
        design_target="project_offerings.duration",
    ),
    FieldSpec(
        name="suitable_audience",
        label_zh="适合人群",
        risk_level="medium",
        design_target="project_match_profiles.suitable_student_directions",
        multi_line=True,
    ),
    FieldSpec(
        name="output_description",
        label_zh="产出描述",
        risk_level="high",
        design_target="project_deliverable_claims.claim_text",
        multi_line=True,
        note="Split into claim_type per design doc section 14.4; promotional text is never a fact.",
    ),
)

FIELD_BY_NAME: dict[str, FieldSpec] = {spec.name: spec for spec in CANONICAL_FIELDS}
FIELD_NAMES: tuple[str, ...] = tuple(spec.name for spec in CANONICAL_FIELDS)


def field_risk(name: str) -> str:
    spec = FIELD_BY_NAME.get(name)
    return spec.risk_level if spec else "high"


def field_label(name: str) -> str:
    spec = FIELD_BY_NAME.get(name)
    return spec.label_zh if spec else name


# --------------------------------------------------------------------------
# Source kinds
# --------------------------------------------------------------------------

SOURCE_KINDS: tuple[str, ...] = ("web_json", "poster_ocr", "handbook_pdf", "table_csv")

SOURCE_KIND_LABELS: dict[str, str] = {
    "web_json": "网页资料",
    "poster_ocr": "课题海报(OCR)",
    "handbook_pdf": "项目手册(PDF)",
    "table_csv": "开课时间表(CSV)",
}

# Extraction confidence vocabulary. This describes how sure the *extractor* is
# that it read the value correctly. It never describes whether the statement
# is true in the world; that is `verification_status` and it is always
# "unverified" until a human reviewer signs off.
EXTRACTION_CONFIDENCE: tuple[str, ...] = ("high", "medium", "low")

# Field state vocabulary produced by the merge stage.
FIELD_STATUSES: tuple[str, ...] = (
    "missing",  # no usable evidence at all
    "resolved",  # all evidence agrees and is factual
    "resolved_with_promotional",  # evidence agrees, but part of it is marketing
    "conflict",  # evidence disagrees; nothing is selected
    "promotional_only",  # only marketing statements; nothing is selected
)


# --------------------------------------------------------------------------
# Runtime settings
# --------------------------------------------------------------------------


@dataclass
class Settings:
    """Runtime configuration. Every knob is explicit, nothing is implicit."""

    output_dir: Path = Path("data/facts")

    # Compliance / network knobs. Only used when a web source is declared by URL.
    user_agent: str = "research-facts/0.1 (internal data package; contact: data-ops@example.com)"
    rate_limit: float = 2.0  # minimum seconds between two requests to one host
    timeout: float = 20.0  # per-request timeout in seconds
    retries: int = 2  # safe retries only: timeout / 429 / selected 5xx

    # Identity / grouping knobs.
    identity_similarity_threshold: float = 0.90
    strict_identity: bool = False  # True = only external_id may group documents

    # Safety rails.
    max_records: int | None = None
    max_continuation_lines: int = 12
    max_continuation_chars: int = 800
    dry_run: bool = False
    verbose: bool = False
    # Force one web source profile instead of auto-detection.
    profile: str | None = None
    # JSON field tables loaded before the run (the real wiring surface).
    profile_files: list[str] = dc_field(default_factory=list)
    # Human review decisions. Defaults to <output-dir>/reviews.json.
    review_file: str | None = None
    # Human identity-merge decisions. Defaults to <output-dir>/merges.json.
    merge_file: str | None = None

    inputs: list[str] = dc_field(default_factory=list)

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        if not self.review_file:
            self.review_file = str(self.reviews_path)
        if not self.merge_file:
            self.merge_file = str(self.merges_path)

    # -- derived paths ----------------------------------------------------
    @property
    def reviews_path(self) -> Path:
        return self.output_dir / "reviews.json"

    @property
    def merges_path(self) -> Path:
        return self.output_dir / "merges.json"

    @property
    def facts_path(self) -> Path:
        return self.output_dir / "facts.jsonl"

    @property
    def evidence_index_path(self) -> Path:
        return self.output_dir / "evidence_index.jsonl"

    @property
    def documents_path(self) -> Path:
        return self.output_dir / "documents.jsonl"

    @property
    def rejected_path(self) -> Path:
        return self.output_dir / "rejected_candidates.jsonl"

    @property
    def manifest_path(self) -> Path:
        return self.output_dir / "run_manifest.json"

    @property
    def missing_report_path(self) -> Path:
        return self.output_dir / "missing_report.json"

    @property
    def conflict_report_path(self) -> Path:
        return self.output_dir / "conflict_report.json"

    @property
    def promotional_report_path(self) -> Path:
        return self.output_dir / "promotional_claims_report.json"

    @property
    def quality_summary_path(self) -> Path:
        return self.output_dir / "quality_summary.json"

    @property
    def duplicates_path(self) -> Path:
        return self.output_dir / "duplicate_candidates.json"

    @property
    def cohorts_path(self) -> Path:
        return self.output_dir / "cohort_groups.json"

    @property
    def public_facts_path(self) -> Path:
        return self.output_dir / "facts.public.jsonl"

    def ensure_output_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def describe(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "rate_limit_seconds": self.rate_limit,
            "timeout_seconds": self.timeout,
            "retries": self.retries,
            "user_agent": self.user_agent,
            "max_records": self.max_records,
            "identity_similarity_threshold": self.identity_similarity_threshold,
            "strict_identity": self.strict_identity,
            "review_file": self.review_file,
            "dry_run": self.dry_run,
        }
