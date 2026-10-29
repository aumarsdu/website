"""Evidence index and quality reports.

Four outputs, each answering one question a writer, a designer, or an operator
actually asks:

``evidence_index.jsonl``
    "Where did this sentence come from?" -- one row per claim, with document,
    source kind, authority, locator, and a hash of the verbatim text.

``missing_report.json``
    "What do we not know yet?" -- per field, which records have no evidence.

``conflict_report.json``
    "What do our sources disagree about?" -- every competing value with both
    sides' locators. Nothing is resolved here on purpose.

``promotional_claims_report.json``
    "What is marketing copy?" -- every claim carrying a promise, with the
    disclaimer it would need.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from .claims import DISCLAIMERS, deliverable_claim_type
from .config import FIELD_NAMES, FIELD_STATUSES, SOURCE_KIND_LABELS, field_label, field_risk
from .schema import FieldClaim, ProjectFactRecord, claim_display_value
from .utils import sha256_text


# --------------------------------------------------------------------------
# Evidence index
# --------------------------------------------------------------------------


def build_evidence_index(records: Sequence[ProjectFactRecord]) -> list[dict[str, Any]]:
    """One flat row per claim, sorted so the file diffs cleanly between runs."""
    rows: list[dict[str, Any]] = []
    for record in records:
        for name in FIELD_NAMES:
            state = record.fields.get(name)
            if not state:
                continue
            for claim in state.claims:
                rows.append(
                    {
                        "record_key": record.record_key,
                        "provider": record.identity.provider,
                        "external_id": record.identity.external_id,
                        "field": name,
                        "field_label": field_label(name),
                        "risk_level": claim.risk,
                        "field_status": state.status,
                        "document_id": claim.locator.document_id,
                        "locator_kind": claim.locator.kind,
                        "locator": claim.locator.pointer,
                        "locator_detail": claim.locator.detail,
                        "raw_text_sha256": sha256_text(claim.raw_text),
                        "raw_text": claim.raw_text,
                        "normalized_value": claim.normalized_value,
                        "extractor": claim.extractor,
                        "extraction_method": claim.extraction_method,
                        "extraction_confidence": claim.extraction_confidence,
                        "evidence_kind": claim.evidence_kind,
                        "deliverable_claim_type": claim.deliverable_claim_type,
                        "matched_phrases": list(claim.matched_phrases),
                        "verification_status": claim.verification_status,
                    }
                )
    rows.sort(
        key=lambda row: (
            row["record_key"],
            row["field"],
            row["document_id"],
            row["locator"],
            row["raw_text_sha256"],
        )
    )
    return rows


# --------------------------------------------------------------------------
# Missing
# --------------------------------------------------------------------------


def build_missing_report(records: Sequence[ProjectFactRecord]) -> dict[str, Any]:
    total = len(records)
    by_field: dict[str, Any] = {}
    not_usable: dict[str, Any] = {}
    for name in FIELD_NAMES:
        missing = [
            record.record_key
            for record in records
            if record.fields.get(name) and record.fields[name].status == "missing"
        ]
        blocked: dict[str, int] = {}
        blocked_keys: dict[str, list[str]] = {}
        for record in records:
            state = record.fields.get(name)
            if not state or state.is_usable:
                continue
            blocked[state.status] = blocked.get(state.status, 0) + 1
            blocked_keys.setdefault(state.status, []).append(record.record_key)
        by_field[name] = {
            "field_label": field_label(name),
            "risk_level": field_risk(name),
            "missing_count": len(missing),
            "coverage_rate": round(1 - (len(missing) / total), 4) if total else 0.0,
            "record_keys": sorted(missing),
        }
        not_usable[name] = {
            "field_label": field_label(name),
            "not_usable_count": sum(blocked.values()),
            "by_status": dict(sorted(blocked.items())),
            "record_keys": {status: sorted(keys) for status, keys in sorted(blocked_keys.items())},
        }
    all_missing = sorted(
        record.record_key for record in records if not record.usable_fields
    )
    return {
        "total_records": total,
        "rule": "未在任何来源中出现的字段一律留空，不做推断补写；"
        "存在但不可用（冲突 / 仅宣传）的字段单独列出，不计入缺失也不计入可用。",
        "by_field": by_field,
        "not_usable_by_field": not_usable,
        "records_without_any_usable_field": all_missing,
    }


# --------------------------------------------------------------------------
# Conflicts
# --------------------------------------------------------------------------


def build_conflict_report(records: Sequence[ProjectFactRecord]) -> dict[str, Any]:
    conflicts: list[dict[str, Any]] = []
    for record in records:
        for name in FIELD_NAMES:
            state = record.fields.get(name)
            if not state or state.status != "conflict":
                continue
            values: list[dict[str, Any]] = []
            # Group by comparison key so equivalent wordings are one side.
            groups: dict[str, list[FieldClaim]] = {}
            for claim in state.claims:
                groups.setdefault(claim.compare_value, []).append(claim)
            for key in sorted(groups):
                sides = [
                    {
                        "document_id": claim.locator.document_id,
                        "locator": claim.locator.pointer,
                        "locator_detail": claim.locator.detail,
                        "raw_text": claim.raw_text,
                        "normalized_value": claim.normalized_value,
                        "extraction_confidence": claim.extraction_confidence,
                        "extraction_method": claim.extraction_method,
                        "evidence_kind": claim.evidence_kind,
                    }
                    for claim in groups[key]
                ]
                representative = groups[key][0]
                values.append(
                    {
                        "value": claim_display_value(representative),
                        "sides": sides,
                    }
                )
            conflicts.append(
                {
                    "record_key": record.record_key,
                    "identity": record.identity.to_dict(),
                    "field": name,
                    "field_label": field_label(name),
                    "risk_level": field_risk(name),
                    "document_count": len(record.document_ids),
                    "values": values,
                    "resolution": "manual_review_required",
                }
            )
    by_field: dict[str, int] = {}
    for item in conflicts:
        by_field[item["field"]] = by_field.get(item["field"], 0) + 1
    return {
        "total_conflicts": len(conflicts),
        "by_field": dict(sorted(by_field.items())),
        "rule": "冲突不做自动裁决，双方证据全部保留，等待人工确认。",
        "conflicts": conflicts,
    }


# --------------------------------------------------------------------------
# Promotional claims
# --------------------------------------------------------------------------


def build_promotional_report(
    records: Sequence[ProjectFactRecord], documents: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    by_kind: dict[str, int] = {}
    promotional_only: list[dict[str, Any]] = []
    for record in records:
        for name in FIELD_NAMES:
            state = record.fields.get(name)
            if not state:
                continue
            if state.status == "promotional_only":
                promotional_only.append(
                    {
                        "record_key": record.record_key,
                        "field": name,
                        "field_label": field_label(name),
                        "claim_count": len(state.claims),
                    }
                )
            for claim in state.claims:
                if not claim.is_promotional:
                    continue
                kind = claim.evidence_kind
                by_kind[kind] = by_kind.get(kind, 0) + 1
                items.append(
                    {
                        "record_key": record.record_key,
                        "field": name,
                        "field_label": field_label(name),
                        "evidence_kind": kind,
                        "deliverable_claim_type": deliverable_claim_type(kind),
                        "matched_phrases": list(claim.matched_phrases),
                        "required_disclaimer": DISCLAIMERS.get(kind),
                        "document_id": claim.locator.document_id,
                        "locator": claim.locator.pointer,
                        "text": claim.raw_text,
                        "has_factual_content": claim.has_factual_content,
                    }
                )
    items.sort(key=lambda item: (item["record_key"], item["field"], item["locator"], item["text"]))
    marketing_docs = [
        {
            "document_id": doc["document_id"],
            "provider": doc["provider"],
            "source_kind": doc["source_kind"],
            "source_authority": doc["source_authority"],
        }
        for doc in sorted(documents, key=lambda item: item["document_id"])
        if doc.get("source_authority") == "supplier_marketing"
    ]
    return {
        "total": len(items),
        "by_kind": dict(sorted(by_kind.items())),
        "fields_with_promotional_only": promotional_only,
        "marketing_source_documents": marketing_docs,
        "rule": "供应商宣传表述一律标记为未核验，不得自动当作已证实事实；"
        "conditional 需附条件与免责声明，prohibited 不得进入销售与对外文案。",
        "claims": items,
    }


# --------------------------------------------------------------------------
# Quality summary
# --------------------------------------------------------------------------


def build_quality_summary(
    *,
    records: Sequence[ProjectFactRecord],
    documents: Sequence[dict[str, Any]],
    settings_payload: dict[str, Any],
    inputs: Sequence[dict[str, Any]],
    errors: dict[str, int],
    content_digest: str,
) -> dict[str, Any]:
    total = len(records)
    field_coverage: dict[str, Any] = {}
    for name in FIELD_NAMES:
        statuses = {status: 0 for status in FIELD_STATUSES}
        for record in records:
            state = record.fields.get(name)
            if state:
                statuses[state.status] = statuses.get(state.status, 0) + 1
        resolved = statuses["resolved"] + statuses["resolved_with_promotional"]
        field_coverage[name] = {
            "field_label": field_label(name),
            "risk_level": field_risk(name),
            "status_counts": statuses,
            "usable": resolved,
            "coverage_rate": round(resolved / total, 4) if total else 0.0,
        }

    by_source_kind: dict[str, dict[str, int]] = {}
    for doc in documents:
        kind = doc["source_kind"]
        bucket = by_source_kind.setdefault(kind, {"documents": 0, "with_external_id": 0})
        bucket["label"] = SOURCE_KIND_LABELS.get(kind, kind)  # type: ignore[assignment]
        bucket["documents"] += 1
        if doc.get("external_id"):
            bucket["with_external_id"] += 1

    claim_count = sum(
        len(state.claims)
        for record in records
        for state in record.fields.values()
    )
    usable = sum(1 for record in records if record.usable_fields)

    issue_counts: dict[str, int] = {}
    for record in records:
        for issue in record.issues:
            issue_counts[issue["type"]] = issue_counts.get(issue["type"], 0) + 1

    return {
        "run": settings_payload,
        "inputs": list(inputs),
        "counts": {
            "documents": len(documents),
            "records": total,
            "claims": claim_count,
            "records_with_usable_fields": usable,
        },
        "field_coverage": field_coverage,
        "documents_by_source_kind": dict(sorted(by_source_kind.items())),
        "unmapped_source_keys": dict(index_unmapped_records(documents)),
        "record_issues": dict(sorted(issue_counts.items())),
        "errors": dict(sorted(errors.items())),
        "content_digest": content_digest,
        "known_limits": [
            "仅覆盖六个规范字段；来源中的其余字段不映射、不猜测。",
            "开场时间的开课/截止等口径差异未建模，遇到口径不明时保留原文并标记冲突。",
            "未包含人工审核流程，verification_status 一律为 unverified。",
        ],
    }


def index_unmapped_records(documents: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Unmapped source keys, counted across documents.

    This is the punch list for wiring a real field table: a key that no profile
    path consumed is either irrelevant or a mapping that is still missing.
    """
    counts: dict[str, int] = {}
    for doc in documents:
        for key in (doc.get("meta") or {}).get("unmapped_source_keys", []) or []:
            counts[str(key)] = counts.get(str(key), 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def build_rejected_report(outputs: Sequence[Any]) -> list[dict[str, Any]]:
    """Label matches that were refused, grouped by reason.

    A refused match is not a claim and must never become one, but it is the
    most useful signal available when a new poster template is wired up: it
    shows which label words the layout produced and why each produced nothing.
    """
    rows: list[dict[str, Any]] = []
    for output in outputs:
        for item in getattr(output, "rejected", []) or []:
            payload = item.to_dict()
            payload["document_id"] = output.document.document_id
            payload["source_kind"] = output.document.source_kind
            rows.append(payload)
    rows.sort(
        key=lambda row: (
            row["source_kind"],
            row["document_id"],
            row["field"],
            row["locator"]["pointer"],
            row["candidate_text"],
        )
    )
    return rows


__all__ = [
    "build_conflict_report",
    "build_rejected_report",
    "build_evidence_index",
    "build_missing_report",
    "build_promotional_report",
    "build_quality_summary",
    "index_unmapped_records",
]
