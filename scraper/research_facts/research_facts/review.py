"""Human review decisions.

A machine cannot promote a supplier statement to a verified fact, so that step
needs a person and an audit trail. This module stores the decision, who made
it, and — crucially — *which evidence* they looked at.

The evidence fingerprint is the part that matters. Without it, an approval would
silently keep granting publish rights after the underlying text changed: the
reviewer signed off on "示例导师甲", the page later says someone else, and the
record would still be marked reviewed. A decision whose fingerprint no longer
matches is reported as ``stale`` and is treated as not approved.

Approval also does not unlock a policy boundary. A field containing a
``prohibited_claim`` (a guaranteed outcome) still has that sentence removed from
customer-facing copy after review; see :mod:`research_facts.projections`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Iterable

from .errors import InputError
from .schema import FieldState
from .storage import atomic_write_text
from .utils import now_iso, sha256_text

# ``adjudicated`` is a third verb and answers a different question than the
# other two: ``approved``/``rejected`` judge one value, ``adjudicated`` picks
# between conflicting sources. They are kept in the same file because both are
# human decisions about the same evidence.
DECISIONS: tuple[str, ...] = ("approved", "rejected", "adjudicated")
# Decisions that count as "not approved".
NON_APPROVING: frozenset[str] = frozenset({"rejected", "stale", "pending"})

REVIEW_FILE = "reviews.json"
REVIEW_SCHEMA_VERSION = 1


def evidence_fingerprint(state: FieldState) -> str:
    """Hash of exactly what a reviewer would have been looking at.

    Covers the selected text, every claim's text, and the documents they came
    from. A re-crawl that changes any of these produces a different fingerprint,
    which is exactly when the approval must stop counting.
    """
    payload = {
        "field": state.field,
        "status": state.status,
        "raw_text": state.selected_raw_text or "",
        "claims": sorted(sha256_text(claim.raw_text) for claim in state.claims),
        "documents": sorted({claim.locator.document_id for claim in state.claims}),
    }
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


@dataclass(frozen=True)
class ReviewDecision:
    """One reviewer's verdict on one field of one record."""

    record_key: str
    field: str
    decision: str
    fingerprint: str
    reviewer: str = "unknown"
    reviewed_at: str = dc_field(default_factory=now_iso)
    note: str = ""
    # Adjudication only: which of the competing statements was chosen. This is
    # a *reference* to a value a source actually stated -- an adjudicator picks
    # a side, they do not write a new one. A field with this set to something
    # that no longer exists in the evidence is ignored, which is the whole
    # point of binding it to the fingerprint as well.
    chosen_value: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise InputError(
                f"review decision must be one of {DECISIONS}, got {self.decision!r}"
            )
        if not self.fingerprint:
            raise InputError("review decision needs the evidence fingerprint")

    def key(self) -> tuple[str, str]:
        return (self.record_key, self.field)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_key": self.record_key,
            "field": self.field,
            "decision": self.decision,
            "fingerprint": self.fingerprint,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "note": self.note,
            "chosen_value": self.chosen_value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewDecision":
        return cls(
            record_key=str(payload.get("record_key", "")),
            field=str(payload.get("field", "")),
            decision=str(payload.get("decision", "")),
            fingerprint=str(payload.get("fingerprint", "")),
            reviewer=str(payload.get("reviewer", "unknown")),
            reviewed_at=str(payload.get("reviewed_at", "")) or now_iso(),
            note=str(payload.get("note", "")),
            chosen_value=payload.get("chosen_value"),
        )


@dataclass
class ReviewRegistry:
    """All decisions for a run, keyed by ``(record_key, field)``."""

    decisions: dict[tuple[str, str], ReviewDecision] = dc_field(default_factory=dict)
    path: Path | None = None

    # -- lookup ----------------------------------------------------------
    def get(self, record_key: str, field: str) -> ReviewDecision | None:
        return self.decisions.get((record_key, field))

    def status_for(self, record_key: str, field: str, fingerprint: str) -> str:
        """Return the verdict, or ``stale`` if the evidence it covered has moved."""
        decision = self.get(record_key, field)
        if decision is None:
            return "pending"
        if decision.fingerprint != fingerprint:
            return "stale"
        return decision.decision

    def adjudication_for(self, record_key: str, field: str, fingerprint: str) -> ReviewDecision | None:
        """A live adjudication for this field, or ``None``.

        A stale decision is not returned: it was made about different evidence.
        """
        decision = self.get(record_key, field)
        if decision is None or decision.decision != "adjudicated":
            return None
        if decision.fingerprint != fingerprint or not decision.chosen_value:
            return None
        return decision

    def set(
        self,
        record_key: str,
        field: str,
        decision: str,
        fingerprint: str,
        *,
        reviewer: str = "unknown",
        note: str = "",
        reviewed_at: str | None = None,
        chosen_value: str | None = None,
    ) -> ReviewDecision:
        if decision == "adjudicated" and not chosen_value:
            raise InputError("an adjudication must name the value it chose")
        entry = ReviewDecision(
            record_key=record_key,
            field=field,
            decision=decision,
            fingerprint=fingerprint,
            reviewer=reviewer,
            reviewed_at=reviewed_at or now_iso(),
            note=note,
            chosen_value=chosen_value,
        )
        self.decisions[entry.key()] = entry
        return entry

    def reset(self, record_key: str, field: str) -> bool:
        return self.decisions.pop((record_key, field), None) is not None

    # -- summary ---------------------------------------------------------
    def counts(self) -> dict[str, int]:
        """Stored decisions by verdict.

        ``stale`` is not counted here: staleness depends on the *current*
        evidence fingerprint, so it is resolved by :meth:`status_for` where the
        records are available.
        """
        summary = {status: 0 for status in DECISIONS}
        for decision in self.decisions.values():
            summary[decision.decision] = summary.get(decision.decision, 0) + 1
        return summary

    def rows(self) -> list[dict[str, Any]]:
        return [self.decisions[key].to_dict() for key in sorted(self.decisions)]

    # -- persistence -----------------------------------------------------
    def to_payload(self) -> dict[str, Any]:
        return {
            "version": REVIEW_SCHEMA_VERSION,
            "rule": "审核只覆盖 fingerprint 指定的那一份证据；证据变了即为 stale，需重新审核。"
            "审核不解除政策边界：prohibited_claim 的句子在任何情况下都不会进入对外文案。",
            "decisions": self.rows(),
        }

    def save(self, path: Path | None = None) -> Path:
        target = Path(path or self.path or REVIEW_FILE)
        atomic_write_text(target, json.dumps(self.to_payload(), ensure_ascii=False, indent=2) + "\n")
        self.path = target
        return target

    @classmethod
    def load(cls, path: Path | str) -> "ReviewRegistry":
        target = Path(path)
        if not target.exists():
            return cls(path=target)
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InputError(f"{target} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise InputError(f"{target} must be a JSON object")
        registry = cls(path=target)
        for item in payload.get("decisions", []):
            if not isinstance(item, dict):
                raise InputError(f"{target}: each decision must be an object")
            entry = ReviewDecision.from_dict(item)
            registry.decisions[entry.key()] = entry
        return registry

    @classmethod
    def load_many(cls, paths: Iterable[Path | str]) -> "ReviewRegistry":
        merged = cls()
        for path in paths:
            other = cls.load(path)
            merged.decisions.update(other.decisions)
            merged.path = merged.path or other.path
        return merged
