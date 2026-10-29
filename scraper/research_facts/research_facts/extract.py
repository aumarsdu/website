"""Turn label hits into evidence-bearing field claims.

Extraction confidence follows a written, auditable policy instead of a model:

===========================  ==========  =====================================
input shape                  confidence  reason
===========================  ==========  =====================================
explicit JSON path           high        structured partner API field
``$..name`` recursive path   low         key found by search, not by contract
labeled line in a handbook   high        text layer, deterministic position
labeled row on a poster      medium      left/right columns joined by geometry
multi-line continuation      medium      value extended past its label line
OCR block confidence < 0.90  downgrade   box may be misread; confidence capped
===========================  ==========  =====================================

This is confidence in the *reading*, never in the truth of the statement. A
``high`` claim is still ``verification_status = "unverified"``.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from .claims import classify_text
from .config import Settings
from .labels import (
    MULTI_LINE_FIELDS,
    LabelHit,
    TextBlock,
    is_stop_line,
    scan_line,
)
from .normalize import normalize_field
from .schema import FieldClaim, Locator, RejectedCandidate
from .utils import clean_multiline, clean_text, strip_html, truncate

_CONFIDENCE_ORDER = ("low", "medium", "high")

# A name is a name. A supplier may name a topic "冲击QS前30" and the project is
# still called that, so a marketing marker must never null out a title or an
# instructor name. The marker is still recorded on the claim and still shows up
# in the promotional report, and the public projection filters it from the copy.
# What must never be auto-promoted to a fact is a *promise*, not a name.
NAME_FIELDS: frozenset[str] = frozenset({"project_title", "instructor"})

# Fields whose value has a closed grammar. If a candidate cannot be normalized
# into one, it is not that kind of fact -- it is a neighbouring cell that merely
# sat next to a header. Refusing it is the difference between a missing field
# and a fabricated one.
TYPED_FIELDS: frozenset[str] = frozenset({"start_date", "duration"})

TYPE_MISMATCH = "value_does_not_fit_field_type"
LABEL_NOT_LEADING = "label_not_first_cell_in_row"

# A marketing poster states its deliverables as a counted list rather than
# behind a label: "10 封教授网申推荐信 + 1 篇英文会议论文辅导". A 195-poster
# survey found that line on 100% of the stat-tile family, against 0% label
# coverage there. It is a genuine statement about outputs, so it is read --
# but only into ``output_description``, never into a typed or a name field,
# and only when the line is short and the pattern is closed.
DELIVERABLE_ITEMS = ("推荐信", "论文", "报告", "证书", "专利")
# The counted unit and the artefact must sit next to each other. That adjacency
# is what separates a deliverable ("10 封教授网申推荐信", "1 篇英文会议论文辅导")
# from the stat strip, where "3周 线上直播 6周 论文辅导" names phases and
# "论文辅导" is a caption far from its number. Units are counted articles only:
# 周/课时/人/轮 are schedule, not artefacts.
_DELIVERABLE_RE = re.compile(
    r"\d+\s*(?:封|篇|份)\s*\S{0,12}?(?:" + "|".join(DELIVERABLE_ITEMS) + r")"
)
_MAX_DELIVERABLE_CHARS = 120


def deliverable_shape_claim(
    block: TextBlock,
    *,
    document_id: str,
    locator_kind: str,
) -> FieldClaim | None:
    """Read a counted deliverable line as the output description, or not at all."""
    text = clean_text(block.text)
    if not text or len(text) > _MAX_DELIVERABLE_CHARS or not _DELIVERABLE_RE.search(text):
        return None
    # A line that is mostly a label already has a better, labelled reading.
    if scan_line(text, require_delimiter=False):
        return None
    return make_claim(
        field="output_description",
        raw_text=text,
        locator=Locator(
            kind=locator_kind,
            document_id=document_id,
            pointer=block.pointer,
            detail=block.detail,
            excerpt=truncate(text, 160),
        ),
        extractor="deliverable_shape",
        method="deliverable_shape",
        # Shape-based, so it never claims the certainty of a labelled read.
        base_confidence="low",
        ocr_confidence=block.ocr_confidence,
    )


def _cap(base: str, ceiling: str) -> str:
    if _CONFIDENCE_ORDER.index(base) <= _CONFIDENCE_ORDER.index(ceiling):
        return base
    return ceiling


def ocr_confidence_ceiling(ocr_confidence: float | None) -> str:
    """Map a real OCR box score onto an extraction ceiling."""
    if ocr_confidence is None:
        return "high"
    if ocr_confidence >= 0.90:
        return "high"
    if ocr_confidence >= 0.70:
        return "medium"
    return "low"


def make_claim(
    *,
    field: str,
    raw_text: str,
    locator: Locator,
    extractor: str,
    method: str,
    base_confidence: str,
    ocr_confidence: float | None = None,
    rejected: list[RejectedCandidate] | None = None,
) -> FieldClaim | None:
    """Build one claim, or ``None`` when the text carries no statement.

    Returning ``None`` for an empty or unparseable value is what keeps "not
    stated" from becoming "stated as empty". When ``rejected`` is supplied, a
    refusal is recorded there instead of vanishing.
    """
    text = clean_multiline(strip_html(raw_text)) if "\n" in str(raw_text) else clean_text(strip_html(raw_text))
    if not text:
        return None

    normalized = normalize_field(field, text)
    if field in TYPED_FIELDS and normalized is None and rejected is not None:
        # e.g. the header cell "开班人数" read as a 项目周期 value.
        rejected.append(
            RejectedCandidate(
                field=field,
                candidate_text=text,
                locator=locator,
                extractor=extractor,
                reason=TYPE_MISMATCH,
            )
        )
        return None
    verdict = classify_text(text)
    confidence = _cap(base_confidence, ocr_confidence_ceiling(ocr_confidence))
    has_factual = True if field in NAME_FIELDS else verdict.has_factual_content

    return FieldClaim(
        field=field,
        raw_text=text,
        normalized_value=normalized.value if normalized else None,
        normalization=normalized.to_dict() if normalized else None,
        locator=locator,
        extractor=extractor,
        extraction_method=method,
        extraction_confidence=confidence,
        evidence_kind=verdict.kind,
        deliverable_claim_type=verdict.claim_type,
        has_factual_content=has_factual,
        matched_phrases=tuple(sorted(set(verdict.phrases))),
    )


def _continuation(
    blocks: Sequence[TextBlock], start_index: int, settings: Settings
) -> tuple[str, int]:
    """Collect the lines that continue a multi-line labeled value."""
    parts: list[str] = []
    total = 0
    last = start_index
    for block in blocks[start_index + 1 :]:
        if len(parts) >= settings.max_continuation_lines:
            break
        text = block.text.strip()
        if not text:
            # One blank line ends the field; do not skip over it.
            break
        if is_stop_line(text):
            break
        if total + len(text) > settings.max_continuation_chars:
            break
        parts.append(text)
        total += len(text)
        last = start_index + 1 + len(parts) - 1
    return "\n".join(parts), last


def claims_from_blocks(
    blocks: Sequence[TextBlock],
    *,
    document_id: str,
    source_kind: str,
    settings: Settings,
    require_delimiter: bool = True,
    locator_kind: str = "text_line",
    base_confidence: str = "high",
    label_must_lead_row: bool = False,
    rejected: list[RejectedCandidate] | None = None,
) -> list[FieldClaim]:
    """Extract every labeled value from a sequence of text blocks.

    Blocks must already be in reading order. One block may carry more than one
    label (a poster row is the normal case). Pass ``rejected`` to collect the
    label matches that were refused.
    """
    claims: list[FieldClaim] = []
    for index, block in enumerate(blocks):
        hits = scan_line(
            block.text,
            require_delimiter=require_delimiter,
            label_must_lead_row=label_must_lead_row,
        )
        for hit in hits:
            claim = _claim_from_hit(
                hit,
                block=block,
                blocks=blocks,
                index=index,
                document_id=document_id,
                source_kind=source_kind,
                settings=settings,
                locator_kind=locator_kind,
                base_confidence=base_confidence,
                rejected=rejected,
            )
            if claim is not None:
                claims.append(claim)
    return claims


def _claim_from_hit(
    hit: LabelHit,
    *,
    block: TextBlock,
    blocks: Sequence[TextBlock],
    index: int,
    document_id: str,
    source_kind: str,
    settings: Settings,
    locator_kind: str,
    base_confidence: str,
    rejected: list[RejectedCandidate] | None = None,
) -> FieldClaim | None:
    multi_line = hit.field in MULTI_LINE_FIELDS
    tail, last_index = _continuation(blocks, index, settings) if multi_line else ("", index)

    if not hit.inline_value or not hit.value:
        # A bare label with nothing after it is only useful to a multi-line field.
        if not multi_line or not tail:
            return None
        value = tail
    elif tail:
        # A labeled bullet list: the first item sits on the label line and the
        # rest follow. They belong to the same statement.
        value = f"{hit.value}\n{tail}"
    else:
        value = hit.value

    extends = last_index > index
    locator = Locator(
        kind=locator_kind,
        document_id=document_id,
        pointer=(
            f"{block.pointer}..{blocks[last_index].pointer}" if extends else block.pointer
        ),
        detail=_extend_detail(block.detail, index, last_index),
        excerpt=truncate(f"{block.text} / {value}" if extends else block.text, 160),
    )
    return make_claim(
        field=hit.field,
        raw_text=value,
        locator=locator,
        extractor=f"label:{hit.label}",
        method="label_multiline" if extends else "label",
        # Reading past the label line is a geometry guess, so the ceiling drops.
        base_confidence=_cap(base_confidence, "medium") if extends else base_confidence,
        ocr_confidence=block.ocr_confidence,
        rejected=rejected,
    )


def _extend_detail(detail: str, start: int, end: int) -> str:
    suffix = f"lines {start + 1}-{end + 1}" if end > start else ""
    return f"{detail} {suffix}".strip() if detail else suffix


def claims_from_json_paths(
    payload: Any,
    mapping: dict[str, Sequence[str]],
    *,
    document_id: str,
    profile_name: str,
    rejected: list[RejectedCandidate] | None = None,
) -> list[FieldClaim]:
    """Extract claims from a structured partner payload via configured paths.

    ``mapping`` maps a canonical field to an ordered list of JSON paths. The
    first path that resolves to a non-empty value wins. Nothing else is read:
    fields without a configured path stay missing, and unmapped source keys are
    reported rather than guessed at.
    """
    from .utils import json_path_get  # local import keeps module import order simple

    claims: list[FieldClaim] = []
    for field, paths in mapping.items():
        for path in paths:
            value = json_path_get(payload, path)
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                continue  # a container is not a stated value; skip to the next path
            confidence = "low" if path.startswith("$..") else "high"
            claim = make_claim(
                field=field,
                raw_text=str(value),
                locator=Locator(
                    kind="json_path",
                    document_id=document_id,
                    pointer=path,
                    detail=f"profile={profile_name}",
                    excerpt=truncate(str(value), 160),
                ),
                extractor=f"json_path:{path}",
                method="json_path",
                base_confidence=confidence,
                rejected=rejected,
            )
            if claim is not None:
                claims.append(claim)
                break
    return claims
