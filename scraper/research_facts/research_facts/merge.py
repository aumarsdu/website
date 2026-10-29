"""Group documents into project records and resolve each field against evidence.

Two rules define the whole module.

**Nothing is dropped.** A field that two sources disagree about keeps every
claim and reports ``status = "conflict"`` with no selected value. The conflict
report and the evidence index are the deliverable; an automatic tie-break would
destroy the only useful information.

**Nothing is invented.** A field with no claim is ``missing`` with a null
value. Grouping documents into one record is the only inference performed, and
a title-similarity group is flagged ``review_required`` so it is treated as a
candidate link, never as a settled merge (design doc section 4.7).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .adapters.base import AdapterOutput
from .adapters.textblock import title_similarity
from .config import FIELD_NAMES, Settings
from .merging import MergeRegistry
from .review import ReviewRegistry, evidence_fingerprint
from .schema import claim_display_value
from .schema import (
    FieldClaim,
    FieldState,
    Identity,
    ProjectFactRecord,
    dedupe_claims,
    sort_records,
)
from .utils import comparison_key, sha256_text

# Fields whose value is an item list: one source listing a subset of another's
# items is "less detail", not a contradiction.
SUBSET_TOLERANT_FIELDS: frozenset[str] = frozenset({"suitable_audience", "output_description"})

# A poster carries a short name and the API a full one. Neither contradicts the
# other, so a title that contains the other is "same project, different length".
CONTAINMENT_TOLERANT_FIELDS: frozenset[str] = frozenset({"project_title"})

_CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}
_SLUG_RE = re.compile(r"[^\w\u3400-\u9fff]+")


def _slug(value: str, limit: int = 48) -> str:
    return _SLUG_RE.sub("_", str(value)).strip("_")[:limit] or "unnamed"


@dataclass
class _Group:
    key: tuple[str, str]
    identity: Identity
    documents: list[str] = None  # type: ignore[assignment]
    claims: list[FieldClaim] = None  # type: ignore[assignment]
    links: list[dict[str, Any]] = None  # type: ignore[assignment]
    issues: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.documents = self.documents or []
        self.claims = self.claims or []
        self.links = self.links or []
        self.issues = self.issues or []


def _claim_rank(claim: FieldClaim) -> tuple[int, int, int, str, str]:
    """Deterministic "best evidence" ordering.

    Preference order: the claim has plain content, then the claim is not
    marketing, then extraction confidence, then a stable id tie-break. The
    ordering is total, so two runs always pick the same claim.
    """
    return (
        0 if claim.has_factual_evidence else 1,
        1 if claim.is_promotional else 0,
        _CONFIDENCE_RANK.get(claim.extraction_confidence, 3),
        claim.locator.document_id,
        claim.locator.pointer,
    )


def _better_title(current: str | None, candidate: str) -> str:
    """Pick a group title without depending on input order.

    The longest title wins, with the document id as a tie-break. "First one
    seen" would make the record change when the inputs are sorted differently.
    """
    if not current or len(candidate) > len(current) or (len(candidate) == len(current) and candidate < current):
        return candidate
    return current


def _record_key(provider: str, basis: str, value: str) -> str:
    return f"{provider}:{basis}:{_slug(value)}"


def _group_outputs(
    outputs: Sequence[AdapterOutput],
    settings: Settings,
    merges: MergeRegistry | None = None,
) -> dict[tuple[str, str], _Group]:
    """Bucket documents into groups, honouring any human merge decisions.

    A merge is applied as an identity union *before* grouping, so the merged
    sides land in one group and the ordinary field machinery decides whether
    the result is resolved or still conflicted. That is deliberate: deciding
    two records are the same entity says nothing about whether their facts
    agree.
    """
    groups: dict[tuple[str, str], _Group] = {}
    # Title index per provider, used only to *propose* a link.
    titles: dict[str, list[tuple[str, str]]] = {}

    for output in outputs:
        document = output.document
        provider = document.provider
        external_id = (document.external_id or "").strip()
        title_hint = (document.title_hint or "").strip()

        key: tuple[str, str] | None = None
        if external_id:
            key = (provider, external_id)
            identity = Identity(
                provider=provider,
                external_id=external_id,
                title_hint=title_hint or None,
                basis="external_id",
            )
        elif not settings.strict_identity and title_hint:
            # Deterministic candidate pick: highest similarity, then the
            # lexicographically smallest key, so input order cannot decide.
            best: tuple[float, str, tuple[str, str]] | None = None
            for existing_key, existing_title in sorted(titles.get(provider, [])):
                score = title_similarity(title_hint, existing_title)
                if score < settings.identity_similarity_threshold:
                    continue
                if best is None or score > best[0]:
                    best = (score, existing_title, existing_key)
            if best is not None:
                score, matched_title, existing_key = best
                key = existing_key
                group = groups[existing_key]
                group.identity = Identity(
                    provider=provider,
                    external_id=group.identity.external_id,
                    title_hint=_better_title(group.identity.title_hint, title_hint),
                    basis="title_similarity",
                    similarity_score=score,
                    review_required=True,
                )
                group.links.append(
                    {
                        "type": "identity_similarity",
                        "from_document": document.document_id,
                        "basis": "title_similarity",
                        "similarity_score": score,
                        "matched_title": matched_title,
                        "status": "candidate_requires_review",
                    }
                )
            else:
                key = (provider, comparison_key(title_hint))
                # A title-only identity is still unstable: once an external id
                # arrives the record key changes. Flag it from the start.
                identity = Identity(
                    provider=provider, title_hint=title_hint, basis="title", review_required=True
                )
                titles.setdefault(provider, []).append((key[1], title_hint))
        else:
            key = (provider, document.document_id)
            identity = Identity(provider=provider, title_hint=title_hint or None, basis="unresolved", review_required=True)

        if key is None:  # pragma: no cover - defensive
            continue

        group = groups.get(key)
        if group is None:
            group = _Group(key=key, identity=identity)
            groups[key] = group
        elif title_hint:
            group.identity = Identity(
                provider=group.identity.provider,
                external_id=group.identity.external_id,
                title_hint=_better_title(group.identity.title_hint, title_hint),
                basis=group.identity.basis,
                similarity_score=group.identity.similarity_score,
                review_required=group.identity.review_required,
            )
        if document.document_id not in group.documents:
            group.documents.append(document.document_id)
        group.claims.extend(output.claims)

    if merges is not None and merges.decisions:
        groups = _apply_merges(groups, merges)
    return groups


def _apply_merges(
    groups: dict[tuple[str, str], _Group], merges: MergeRegistry
) -> dict[tuple[str, str], _Group]:
    """Fold merged identity pairs into one group, and report what was skipped."""
    by_text: dict[str, tuple[str, str]] = {}
    side_evidence: dict[tuple[str, str], tuple[list[str], list[str]]] = {}
    for key, group in groups.items():
        text = _record_key(key[0], "external_id", key[1])
        by_text[text] = key
        side_evidence[key] = (
            list(group.documents),
            [sha256_text(claim.raw_text) for claim in group.claims],
        )

    finder, applied, skipped = merges.resolve(by_text, side_evidence)
    merges.applied = applied
    merges.skipped = skipped

    # The union is built over group keys, so the root *is* the surviving key.
    folded: dict[tuple[str, str], _Group] = {}
    for key, group in groups.items():
        target = finder.find(key)
        existing = folded.get(target)
        if existing is None:
            folded[target] = group
            continue
        for document_id in group.documents:
            if document_id not in existing.documents:
                existing.documents.append(document_id)
        existing.claims.extend(group.claims)
        detail = f"人工合并：{_record_key(key[0], 'external_id', key[1])} 并入本记录。"
        if not any(item.get("detail") == detail for item in existing.issues):
            existing.issues.append({"type": "identity_merged", "detail": detail})
    for group in folded.values():
        group.documents.sort()
    return folded


def _subset_chain(claims: Sequence[FieldClaim]) -> tuple[bool, FieldClaim | None]:
    """True when every item set is contained in the largest one."""
    item_sets = {claim.compare_value: claim.compare_items for claim in claims if claim.compare_items}
    if len(item_sets) < 2:
        return True, None
    largest_value = max(item_sets, key=lambda value: len(item_sets[value]))
    largest = item_sets[largest_value]
    chained = all(items <= largest for items in item_sets.values())
    if not chained:
        return False, None
    best = max(
        (claim for claim in claims if claim.compare_value == largest_value),
        key=lambda claim: _claim_rank(claim),
    )
    return True, best


def _containment_chain(claims: Sequence[FieldClaim]) -> tuple[bool, FieldClaim | None]:
    """True when every distinct value is a substring of the longest one."""
    values = {claim.compare_value: claim for claim in claims if claim.compare_value}
    if len(values) < 2:
        return True, None
    longest = max(values, key=len)
    contained = all(
        value == longest or value in longest for value in values if value != longest
    )
    if not contained:
        return False, None
    best = max(
        (claim for claim in claims if claim.compare_value == longest),
        key=lambda claim: _claim_rank(claim),
    )
    return True, best


def _tolerant_reconcile(
    field: str, claims: Sequence[FieldClaim]
) -> tuple[bool, FieldClaim | None, str]:
    """Decide whether differing values are compatible rather than contradictory."""
    if field in CONTAINMENT_TOLERANT_FIELDS:
        ok, best = _containment_chain(claims)
        return ok, best, "多源为简称/全称关系，已采用最完整的一条；其余表述作为证据保留。"
    if field in SUBSET_TOLERANT_FIELDS:
        ok, best = _subset_chain(claims)
        return ok, best, "多源条目数量不同，已采用信息最全的一条；其余表述作为证据保留。"
    return False, None, ""


def _apply_adjudication(
    state: FieldState, record_key: str, registry: ReviewRegistry | None
) -> bool:
    """Resolve a conflict with a human decision. Returns True if it applied.

    Three rules keep this from becoming a loophole:

    1. The adjudicator names one of the competing statements. A value that no
       source stated cannot be adjudicated in.
    2. Only plain statements may be chosen. A side that is purely promotional
       is refused, so a conflict cannot be settled by picking the promise.
    3. No claim is removed. The losing sides stay in ``claims`` and stay in the
       conflict report, so the decision can be audited or reversed.
    """
    if registry is None or state.status != "conflict" or len(state.claims) < 2:
        return False
    decision = registry.adjudication_for(
        record_key, state.field, evidence_fingerprint(state)
    )
    if decision is None:
        return False

    wanted = decision.chosen_value
    chosen = [
        claim
        for claim in state.claims
        if claim_display_value(claim) == wanted or claim.compare_value == wanted
    ]
    if not chosen:
        return False
    if not any(claim.has_factual_evidence for claim in chosen):
        state.note = (
            f"裁决选择了仅含宣传表述的一方（{decision.chosen_value}），已拒绝采用；"
            f"请改选另一方或补充证据。裁决人：{decision.reviewer}"
        )
        return False

    winner = min(chosen, key=_claim_rank)
    state.status = "resolved"
    state.resolution = "human_adjudication"
    state.selected_claim = winner
    state.selected_raw_text = winner.raw_text
    state.selected_normalized_value = winner.normalized_value
    state.note = (
        f"来源之间不一致，已由 {decision.reviewer} 于 {decision.reviewed_at} 裁决采用"
        f"「{winner.normalized_value or winner.raw_text}」；"
        f"被舍弃的一方仍作为证据保留。裁决备注：{decision.note or '无'}"
    )
    if state.has_promotional_evidence:
        state.note += "（本字段仍含宣传表述，对外文案需过滤）"
    return True


def _build_field_state(
    field: str,
    claims: Sequence[FieldClaim],
    *,
    record_key: str = "",
    registry: ReviewRegistry | None = None,
) -> FieldState:
    """Decide what the evidence supports for one field."""
    state = FieldState(field=field, status="missing")
    if not claims:
        state.note = "来源未给出该字段内容，未补写。"
        return state

    state.claims = dedupe_claims(claims)
    distinct: dict[str, FieldClaim] = {}
    for claim in state.claims:
        distinct.setdefault(claim.compare_value, claim)
    # Report the readable value, not the punctuation-stripped comparison key.
    state.conflict_values = sorted({claim_display_value(claim) for claim in distinct.values()})

    chained, superset_claim, note = _tolerant_reconcile(field, state.claims)
    if len(distinct) > 1 and chained and superset_claim is not None:
        state.status = "resolved"
        state.selected_claim = superset_claim
        state.note = note
    elif len(distinct) > 1:
        state.status = "conflict"
        state.note = "来源之间不一致，未选择任何一方；双方证据均已保留。"
        if _apply_adjudication(state, record_key, registry):
            return state
        return state
    else:
        state.selected_claim = min(state.claims, key=_claim_rank)

    claim = state.selected_claim
    assert claim is not None
    if not claim.has_factual_evidence:
        state.status = "promotional_only"
        state.selected_claim = None
        state.selected_raw_text = None
        state.selected_normalized_value = None
        state.note = "仅有供应商宣传表述，未作为事实采用；请人工核验后再决定是否引用。"
        return state

    if state.has_promotional_evidence:
        state.status = "resolved_with_promotional"
        state.note = "内容一致，但包含供应商宣传表述；对外文案需过滤宣传部分。"
    else:
        state.status = "resolved"
    state.selected_raw_text = claim.raw_text
    state.selected_normalized_value = claim.normalized_value
    if claim.normalized_value is None:
        # The statement exists but has no canonical form. Say so instead of
        # letting a null value look like missing data.
        state.note = "原文已获取，但未能归一化；请直接使用 raw_text，不要据此推断。"
    return state


def build_records(
    outputs: Sequence[AdapterOutput],
    settings: Settings,
    registry: ReviewRegistry | None = None,
    merges: MergeRegistry | None = None,
) -> tuple[list[ProjectFactRecord], dict[str, Any]]:
    """Group adapter output into one record per project."""
    groups = _group_outputs(outputs, settings, merges)
    records: list[ProjectFactRecord] = []

    for (provider, basis_value), group in sorted(groups.items()):
        basis = group.identity.basis
        record_key = _record_key(provider, basis, basis_value)
        by_field: dict[str, list[FieldClaim]] = {name: [] for name in FIELD_NAMES}
        for claim in group.claims:
            if claim.field in by_field:
                by_field[claim.field].append(claim)

        fields = {
            name: _build_field_state(
                name, by_field[name], record_key=record_key, registry=registry
            )
            for name in FIELD_NAMES
        }
        record = ProjectFactRecord(
            record_key=record_key,
            identity=group.identity,
            document_ids=sorted(group.documents),
            fields=fields,
            links=sorted(group.links, key=lambda link: json_key(link)),
            issues=group.issues,
        )

        if basis != "external_id":
            record.issues.append(
                {
                    "type": "identity_not_stable",
                    "detail": f"identity basis = {basis}；补齐 external_id 后 record_key 会变化，"
                    "建议接入方确认后再固定。",
                }
            )
        if not record.usable_fields:
            record.issues.append(
                {"type": "no_usable_field", "detail": "六个规范字段均无可用取值。"}
            )
        record.validate()
        records.append(record)

    adjudicated = sum(
        1
        for record in records
        for state in record.fields.values()
        if state.resolution == "human_adjudication"
    )
    stats = {
        "documents": len(outputs),
        "records": len(records),
        "claims": sum(len(group.claims) for group in groups.values()),
        "groups_by_basis": _count_by(groups.values(), lambda group: group.identity.basis),
        "adjudicated_fields": adjudicated,
        "merged_records": sum(
            1
            for record in records
            if any(issue.get("type") == "identity_merged" for issue in record.issues)
        ),
    }
    return sort_records(records), stats


def _count_by(items: Iterable[Any], key) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        name = key(item)
        counts[str(name)] = counts.get(str(name), 0) + 1
    return dict(sorted(counts.items()))


def json_key(payload: Any) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
