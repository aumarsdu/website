"""T02 contract: identity encoding, hash projection, field states, observation keys.

Pure functions only. Expected values are frozen in golden/t02_expectations.json;
this module must reproduce them. Any rule change requires a new hash_version.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from typing import TypedDict


class ContractError(ValueError):
    """A contract input violated the frozen rules."""


CONTRACT_VERSION = "1"

REQUIRED_MANIFEST_FIELDS = (
    "contract_version",
    "batch_id",
    "source_code",
    "input_files",
    "scope",
    "capture_mode",
    "captured_at",
    "observed_order",
    "coverage",
    "adapter_version",
    "mapping_version",
    "hash_version",
)

FIELD_STATES = ("value", "explicitly_empty", "not_provided", "extraction_failed")


def canonical_json(value: object) -> str:
    """Utf-8 canonical JSON: sorted keys, no spaces, non-ASCII preserved."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def identity_key(source_code: str, native_id: str) -> str:
    """Unambiguous identity tuple; native_id stays an exact string (0 != 00)."""
    return canonical_json({"native_id": native_id, "source": source_code})


def payload_hash(
    record: Mapping[str, object], whitelist: Sequence[str], hash_version: str
) -> str:
    """Deterministic business hash over whitelisted fields only."""
    business = {key: record[key] for key in whitelist if key in record}
    canonical = canonical_json({"business": business, "hash_version": hash_version})
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def field_state(record: Mapping[str, object], key: str, *, failed: bool = False) -> str:
    """Distinguish value / explicitly_empty / not_provided / extraction_failed."""
    if failed:
        return "extraction_failed"
    if key not in record:
        return "not_provided"
    if record[key] is None:
        return "explicitly_empty"
    return "value"


def observation_key(batch_id: str, ident: str, context_key: str, payload: str) -> str:
    """Idempotent observation identity: batch+record+context+payload."""
    return canonical_json(
        {"batch": batch_id, "context": context_key, "payload": payload, "record": ident}
    )


class Observation(TypedDict):
    payload: str
    order_key: str | None


class ProjectionResult(TypedDict):
    payload: str | None
    status: str
    history_count: int
    conflict_payloads: list[str]


def resolve_projection(observations: Iterable[Observation]) -> ProjectionResult:
    """Trusted-order projection; arrival order and unknown order never win."""
    items = list(observations)
    known: dict[str, list[str]] = {}
    for item in items:
        key = item["order_key"]
        if key is not None:
            known.setdefault(key, []).append(item["payload"])
    fallback: str | None = None
    for key in sorted(known, reverse=True):
        seen: list[str] = []
        for payload in known[key]:
            if payload not in seen:
                seen.append(payload)
        if len(seen) == 1 and fallback is None:
            fallback = seen[0]
    if not known:
        return {
            "payload": None,
            "status": "unresolved",
            "history_count": len(items),
            "conflict_payloads": [],
        }
    top = max(known)
    top_payloads: list[str] = []
    for payload in known[top]:
        if payload not in top_payloads:
            top_payloads.append(payload)
    if len(top_payloads) == 1:
        return {
            "payload": top_payloads[0],
            "status": "ok",
            "history_count": len(items),
            "conflict_payloads": [],
        }
    return {
        "payload": fallback,
        "status": "conflict",
        "history_count": len(items),
        "conflict_payloads": top_payloads,
    }


def manifest_digest(manifest: Mapping[str, object]) -> str:
    """Digest of the immutable batch manifest description."""
    return hashlib.sha256(canonical_json(dict(manifest)).encode("utf-8")).hexdigest()


def validate_manifest(manifest: Mapping[str, object]) -> None:
    """Machine-check the manifest shape before any dependent work."""
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            raise ContractError("contract_invalid")
    if manifest["contract_version"] != CONTRACT_VERSION:
        raise ContractError("contract_invalid")
    if not isinstance(manifest["batch_id"], str) or not manifest["batch_id"]:
        raise ContractError("contract_invalid")
    if not isinstance(manifest["input_files"], list) or not manifest["input_files"]:
        raise ContractError("contract_invalid")


def bind_batch_id(existing: Mapping[str, str], manifest: Mapping[str, object]) -> str:
    """Same batch_id with a different manifest_digest must be rejected."""
    batch_id = str(manifest["batch_id"])
    digest = manifest_digest(manifest)
    if batch_id in existing and existing[batch_id] != digest:
        raise ContractError("identity_conflict")
    return digest


def transformation_run(batch_id: str, adapter_version: str) -> str:
    """Identical bytes re-parsed under a new adapter version form a new run."""
    return canonical_json({"adapter_version": adapter_version, "batch": batch_id})
