"""T04 adapters: map the four structured entries onto the T02 contract.

Common logic lives here; per-entry differences are data (ADAPTER_CONFIG).
Adapters never write the main database; they emit T08 staging rows so the
strong validator and atomic sealing apply unchanged.
"""

from __future__ import annotations

from typing import Any

from contract import identity_key

ADAPTER_CONFIG: dict[str, dict[str, Any]] = {
    "jisi_future_sou_tools": {
        "id_field": "id",
        "fields": {
            "title": "name",
            "instructor": "raw.dTeacherNickName",
            "institution": "raw.dTeacherSchool",
            "start_date": "raw.schoolBegins",
            "duration": "raw.cycle",
        },
        "order_field": "crawled_at",
    },
    "jisi_future_domestic": {
        "id_field": "id",
        "fields": {
            "title": "name",
            "instructor": "raw.dTeacherNickName",
            "institution": "raw.dTeacherSchool",
            "start_date": "raw.schoolBegins",
            "duration": "raw.cycle",
        },
        "order_field": "crawled_at",
    },
    "zhongke": {
        "id_field": "id",
        "fields": {
            "title": "title",
            "category": "category",
            "instructor": "teacher",
            "institution": "university",
        },
        "order_field": "crawled_at",
    },
    "hirep": {
        "id_field": "business_id",
        "fields": {
            "title": "title",
            "category": "category",
            "instructor": "professor",
            "institution": "university",
        },
        "order_field": "crawled_at",
    },
}


class AdapterError(ValueError):
    """The entry is not covered by the adapter configuration."""


def resolve(record: dict[str, Any], dotted: str) -> Any:
    """Follow a dotted path; returns None when any level is absent."""
    current: Any = record
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def adapt_row(entry: str, row: dict[str, Any]) -> dict[str, Any]:
    """Map one source row to a staging row plus identity/observation metadata."""
    config = ADAPTER_CONFIG.get(entry)
    if config is None:
        raise AdapterError("entry_not_configured")
    native = row.get(config["id_field"])
    staging_row: dict[str, Any] = {}
    field_states: dict[str, str] = {}
    for target, source_path in config["fields"].items():
        value = resolve(row, source_path)
        if value is None:
            field_states[target] = "not_provided"
            continue
        if isinstance(value, str):
            if value.strip():
                staging_row[target] = value
                field_states[target] = "value"
            else:
                field_states[target] = "explicitly_empty"
            continue
        staging_row[target] = value
        field_states[target] = "value"
    order_value = row.get(config["order_field"])
    if native is None or native == "":
        return {
            "native_id": None,
            "unmapped_reason": "id_missing",
            "staging_row": staging_row,
            "field_states": field_states,
            "order_key": order_value,
        }
    staging_row["id"] = str(native)
    if order_value is not None:
        staging_row["crawled_at"] = order_value
    return {
        "native_id": str(native),
        "identity_key": identity_key(entry, str(native)),
        "staging_row": staging_row,
        "field_states": field_states,
        "order_key": order_value,
    }


def adapt_rows(entry: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Adapt a batch; counts reconcile rows in against classified rows out."""
    mapped: list[dict[str, Any]] = []
    unmapped = 0
    for row in rows:
        adapted = adapt_row(entry, row)
        if adapted["native_id"] is None:
            unmapped += 1
            continue
        mapped.append(adapted)
    return {
        "entry": entry,
        "rows_in": len(rows),
        "mapped": mapped,
        "unmapped": unmapped,
        "counts": {"rows_in": len(rows), "mapped": len(mapped), "unmapped": unmapped},
    }
