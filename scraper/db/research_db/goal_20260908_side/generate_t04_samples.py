"""Generate T04 adapter samples from real registered inputs and freeze expectations.

Samples are deterministic positions (first two, quantiles, last) from the
registered pilot files, within pilot limits. Expected mappings are produced by
the dotted-path mapping CONFIG below (independent of adapters.py), one entry
per sample. Output: fixtures/t04/<entry>/samples.jsonl + fixtures/t04_expected.json.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SIDE = Path(__file__).resolve().parent
WORKSPACE = SIDE.parent.parent.parent
FIX = SIDE / "fixtures" / "t04"

PILOT_LIMITS = {
    "jisi_future_sou_tools": 25,
    "jisi_future_domestic": 25,
    "zhongke": 50,
    "hirep": 50,
}
SAMPLE_FILES = {
    "jisi_future_sou_tools": "集思未来/output/full_refresh/20260602-full-refresh/sou_tools/processed/records.jsonl",
    "jisi_future_domestic": "集思未来/output/full_refresh/20260602-full-refresh/domestic/processed/records.jsonl",
    "zhongke": "中科/output/processed/projects.jsonl",
    "hirep": "HIREP/output_pbl_full_refresh_20260602/processed/projects.jsonl",
}
# per-entry mapping config (the reviewed source of truth for expectations)
ADAPTER_CONFIG = {
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
SAMPLE_POSITIONS = {
    "jisi_future_sou_tools": [1, 2, 3, 6, 9, 12, 15, 18, 21, 25],
    "jisi_future_domestic": [1, 2, 3, 6, 9, 12, 15, 18, 21, 25],
    "zhongke": [1, 2, 5, 10, 15, 20, 25, 30, 40, 50],
    "hirep": [1, 2, 5, 10, 15, 20, 25, 30, 40, 50],
}


def get_path(record: dict, dotted: str):
    current = record
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


for entry, limit in PILOT_LIMITS.items():
    rows = []
    positions = [p for p in SAMPLE_POSITIONS[entry] if p <= limit]
    with open(WORKSPACE / SAMPLE_FILES[entry], encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if index > positions[-1]:
                break
            if index in positions:
                rows.append(json.loads(line))
    entry_dir = FIX / entry
    entry_dir.mkdir(parents=True, exist_ok=True)
    with open(entry_dir / "samples.jsonl", "w", encoding="utf-8") as out:
        out.writelines(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        )
    cfg = ADAPTER_CONFIG[entry]
    expectations = []
    for row in rows:
        native_id = row.get(cfg["id_field"])
        business = {}
        states = {}
        for target, source_path in cfg["fields"].items():
            value = get_path(row, source_path)
            if value is None:
                states[target] = "not_provided"
            elif isinstance(value, str) and value.strip():
                business[target] = value
                states[target] = "value"
            elif isinstance(value, str):
                states[target] = "explicitly_empty"
            else:
                states[target] = "value"
                business[target] = value
        expectations.append(
            {
                "native_id": str(native_id) if native_id is not None else None,
                "business": business,
                "field_states": states,
                "order_key": row.get(cfg["order_field"]),
            }
        )
    expected_path = entry_dir / "expected.json"
    expected_path.write_text(
        json.dumps(
            {"entry": entry, "config": cfg, "expectations": expectations},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(entry, "samples:", len(rows), "expected:", len(expectations))

all_expected = {"frozen_at": "2026-09-25", "entries": {}}
for entry in PILOT_LIMITS:
    all_expected["entries"][entry] = json.loads(
        (FIX / entry / "expected.json").read_text(encoding="utf-8")
    )
out = FIX / "t04_expected.json"
out.write_text(
    json.dumps(all_expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print("frozen:", out, "sha256:", hashlib.sha256(out.read_bytes()).hexdigest())
