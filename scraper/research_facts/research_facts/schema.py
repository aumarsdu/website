"""Canonical data structures: locator, field claim, field state, fact record.

The central idea is a three-level separation:

``Locator``
    *Where* a statement was read. Always present, even when the value is junk.

``FieldClaim``
    *What* one source document said about one field: the original text, the
    normalized form, how it was extracted, and whether it reads as a marketing
    statement. Claims are never deleted; conflicts keep every side.

``FieldState``
    What the merged evidence supports: missing, resolved, conflicted, or
    promotional-only. Only ``resolved`` states carry a selected value.

A field with no evidence has ``value = None``. Nothing in this module can turn
"not stated" into a value.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable

from .config import (
    EXTRACTION_CONFIDENCE,
    FIELD_BY_NAME,
    FIELD_NAMES,
    FIELD_STATUSES,
    field_risk,
)
from .errors import SchemaValidationError
from .utils import comparison_key

# Verbatim text of the statement inside the source document.
EVIDENCE_KINDS: tuple[str, ...] = ("factual", "conditional_claim", "prohibited_claim")

# Mirrors design doc section 14.4 (project_deliverable_claims.claim_type).
DELIVERABLE_CLAIM_TYPES: tuple[str, ...] = ("guaranteed", "conditional", "prohibited")

VERIFICATION_STATUS = "unverified"  # only a human review can change this


@dataclass(frozen=True)
class Locator:
    """Address of one statement inside one source document."""

    kind: str  # "json_path" | "text_line" | "text_row"
    document_id: str
    pointer: str  # "$.raw.cycle" | "p3#line7" | "row#2"
    detail: str = ""  # "page=3 bbox=(40,210,610,58)"
    excerpt: str = ""  # short verbatim surroundings

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "document_id": self.document_id,
            "pointer": self.pointer,
            "detail": self.detail,
            "excerpt": self.excerpt,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Locator":
        return cls(
            kind=str(payload.get("kind", "json_path")),
            document_id=str(payload.get("document_id", "")),
            pointer=str(payload.get("pointer", "")),
            detail=str(payload.get("detail", "")),
            excerpt=str(payload.get("excerpt", "")),
        )


@dataclass(frozen=True)
class RejectedCandidate:
    """A label match that was refused instead of becoming a claim.

    Refusals are recorded, not dropped. When a poster's header row reads
    ``项目周期 | 开班人数``, the value cannot be a duration -- but a human
    reviewing the template still needs to see that the row was noticed and why
    it produced nothing. Silence would be indistinguishable from a bug.
    """

    field: str
    candidate_text: str
    locator: Locator
    extractor: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "candidate_text": self.candidate_text,
            "locator": self.locator.to_dict(),
            "extractor": self.extractor,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FieldClaim:
    """One statement about one field, from one place in one document."""

    field: str
    raw_text: str
    locator: Locator
    extractor: str
    extraction_method: str
    extraction_confidence: str
    evidence_kind: str = "factual"
    deliverable_claim_type: str | None = None
    normalized_value: str | None = None
    normalization: dict[str, Any] | None = None
    risk_level: str | None = None
    verification_status: str = VERIFICATION_STATUS
    # True when the statement also contains plain, non-promotional sentences.
    has_factual_content: bool = True
    matched_phrases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.field:
            raise SchemaValidationError("FieldClaim.field is required")
        if not self.raw_text.strip():
            # An empty statement is not evidence. Callers must drop it.
            raise SchemaValidationError("FieldClaim.raw_text must not be empty")
        if self.extraction_confidence not in EXTRACTION_CONFIDENCE:
            raise SchemaValidationError(
                f"invalid extraction_confidence: {self.extraction_confidence!r}"
            )
        if self.evidence_kind not in EVIDENCE_KINDS:
            raise SchemaValidationError(f"invalid evidence_kind: {self.evidence_kind!r}")
        if self.deliverable_claim_type not in (None, *DELIVERABLE_CLAIM_TYPES):
            raise SchemaValidationError(
                f"invalid deliverable_claim_type: {self.deliverable_claim_type!r}"
            )

    @property
    def risk(self) -> str:
        return self.risk_level or field_risk(self.field)

    @property
    def is_promotional(self) -> bool:
        return self.evidence_kind != "factual"

    @property
    def has_factual_evidence(self) -> bool:
        """True when repeating this claim as a stated fact is defensible."""
        return self.evidence_kind == "factual" or self.has_factual_content

    @property
    def compare_value(self) -> str:
        """Value used to decide whether two claims agree.

        Prefers the normalized form so ``2027-01-08`` and ``2027年1月8日`` are
        recognised as the same date rather than reported as a conflict, and so
        an order-insensitive key keeps ``航空、遥感`` from conflicting with
        ``遥感、航空``.
        """
        if self.normalization:
            override = self.normalization.get("compare_key")
            if override:
                return str(override)
        if self.normalized_value:
            return comparison_key(self.normalized_value)
        return comparison_key(self.raw_text)

    @property
    def compare_items(self) -> frozenset[str]:
        """Item-level set used by fields whose conflict policy allows subsets."""
        if self.normalization:
            items = self.normalization.get("items")
            if isinstance(items, list) and items:
                return frozenset(comparison_key(str(item)) for item in items if str(item).strip())
        return frozenset()

    @property
    def dedupe_key(self) -> tuple[str, str, str, str]:
        return (self.field, self.locator.document_id, self.locator.pointer, self.raw_text)

    @property
    def sort_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.field,
            self.locator.document_id,
            self.locator.pointer,
            self.evidence_kind,
            self.normalized_value or "",
            self.raw_text,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "field_label": FIELD_BY_NAME[self.field].label_zh if self.field in FIELD_BY_NAME else self.field,
            "raw_text": self.raw_text,
            "normalized_value": self.normalized_value,
            "normalization": self.normalization,
            "locator": self.locator.to_dict(),
            "extractor": self.extractor,
            "extraction_method": self.extraction_method,
            "extraction_confidence": self.extraction_confidence,
            "evidence_kind": self.evidence_kind,
            "deliverable_claim_type": self.deliverable_claim_type,
            "matched_phrases": list(self.matched_phrases),
            "has_factual_content": self.has_factual_content,
            "risk_level": self.risk,
            "verification_status": self.verification_status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FieldClaim":
        return cls(
            field=str(payload.get("field", "")),
            raw_text=str(payload.get("raw_text", "")),
            locator=Locator.from_dict(payload.get("locator") or {}),
            extractor=str(payload.get("extractor", "")),
            extraction_method=str(payload.get("extraction_method", "")),
            extraction_confidence=str(payload.get("extraction_confidence", "low")),
            evidence_kind=str(payload.get("evidence_kind", "factual")),
            deliverable_claim_type=payload.get("deliverable_claim_type"),
            normalized_value=payload.get("normalized_value"),
            normalization=payload.get("normalization"),
            risk_level=payload.get("risk_level"),
            verification_status=str(payload.get("verification_status", VERIFICATION_STATUS)),
            has_factual_content=bool(payload.get("has_factual_content", True)),
            matched_phrases=tuple(payload.get("matched_phrases", ())),
        )


def claim_display_value(claim: FieldClaim) -> str:
    """The value a person reads and quotes: normalized if there is one."""
    return claim.normalized_value or claim.raw_text


@dataclass
class FieldState:
    """Merged evidence for one canonical field on one project."""

    field: str
    status: str
    claims: list[FieldClaim] = dc_field(default_factory=list)
    selected_raw_text: str | None = None
    selected_normalized_value: str | None = None
    selected_claim: FieldClaim | None = None
    conflict_values: list[str] = dc_field(default_factory=list)
    note: str = ""
    # How the status was reached, when a human was involved. Deliberately not a
    # status: adding one would change the arithmetic in every report, and the
    # reports are the part downstream people already rely on.
    resolution: str | None = None  # None | "human_adjudication"

    @property
    def is_usable(self) -> bool:
        """True only when a value may be used as a stated fact downstream."""
        return self.status in ("resolved", "resolved_with_promotional")

    @property
    def risk_level(self) -> str:
        return field_risk(self.field)

    @property
    def has_promotional_evidence(self) -> bool:
        return any(claim.is_promotional for claim in self.claims)

    def to_dict(self, include_claims: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "field": self.field,
            "field_label": FIELD_BY_NAME[self.field].label_zh if self.field in FIELD_BY_NAME else self.field,
            "status": self.status,
            "risk_level": self.risk_level,
            "claim_count": len(self.claims),
            "distinct_value_count": len({claim.compare_value for claim in self.claims}),
            "has_promotional_evidence": self.has_promotional_evidence,
            "value": self.selected_normalized_value,
            "raw_text": self.selected_raw_text,
            "verification_status": VERIFICATION_STATUS,
            "conflict_values": list(self.conflict_values),
            "resolution": self.resolution,
            "note": self.note,
        }
        if include_claims:
            payload["claims"] = [claim.to_dict() for claim in self.claims]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FieldState":
        return cls(
            field=str(payload.get("field", "")),
            status=str(payload.get("status", "missing")),
            claims=[FieldClaim.from_dict(item) for item in payload.get("claims", [])],
            selected_raw_text=payload.get("raw_text"),
            selected_normalized_value=payload.get("value"),
            conflict_values=list(payload.get("conflict_values", [])),
            note=str(payload.get("note", "")),
            resolution=payload.get("resolution"),
        )


@dataclass(frozen=True)
class Identity:
    """How documents were grouped into one project record."""

    provider: str
    external_id: str | None = None
    title_hint: str | None = None
    basis: str = "external_id"  # "external_id" | "title" | "title_similarity" | "unresolved"
    similarity_score: float | None = None
    review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "external_id": self.external_id,
            "title_hint": self.title_hint,
            "basis": self.basis,
            "similarity_score": self.similarity_score,
            "review_required": self.review_required,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Identity":
        return cls(
            provider=str(payload.get("provider", "")),
            external_id=payload.get("external_id"),
            title_hint=payload.get("title_hint"),
            basis=str(payload.get("basis", "unresolved")),
            similarity_score=payload.get("similarity_score"),
            review_required=bool(payload.get("review_required", False)),
        )


@dataclass
class ProjectFactRecord:
    """All evidence collected for one project, across every source kind."""

    record_key: str
    identity: Identity
    document_ids: list[str] = dc_field(default_factory=list)
    fields: dict[str, FieldState] = dc_field(default_factory=dict)
    links: list[dict[str, Any]] = dc_field(default_factory=list)
    issues: list[dict[str, Any]] = dc_field(default_factory=list)

    def validate(self) -> None:
        if not self.record_key:
            raise SchemaValidationError("ProjectFactRecord.record_key is required")
        if not self.identity.provider:
            raise SchemaValidationError("identity.provider is required")
        for name, state in self.fields.items():
            if name not in FIELD_NAMES:
                raise SchemaValidationError(f"unknown canonical field in record: {name!r}")
            if state.status not in FIELD_STATUSES:
                raise SchemaValidationError(f"invalid field status: {state.status!r}")
            # A value may only exist when the evidence supports using it.
            if state.selected_normalized_value is not None and not state.is_usable:
                raise SchemaValidationError(
                    f"field {name!r} has status {state.status!r} but carries a selected value"
                )
            if state.status == "missing" and state.claims:
                raise SchemaValidationError(f"field {name!r} is missing but has claims")

    @property
    def usable_fields(self) -> list[str]:
        return [name for name in FIELD_NAMES if self.fields.get(name) and self.fields[name].is_usable]

    def to_dict(self, include_claims: bool = True) -> dict[str, Any]:
        self.validate()
        return {
            "record_key": self.record_key,
            "identity": self.identity.to_dict(),
            "document_ids": list(self.document_ids),
            "fields": {
                name: self.fields[name].to_dict(include_claims=include_claims)
                for name in FIELD_NAMES
                if name in self.fields
            },
            "links": list(self.links),
            "issues": list(self.issues),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectFactRecord":
        fields = {
            name: FieldState.from_dict(value)
            for name, value in (payload.get("fields") or {}).items()
        }
        return cls(
            record_key=str(payload.get("record_key", "")),
            identity=Identity.from_dict(payload.get("identity") or {}),
            document_ids=list(payload.get("document_ids", [])),
            fields=fields,
            links=list(payload.get("links", [])),
            issues=list(payload.get("issues", [])),
        )


def sort_records(records: Iterable[ProjectFactRecord]) -> list[ProjectFactRecord]:
    """Deterministic ordering so repeated imports produce identical output."""
    return sorted(records, key=lambda record: record.record_key)


def sort_claims(claims: Iterable[FieldClaim]) -> list[FieldClaim]:
    return sorted(claims, key=lambda claim: claim.sort_key)


def dedupe_claims(claims: Iterable[FieldClaim]) -> list[FieldClaim]:
    """Drop exact repeats of the same statement from the same place."""
    seen: set[tuple[str, str, str, str]] = set()
    result: list[FieldClaim] = []
    for claim in sort_claims(claims):
        if claim.dedupe_key in seen:
            continue
        seen.add(claim.dedupe_key)
        result.append(claim)
    return result
