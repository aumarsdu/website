"""Customer-facing projection.

This module is the only place that decides what may leave the internal data
set. It encodes four rules from the design doc's publication gates:

1. High-risk fields (导师, 产出描述) cannot appear in a public record before a
   human review. They are emitted as a separate review queue instead, with the
   marketing parts already filtered out, so a reviewer can approve quickly.
2. A human approval unlocks *field eligibility only*. It never removes a policy
   boundary: a ``prohibited_claim`` sentence stays out of customer-facing copy
   whether or not someone signed off on the field.
3. Supplier promises are stripped from every value that does go out, and a
   field left empty by that filter is dropped rather than published blank.
4. A record is only ``publishable`` when the gates we can actually evaluate
   pass. Gates that need data this package does not collect are reported as
   ``not_evaluated`` rather than silently assumed.
"""

from __future__ import annotations

from typing import Any, Sequence

from .claims import keep_factual_only
from .config import FIELD_NAMES, field_label, field_risk
from .review import ReviewRegistry, evidence_fingerprint
from .schema import ProjectFactRecord
from .utils import truncate

# Fields whose public use is gated on review (design doc section 8.2).
REVIEW_GATED_FIELDS: tuple[str, ...] = ("instructor", "output_description")

REQUIRED_FIELD = "project_title"
REQUIRED_ONE_OF: tuple[tuple[str, ...], ...] = (("start_date", "duration"),)

# Gates from design doc section 8.5 that this six-field package cannot judge.
OUT_OF_SCOPE_GATES: tuple[str, ...] = (
    "project_type_present",
    "discipline_present",
    "provider_approved_instructor_fallback",
    "asset_rights_approved",
    "offering_validity",
    "price_policy",
    "data_freshness_window",
    "takedown_status",
)


def build_public_rows(
    records: Sequence[ProjectFactRecord],
    reviews: ReviewRegistry | None = None,
    cohorts: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = reviews or ReviewRegistry()
    cohort_map = cohorts or {}
    rows: list[dict[str, Any]] = []
    withheld_total = 0
    filtered_total = 0
    dropped_by_field: dict[str, int] = {}
    approved_total = 0
    stale_total = 0
    rejected_total = 0

    for record in records:
        display: dict[str, Any] = {}
        review_queue: list[dict[str, Any]] = []
        filtered_segments = 0
        record_dropped: list[str] = []

        for name in FIELD_NAMES:
            state = record.fields.get(name)
            if not state or not state.is_usable or state.selected_raw_text is None:
                continue
            factual_text, withheld = keep_factual_only(state.selected_raw_text)
            filtered_segments += len(withheld)
            if not factual_text:
                # Everything in this field was marketing. Publishing an empty
                # string or the raw promise would be worse than publishing
                # nothing, so the field is dropped and counted.
                record_dropped.append(name)
                dropped_by_field[name] = dropped_by_field.get(name, 0) + 1
                continue
            entry = {
                "value": state.selected_normalized_value,
                "text": factual_text,
                "status": state.status,
                "risk_level": state.risk_level,
                "verification_status": "unverified",
                "attribution": "supplier_statement",
                "evidence_documents": sorted(
                    {claim.locator.document_id for claim in state.claims}
                ),
            }
            if withheld:
                entry["marketing_segments_withheld"] = len(withheld)

            if name in REVIEW_GATED_FIELDS:
                fingerprint = evidence_fingerprint(state)
                decision = registry.get(record.record_key, name)
                review_status = registry.status_for(record.record_key, name, fingerprint)
                review_item = {
                    "field": name,
                    "field_label": field_label(name),
                    "risk_level": field_risk(name),
                    "reason": "high_risk_field_requires_human_review",
                    "review_status": review_status,
                    "evidence_fingerprint": fingerprint,
                    "draft_text": factual_text,
                    "draft_value": state.selected_normalized_value,
                    "marketing_segments_withheld": len(withheld),
                    "evidence_documents": entry["evidence_documents"],
                }
                if decision is not None:
                    review_item["reviewer"] = decision.reviewer
                    review_item["reviewed_at"] = decision.reviewed_at
                    review_item["review_note"] = decision.note

                if review_status == "approved":
                    approved_total += 1
                    # Approval clears the *review* gate only. The text above is
                    # already marketing-filtered, and a prohibited sentence
                    # never reappears here.
                    entry["verification_status"] = "reviewed"
                    entry["attribution"] = "supplier_statement_reviewed"
                    entry["review"] = {
                        "status": "approved",
                        "reviewer": decision.reviewer if decision else "unknown",
                        "reviewed_at": decision.reviewed_at if decision else None,
                        "evidence_fingerprint": fingerprint,
                    }
                    display[name] = entry
                else:
                    if review_status == "stale":
                        stale_total += 1
                        review_item["reason"] = "evidence_changed_since_approval"
                    elif review_status == "rejected":
                        rejected_total += 1
                        review_item["reason"] = "review_rejected"
                    review_queue.append(review_item)
                continue
            display[name] = entry

        gates = _evaluate_gates(record, display, review_queue)
        if record_dropped:
            gates.append(
                {
                    "gate": "no_purely_promotional_field_in_display",
                    "evaluated": True,
                    "passed": False,
                    "detail": f"过滤后为空的字段已移除：{'、'.join(record_dropped)}",
                }
            )
        data_gates = [gate for gate in gates if gate["evaluated"] and gate["gate"] != "high_risk_review_done"]
        withheld_total += len(review_queue)
        filtered_total += filtered_segments
        rows.append(
            {
                "record_key": record.record_key,
                "identity": record.identity.to_dict(),
                # ready_for_review: the data a reviewer needs is present and
                # consistent. publishable: also reviewed, and no gate fails.
                "ready_for_review": all(gate["passed"] for gate in data_gates),
                "publishable": all(gate["passed"] for gate in gates if gate["evaluated"]),
                "display": display,
                # Carried on the row rather than in display: a cohort is context
                # about the record, not a field the customer asked about.
                "cohort": cohort_map.get(record.record_key),
                "dropped_purely_promotional_fields": record_dropped,
                "review_queue": review_queue,
                "gates": gates,
                "notice": "对外字段均为供应商陈述；经人工审核的字段标记为 reviewed，"
                "未审核的仍为 unverified。审核不解除宣传话术的政策边界。",
            }
        )

    rows.sort(key=lambda row: row["record_key"])
    withheld_fields: dict[str, int] = {}
    for row in rows:
        for item in row["review_queue"]:
            key = f"{item['field_label']}({item['field']})"
            withheld_fields[key] = withheld_fields.get(key, 0) + 1

    summary = {
        "records": len(rows),
        "ready_for_review": sum(1 for row in rows if row["ready_for_review"]),
        "publishable": sum(1 for row in rows if row["publishable"]),
        "review_queue_items": withheld_total,
        "review_queue_by_field": dict(sorted(withheld_fields.items())),
        "approved_fields": approved_total,
        "stale_approvals": stale_total,
        "rejected_fields": rejected_total,
        "marketing_segments_filtered": filtered_total,
        "fields_dropped_as_purely_promotional": dict(sorted(dropped_by_field.items())),
        "out_of_scope_gates": list(OUT_OF_SCOPE_GATES),
        "rule": "高风险字段需人工审核后才进入对外字段；宣传表述在任何情况下都不进入对外文案；"
        "证据变化会使既有审核失效（stale）。",
    }
    return rows, summary


def _evaluate_gates(
    record: ProjectFactRecord,
    display: dict[str, Any],
    review_queue: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []

    title_state = record.fields.get(REQUIRED_FIELD)
    title_ok = bool(title_state and title_state.is_usable and title_state.selected_raw_text)
    gates.append(
        {
            "gate": "source_traceability",
            "evaluated": True,
            "passed": bool(record.document_ids),
            "detail": f"{len(record.document_ids)} 份来源文档",
        }
    )
    gates.append(
        {
            "gate": "required_display_title",
            "evaluated": True,
            "passed": title_ok,
            "detail": f"课题名状态 = {title_state.status if title_state else 'missing'}",
        }
    )
    offering = [
        name
        for name in ("start_date", "duration")
        if display.get(name, {}).get("value")
    ]
    gates.append(
        {
            "gate": "duration_or_start_date",
            "evaluated": True,
            "passed": bool(offering),
            "detail": "、".join(offering) if offering else "日期与周期均无可用取值",
        }
    )
    instructor_state = record.fields.get("instructor")
    instructor_ok = bool(instructor_state and instructor_state.is_usable)
    gates.append(
        {
            "gate": "instructor_available",
            "evaluated": True,
            "passed": instructor_ok,
            "detail": f"导师状态 = {instructor_state.status if instructor_state else 'missing'}",
        }
    )
    gates.append(
        {
            "gate": "high_risk_review_done",
            "evaluated": True,
            "passed": not review_queue,
            "detail": (
                f"{len(review_queue)} 个高风险字段待人工审核"
                if review_queue
                else "无待审高风险字段"
            ),
        }
    )
    conflicts = [
        name
        for name in FIELD_NAMES
        if record.fields.get(name) and record.fields[name].status == "conflict"
    ]
    gates.append(
        {
            "gate": "no_unresolved_conflict",
            "evaluated": True,
            "passed": not conflicts,
            "detail": "、".join(conflicts) if conflicts else "无未决冲突",
        }
    )
    for name in OUT_OF_SCOPE_GATES:
        gates.append(
            {
                "gate": name,
                "evaluated": False,
                "passed": False,
                "detail": "本输入包不采集该维度，未评估。",
            }
        )
    return gates


def describe_publication(records: Sequence[ProjectFactRecord], reviews: ReviewRegistry | None = None) -> str:
    """One-line human summary used by the CLI."""
    rows, summary = build_public_rows(records, reviews)
    parts = [
        f"记录 {summary['records']} 条",
        f"待审 {summary['ready_for_review']} 条",
        f"高风险待审 {summary['review_queue_items']} 项",
        f"已过审 {summary['approved_fields']} 项",
        f"已过滤宣传表述 {summary['marketing_segments_filtered']} 处",
    ]
    if summary["stale_approvals"]:
        parts.append(f"审核已过期需重做 {summary['stale_approvals']} 项")
    if summary["fields_dropped_as_purely_promotional"]:
        detail = "、".join(
            f"{key} {count}" for key, count in summary["fields_dropped_as_purely_promotional"].items()
        )
        parts.append(f"整字段为宣传已移除：{detail}")
    if summary["review_queue_by_field"]:
        detail = "、".join(f"{key} {count}" for key, count in summary["review_queue_by_field"].items())
        parts.append(f"待审字段分布：{detail}")
    first_withheld = next((row["review_queue"][0] for row in rows if row["review_queue"]), None)
    if first_withheld:
        parts.append(
            f"示例待审：{first_withheld['field_label']} = {truncate(first_withheld['draft_text'] or '', 40)}"
        )
    return "；".join(parts)
