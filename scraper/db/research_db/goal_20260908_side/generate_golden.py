"""Generate and freeze T02 contract golden expectations.

Run BEFORE implementing contract.py. The algorithm block below is the
normative mini-spec; contract.py must reproduce the frozen digests.
Edit only through a new hash_version — frozen files never change in place.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def identity_key(source_code: str, native_id: str) -> str:
    return canonical_json({"native_id": native_id, "source": source_code})


def payload_hash(record: dict, whitelist: list[str], hash_version: str) -> str:
    business = {k: record[k] for k in whitelist if k in record}
    return digest(canonical_json({"business": business, "hash_version": hash_version}))


def observation_key(batch_id: str, ident: str, context_key: str, payload: str) -> str:
    return canonical_json(
        {"batch": batch_id, "context": context_key, "payload": payload, "record": ident}
    )


WHITELIST = ["title", "category", "instructor", "start_date", "price", "currency"]
HASH_VERSION = "h1"

REC_A = {"title": "项目A", "category": "理工科", "price": "12000"}
REC_B = {"title": "项目B", "category": "理工科", "price": "13500"}
REC_C = {"title": "项目C", "category": "商科", "price": "9800"}

identity = identity_key("jisi_future_sou_tools", "JS-001")
payload = {
    name: payload_hash(rec, WHITELIST, HASH_VERSION)
    for name, rec in (("A", REC_A), ("B", REC_B), ("C", REC_C))
}

cases = {
    "algorithm": {
        "canonical_json": "utf-8, sort_keys=True, ensure_ascii=False, separators(',',':')",
        "identity": "canonical_json of object {native_id, source}; string_exact, no numeric coercion",
        "payload_hash": "sha256(canonical_json({business: whitelisted fields present in record, hash_version}))",
        "observation_key": "canonical_json of object {batch, context, payload, record}",
        "projection_rules": [
            "projection comes from the observation with the greatest known order key",
            "distinct payloads sharing the greatest order key => status conflict; projection falls back to the latest order key that has a single payload, else unresolved",
            "observations with unknown order never change the projection; they are history only",
            "arrival order of batches/rows never decides the winner",
        ],
        "whitelist": WHITELIST,
        "hash_version": HASH_VERSION,
    },
    "ab_a": {
        "identity": identity,
        "sequence": [
            {"order_key": "t1", "payload": payload["A"]},
            {"order_key": "t2", "payload": payload["B"]},
            {"order_key": "t3", "payload": payload["A"]},
        ],
        "expected": {
            "observations_retained": 3,
            "projection_payload": payload["A"],
            "status": "ok",
        },
    },
    "six_orderings": {
        "batches": [
            {"batch_id": "b1", "order_key": "t1", "payload": payload["A"]},
            {"batch_id": "b2", "order_key": "t2", "payload": payload["B"]},
            {"batch_id": "b3", "order_key": "t3", "payload": payload["C"]},
        ],
        "expected": {
            "projection_payload": payload["C"],
            "status": "ok",
            "permutations_all_identical": True,
        },
    },
    "same_order_conflict": {
        "sequence": [
            {"order_key": "t1", "payload": payload["A"]},
            {"order_key": "t2", "payload": payload["B"]},
            {"order_key": "t3", "payload": payload["B"]},
            {"order_key": "t3", "payload": payload["C"]},
        ],
        "expected": {
            "status": "conflict",
            "projection_payload": payload["B"],
            "conflict_payloads": [payload["B"], payload["C"]],
            "observations_retained": 4,
        },
    },
    "unknown_order": {
        "sequence": [
            {"order_key": "t1", "payload": payload["A"]},
            {"order_key": None, "payload": payload["C"]},
        ],
        "expected": {
            "status": "ok",
            "projection_payload": payload["A"],
            "observations_retained": 2,
        },
    },
    "id_separator": {
        "with_pipe": identity_key("src", "a|b"),
        "parts_concat": identity_key("src", "a") + "|" + identity_key("src", "b"),
        "expected": {
            "with_pipe_not_equal_parts_concat": True,
            "round_trip_native_id": "a|b",
        },
    },
    "zero_padding": {
        "zero": identity_key("src", "0"),
        "padded": identity_key("src", "001"),
        "expected": {"distinct": True, "no_numeric_coercion": True},
    },
    "unicode": {
        "record": {"title": "-café 项目🎯", "category": "人文社科7-9"},
        "expected": {
            "digest": payload_hash(
                {"title": "-café 项目🎯", "category": "人文社科7-9"},
                WHITELIST,
                HASH_VERSION,
            ),
            "repeat_stable": True,
        },
    },
    "field_states": {
        "record_value": {"price": "12000"},
        "record_explicitly_empty": {"price": None},
        "record_not_provided": {},
        "expected": {
            "states": {"price": "value", "title": "not_provided"},
            "explicit_empty_price": "explicitly_empty",
            "failed_price": "extraction_failed",
            "distinct_triples": True,
        },
    },
    "hash_exclusion": {
        "with_noise": payload_hash(
            {
                **REC_A,
                "crawled_at": "2026-06-02T07:52:16Z",
                "local_path": "/tmp/x.jsonl",
                "processing_log": "step1",
            },
            WHITELIST,
            HASH_VERSION,
        ),
        "expected": {"equals_plain_payload_A": payload["A"]},
    },
    "hash_version_bump": {
        "h1": payload_hash(REC_A, WHITELIST, "h1"),
        "h2": payload_hash(REC_A, WHITELIST, "h2"),
        "expected": {"distinct": True},
    },
    "manifest": {
        "manifest": {
            "contract_version": "1",
            "batch_id": "batch-001",
            "source_code": "jisi_future_sou_tools",
            "capture_mode": "full",
            "captured_at": "2026-06-02T07:52:16Z",
            "observed_order": "unknown",
            "coverage": "complete",
            "adapter_version": "a1",
            "mapping_version": "m1",
            "hash_version": "h1",
            "scope": {"entry": "sou_tools"},
            "input_files": [
                {
                    "relative_path": "processed/records.jsonl",
                    "sha256": "ab" * 32,
                    "byte_size": 10,
                    "row_count": 1,
                    "format": "jsonl",
                    "role": "fact",
                }
            ],
        },
        "expected": {
            "manifest_digest": None,
            "same_batch_other_digest_rejected": True,
            "transformation_run_on_new_adapter_distinct": True,
            "capture_event_unchanged": True,
        },
    },
}
cases["manifest"]["expected"]["manifest_digest"] = digest(
    canonical_json(cases["manifest"]["manifest"])
)
m2 = dict(cases["manifest"]["manifest"], coverage="partial")
cases["manifest"]["expected"]["other_digest"] = digest(canonical_json(m2))

out = Path(__file__).with_name("golden")
out.mkdir(exist_ok=True)
(out / "t02_expectations.json").write_text(
    json.dumps(cases, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print("golden frozen:", out / "t02_expectations.json")
print(
    "sha256:", hashlib.sha256((out / "t02_expectations.json").read_bytes()).hexdigest()
)
