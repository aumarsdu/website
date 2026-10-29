"""Generate T08 staging fixtures and freeze expected verdicts.

Positive sample: synthetic 4-row batch exercising accepted/duplicate/field states.
Negative variants derive from it by mutation (each has a frozen verdict).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

SIDE = Path(__file__).resolve().parent
FIX = SIDE / "fixtures" / "t08"


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(canonical_json(r) + "\n" for r in rows), encoding="utf-8")


if FIX.exists():
    shutil.rmtree(FIX)

cases = {}

# ---- positive sample ----
ok = FIX / "case_ok"
ok.mkdir(parents=True)
rows = [
    {
        "id": "SYN-001",
        "title": "项目A",
        "category": "理工科",
        "price": "12000",
        "currency": "CNY",
        "start_date": "2026-06-15",
        "crawled_at": "2026-06-02T07:52:16Z",
        "url": "https://example.com/p/1?track=ad",
        "internal_note": "secret-A",
    },
    {
        "id": "SYN-002",
        "title": "项目B",
        "category": "理工科",
        "price": None,
        "start_date": "2026年7月",
        "crawled_at": "2026-06-02T07:52:16Z",
        "url": "https://example.com/p/2",
    },
    {
        "id": "SYN-001",
        "title": "项目A",
        "category": "理工科",
        "price": "12000",
        "currency": "CNY",
        "start_date": "2026-06-15",
        "crawled_at": "2026-06-02T07:52:16Z",
        "url": "https://example.com/p/1?track=ad",
    },
    {"id": "", "title": "无ID", "crawled_at": "2026-06-02T07:52:16Z"},
    {
        "id": "SYN-004",
        "title": "坏价格",
        "price": 12000,
        "crawled_at": "2026-06-02T07:52:16Z",
    },
]
write_jsonl(ok / "records.jsonl", rows)
manifest = {
    "contract_version": "1",
    "batch_id": "batch-syn-001",
    "source_code": "jisi_future_sou_tools",
    "capture_mode": "full",
    "captured_at": "2026-06-02T07:52:16Z",
    "observed_order": "unknown",
    "coverage": "complete",
    "adapter_version": "a1",
    "mapping_version": "m1",
    "hash_version": "h1",
    "scope": {"entry": "synthetic"},
    "input_files": [
        {
            "relative_path": "records.jsonl",
            "sha256": digest_bytes((ok / "records.jsonl").read_bytes()),
            "byte_size": (ok / "records.jsonl").stat().st_size,
            "row_count": 5,
            "format": "jsonl",
            "role": "fact",
        }
    ],
}
(ok / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
cases["case_ok"] = {
    "expected": {
        "accepted": 2,
        "duplicate": 1,
        "rejected": 1,
        "quarantined": 1,
        "rows_read": 5,
        "sealed": True,
        "scrubbed_fields_absent": ["url", "internal_note", "crawled_at"],
        "sealed_rows": 2,
    }
}


def write_variant(name: str, mutate) -> None:
    d = FIX / name
    d.mkdir(parents=True)
    shutil.copy(ok / "manifest.json", d / "manifest.json")
    shutil.copy(ok / "records.jsonl", d / "records.jsonl")
    mutate(d)


# invalid rows -> all rejected but counts must reconcile
def mut_badjson(d: Path) -> None:
    p = d / "records.jsonl"
    text = (ok / "records.jsonl").read_text(encoding="utf-8")
    p.write_text(text + "{broken json\n", encoding="utf-8")
    # hash/size stay consistent with the manifest on purpose: this variant
    # isolates the row-count mismatch; the manifest row_count stays 5
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    m["input_files"][0]["sha256"] = digest_bytes(p.read_bytes())
    m["input_files"][0]["byte_size"] = p.stat().st_size
    (d / "manifest.json").write_text(canonical_json(m), encoding="utf-8")


write_variant("case_bad_json", mut_badjson)
cases["case_bad_json"] = {
    "expected": {
        "rejected": "manifest_row_count_mismatch",
        "sealed": False,
        "error": "row_count_mismatch",
    }
}


def mut_truncated(d: Path) -> None:
    p = d / "records.jsonl"
    text = (ok / "records.jsonl").read_text(encoding="utf-8")
    cut = text[: len(text) // 2]
    p.write_text(cut, encoding="utf-8")
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    m["input_files"][0]["row_count"] = 2
    m["input_files"][0]["sha256"] = digest_bytes(p.read_bytes())
    m["input_files"][0]["byte_size"] = p.stat().st_size
    (d / "manifest.json").write_text(canonical_json(m), encoding="utf-8")


write_variant("case_truncated", mut_truncated)
cases["case_truncated"] = {"expected": {"sealed": False, "error": "row_truncated"}}


def mut_missing_file(d: Path) -> None:
    (d / "records.jsonl").unlink()
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    m["input_files"][0]["sha256"] = digest_bytes(b"gone")
    m["input_files"][0]["byte_size"] = 4
    (d / "manifest.json").write_text(canonical_json(m), encoding="utf-8")


write_variant("case_missing_file", mut_missing_file)
cases["case_missing_file"] = {"expected": {"sealed": False, "error": "input_missing"}}


def mut_hash_mismatch(d: Path) -> None:
    p = d / "records.jsonl"
    text = (ok / "records.jsonl").read_text(encoding="utf-8")
    p.write_text(text.replace("项目A", "项目X"), encoding="utf-8")


write_variant("case_hash_mismatch", mut_hash_mismatch)
cases["case_hash_mismatch"] = {"expected": {"sealed": False, "error": "input_changed"}}


def mut_empty(d: Path) -> None:
    for f in d.iterdir():
        f.unlink()


write_variant("case_empty_dir", mut_empty)
cases["case_empty_dir"] = {"expected": {"sealed": False, "error": "empty_input"}}


# observations referencing unknown record and cross-record payload pointer
def mut_observations(d: Path) -> None:
    write_jsonl(
        d / "observations.jsonl",
        [
            {
                "record": "SYN-001",
                "context_key": "detail",
                "payload_ref": "missing-hash",
                "order_key": "2026-06-02T07:52:16Z",
            },
            {
                "record": "SYN-999",
                "context_key": "detail",
                "payload_ref": "missing-hash",
                "order_key": "2026-06-02T07:52:16Z",
            },
        ],
    )
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    m["input_files"].append(
        {
            "relative_path": "observations.jsonl",
            "sha256": digest_bytes((d / "observations.jsonl").read_bytes()),
            "byte_size": (d / "observations.jsonl").stat().st_size,
            "row_count": 2,
            "format": "jsonl",
            "role": "observation",
        }
    )
    (d / "manifest.json").write_text(canonical_json(m), encoding="utf-8")


write_variant("case_observations_bad_refs", mut_observations)
cases["case_observations_bad_refs"] = {
    "expected": {
        "sealed": False,
        "errors": ["observation_payload_unknown", "observation_record_unknown"],
    }
}

expected_file = SIDE / "fixtures" / "t08_expected.json"
expected_file.write_text(
    json.dumps(
        {
            "cases": cases,
            "frozen_at": "2026-09-25",
            "note": "verdicts frozen before stage_validator.py implementation",
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
print("frozen:", expected_file)
print("sha256:", digest_bytes(expected_file.read_bytes()))
