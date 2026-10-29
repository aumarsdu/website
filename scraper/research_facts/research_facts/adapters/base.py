"""Adapter contract shared by every input kind.

An adapter turns one input file into a list of :class:`AdapterOutput`. It reads
a source, extracts claims with locators, and nothing else. Merging, conflict
detection, and reporting happen downstream, so a new source kind never needs to
touch the merge rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..config import Settings
from ..schema import FieldClaim, RejectedCandidate
from ..utils import file_digest

# How much a source is trusted *as an origin*, independent of what a sentence
# says. Recorded on every document and surfaced in the promotional report.
SOURCE_AUTHORITIES: tuple[str, ...] = (
    "supplier_marketing",  # poster, landing page, sales sheet
    "supplier_official",  # partner API / official notice
    "internal_note",  # our own ops note
    "unknown",
)


@dataclass(frozen=True)
class SourceDocument:
    """One source artifact that claims to be about one project."""

    document_id: str
    source_kind: str
    provider: str
    origin: str
    origin_sha256: str
    external_id: str | None = None
    title_hint: str | None = None
    source_authority: str = "unknown"
    meta: dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_kind": self.source_kind,
            "source_authority": self.source_authority,
            "provider": self.provider,
            "external_id": self.external_id,
            "title_hint": self.title_hint,
            "origin": self.origin,
            "origin_sha256": self.origin_sha256,
            "meta": self.meta,
        }


@dataclass
class AdapterOutput:
    """What one adapter produced for one source document."""

    document: SourceDocument
    claims: list[FieldClaim] = dc_field(default_factory=list)
    stats: dict[str, Any] = dc_field(default_factory=dict)
    unmapped_source_keys: list[str] = dc_field(default_factory=list)
    # Label matches that were refused, kept for audit: a template review needs
    # to see what was noticed and why it produced no value.
    rejected: list[RejectedCandidate] = dc_field(default_factory=list)


@runtime_checkable
class Adapter(Protocol):
    name: str
    source_kind: str
    accepts: tuple[str, ...]

    def load(self, path: Path, settings: Settings) -> list[AdapterOutput]:
        ...


def make_document(
    *,
    document_id: str,
    source_kind: str,
    provider: str,
    origin: str,
    external_id: str | None = None,
    title_hint: str | None = None,
    source_authority: str = "unknown",
    meta: dict[str, Any] | None = None,
) -> SourceDocument:
    if not document_id:
        raise ValueError("document_id is required")
    if source_authority not in SOURCE_AUTHORITIES:
        raise ValueError(f"unknown source_authority: {source_authority!r}")
    return SourceDocument(
        document_id=document_id,
        source_kind=source_kind,
        provider=provider,
        origin=origin,
        origin_sha256=file_digest(Path(origin)) if Path(origin).exists() else "",
        external_id=external_id,
        title_hint=title_hint,
        source_authority=source_authority,
        meta=dict(meta or {}),
    )
