"""Wiring check: is a source mappable, and what would we actually get from it?

Wiring a new partner is blocked on getting a field table and a few sample
exports. This module removes most of that block: give it whatever export you
already have, and it reports what the six canonical fields would look like
*without writing anything*.

That answers the two questions worth asking before asking a partner for
samples:

* does the file even have the fields, or would five of six stay empty?
* which source keys are not mapped yet -- the concrete punch list for the field
  table, rather than a vague "please send us samples".

Nothing here persists data, and nothing here guesses: a field with no mapping
is reported as unmapped, not invented.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from .config import FIELD_NAMES, SOURCE_KIND_LABELS, field_label
from .schema import ProjectFactRecord
from .utils import comparison_key


def _coverage(records: Sequence[ProjectFactRecord]) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    for name in FIELD_NAMES:
        usable = 0
        conflict = 0
        missing = 0
        promotional_only = 0
        for record in records:
            state = record.fields.get(name)
            if not state:
                missing += 1
                continue
            if state.is_usable:
                usable += 1
            elif state.status == "conflict":
                conflict += 1
            elif state.status == "promotional_only":
                promotional_only += 1
            else:
                missing += 1
        total = len(records)
        coverage[name] = {
            "field_label": field_label(name),
            "usable": usable,
            "conflict": conflict,
            "promotional_only": promotional_only,
            "missing": missing,
            "coverage_rate": round(usable / total, 4) if total else 0.0,
        }
    return coverage


def _unmapped_keys(outputs: Sequence[Any], limit: int = 25) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for output in outputs:
        for key in getattr(output, "unmapped_source_keys", []) or []:
            counts[str(key)] = counts.get(str(key), 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "total_keys": len(ordered),
        "top": [{"key": key, "records": count} for key, count in ordered[:limit]],
    }


def _unmapped_field_hints(outputs: Sequence[Any]) -> list[dict[str, Any]]:
    """Unmapped columns that look like a canonical field.

    A hint, not a mapping: the question is whether excluding the column was
    deliberate. HIREP ships 开课时间（日期） next to 首课时间 / 讲授课开始时间 /
    研究课开始时间 -- all four are dates and only one is the start date, so
    silently leaving three unmapped is exactly the decision that needs to be
    visible.
    """
    from .adapters.csv_table import looks_like_fields

    seen: dict[str, int] = {}
    for output in outputs:
        for key in getattr(output, "unmapped_source_keys", []) or []:
            seen[str(key)] = seen.get(str(key), 0) + 1
    hints = []
    for key, count in sorted(seen.items(), key=lambda item: (-item[1], item[0])):
        fields = looks_like_fields(key)
        if fields:
            hints.append(
                {
                    "column": key,
                    "looks_like": fields,
                    "records": count,
                    "question": "该列形似上述字段，是有意排除还是待补映射？",
                }
            )
    return hints


def _declared_semantics(outputs: Sequence[Any]) -> list[dict[str, Any]]:
    """口径 declarations carried by the loaded profiles, for confirmation."""
    from .adapters import TABLE_PROFILES

    rows = []
    for name in sorted(TABLE_PROFILES):
        profile = TABLE_PROFILES[name]
        for field, text in sorted(getattr(profile, "semantics", {}).items()):
            rows.append({"profile": name, "field": field, "semantics": text})
    return rows


def _template_signatures(outputs: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for output in outputs:
        signature = (output.document.meta or {}).get("template_signature")
        if not signature:
            continue
        name = "+".join(signature)
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def build_wiring_report(
    outputs: Sequence[Any],
    records: Sequence[ProjectFactRecord],
    inputs_meta: Sequence[dict[str, Any]],
    errors: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Assess one candidate source without persisting anything."""
    coverage = _coverage(records)
    empty = [name for name, item in coverage.items() if item["usable"] == 0]
    providers = sorted({record.identity.provider for record in records})
    kinds = sorted({output.document.source_kind for output in outputs})

    return {
        "verdict": _verdict(coverage, empty, errors or {}, len(records)),
        "records": len(records),
        "documents": len(outputs),
        "providers": providers,
        "source_kinds": [
            {"source_kind": kind, "label": SOURCE_KIND_LABELS.get(kind, kind)} for kind in kinds
        ],
        "inputs": list(inputs_meta),
        "field_coverage": coverage,
        "fields_that_stay_empty": [
            {"field": name, "field_label": field_label(name)} for name in empty
        ],
        "unmapped_source_keys": _unmapped_keys(outputs),
        "unmapped_that_look_like_fields": _unmapped_field_hints(outputs),
        "declared_semantics": _declared_semantics(outputs),
        "poster_template_signatures": _template_signatures(outputs),
        "rejected_candidates": sum(len(getattr(o, "rejected", []) or []) for o in outputs),
        "errors": dict(errors or {}),
        "rule": (
            "这是接线自检：只读、不落盘。未映射的源字段不会被猜测，"
            "unmapped_source_keys 就是字段表待补清单。"
        ),
    }


def _verdict(
    coverage: dict[str, Any], empty: list[str], errors: dict[str, int], record_count: int
) -> str:
    # "No usable coverage dict" is not the same as "nothing was read": the dict
    # always has six entries, so the test has to be on the record count.
    if errors and record_count == 0:
        return "unusable：输入无法读取，先修输入"
    usable_fields = sum(1 for item in coverage.values() if item["usable"] > 0)
    if usable_fields == 0:
        return "unmappable：六个字段全部为空，需要字段表或换个源"
    if len(empty) >= 4:
        return (
            f"partially_mappable：只有 {usable_fields}/6 个字段有数据，"
            "建议先确认缺口字段是否有来源"
        )
    if empty:
        return f"mappable_with_gaps：{usable_fields}/6 个字段有数据，{len(empty)} 个待补来源"
    return "mappable：六个字段全部可用"


def subject_signature(records: Sequence[ProjectFactRecord]) -> str:
    """A short fingerprint of the subject matter, for comparing two sources.

    Two exports that describe the same catalogue produce the same signature, so
    a wiring check can say "these are the same programme family" without
    comparing thousands of titles by eye.
    """
    from .dedup import title_of
    from .utils import sha256_text

    titles = sorted({comparison_key(title_of(record)) for record in records})[:200]
    return sha256_text(json.dumps(titles, ensure_ascii=False))
