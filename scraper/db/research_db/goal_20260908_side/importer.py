"""T09 idempotent importer: accepts only T08-sealed batches, writes the
candidate model in one transaction per batch, and reports counts from
committed state only.

Concurrency: pg_advisory_xact_lock(batch_id) serializes same-batch imports;
the loser observes a clean unchanged replay. Batch-id reuse with a different
manifest digest raises identity_conflict. Current pointers follow the T02
contract projection (contract.resolve_projection): old batches never regress
and same-order payload conflicts land in the conflicts queue. Manual override
rows are never touched.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pg_candidate
from contract import manifest_digest, resolve_projection

MAX_BATCH_ROWS = 500


class ImportError_(ValueError):
    """The sealed batch cannot be imported."""


def _dquote(value: str) -> str:
    if "$$" in value:
        raise ImportError_("contract_invalid")
    return f"$${value}$$"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _load_sealed(sealed_dir: Path, staging_dir: Path) -> tuple[dict, list[dict], dict]:
    seal_path = sealed_dir / "seal.json"
    batch_path = sealed_dir / "batch.jsonl"
    manifest_path = staging_dir / "manifest.json"
    for path in (seal_path, batch_path, manifest_path):
        if not path.is_file():
            raise ImportError_("seal_invalid")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    for key in (
        "batch_id",
        "manifest_digest",
        "batch_sha256",
        "validator_version",
        "source_code",
        "hash_version",
        "contract_version",
    ):
        if key not in seal:
            raise ImportError_("seal_invalid")
    if seal["validator_version"] != "t08-v1":
        raise ImportError_("seal_invalid")
    if _sha256_file(batch_path) != seal["batch_sha256"]:
        raise ImportError_("input_changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest_digest(manifest) != seal["manifest_digest"]:
        raise ImportError_("input_changed")
    if manifest["batch_id"] != seal["batch_id"]:
        raise ImportError_("identity_conflict")
    rows = [
        json.loads(line)
        for line in batch_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) > MAX_BATCH_ROWS:
        raise ImportError_("batch_too_large")
    for row in rows:
        source, _native = _identity_parts(row["identity_key"])
        if source != seal["source_code"]:
            raise ImportError_("seal_invalid")
    return seal, rows, manifest


def _committed_counts(database: str, batch_id: str) -> dict[str, int]:
    result = pg_candidate.psql(
        database,
        "SELECT "
        f"(SELECT count(*) FROM observations WHERE batch_id = {_dquote(batch_id)}), "
        "(SELECT count(*) FROM source_records), "
        "(SELECT count(*) FROM content_payloads), "
        "(SELECT count(*) FROM conflicts);",
    )
    obs, records, payloads, conflicts = result.stdout.strip().split("|")
    return {
        "observations": int(obs),
        "source_records": int(records),
        "content_payloads": int(payloads),
        "conflicts": int(conflicts),
    }


def _identity_parts(identity_key: str) -> tuple[str, str]:
    parsed = json.loads(identity_key)
    return str(parsed["source"]), str(parsed["native_id"])


def _sql_for_batch(
    seal: dict, rows: list[dict], coverage: str, candidate_identities: bool
) -> str:
    """One transaction: lock, read before-counts, upsert rows, commit.

    The before-counts SELECT runs inside the transaction AFTER the advisory
    lock, so concurrent waiters read post-winner totals (receipt honesty)."""
    source_code = seal["source_code"]
    batch_id = seal["batch_id"]
    digest = seal["manifest_digest"]
    hash_version = seal["hash_version"]
    contract_version = str(seal.get("contract_version", "1"))
    parts = ["BEGIN;", f"SELECT pg_advisory_xact_lock(hashtext({_dquote(batch_id)}));"]
    parts.append(
        "SELECT (SELECT count(*) FROM observations WHERE batch_id = "
        + _dquote(batch_id)
        + "), (SELECT count(*) FROM source_records), "
        "(SELECT count(*) FROM content_payloads), "
        "(SELECT count(*) FROM conflicts);"
    )
    parts.append(
        f"INSERT INTO providers (provider_name) SELECT {_dquote(source_code)} "
        f"WHERE NOT EXISTS (SELECT 1 FROM providers WHERE provider_name = "
        f"{_dquote(source_code)});"
    )
    parts.append(
        f"INSERT INTO sources (source_code, provider_id, namespace) "
        f"SELECT {_dquote(source_code)}, (SELECT provider_id FROM providers "
        f"WHERE provider_name = {_dquote(source_code)}), {_dquote(source_code)} "
        f"WHERE NOT EXISTS (SELECT 1 FROM sources WHERE source_code = "
        f"{_dquote(source_code)});"
    )
    parts.append(
        f"DO $batch$ DECLARE existing text; BEGIN "
        f"INSERT INTO ingest_batches (batch_id, source_id, manifest_digest, "
        f"contract_version, capture_mode, captured_at, observed_order, coverage, "
        f"adapter_version, mapping_version, hash_version) "
        f"SELECT {_dquote(batch_id)}, s.source_id, {_dquote(digest)}, "
        f"{_dquote(contract_version)}, 'full', now(), NULL, "
        f"{_dquote(coverage)}, "
        f"'t09', 't09', {_dquote(hash_version)} "
        f"FROM sources s WHERE s.source_code = {_dquote(source_code)} "
        f"ON CONFLICT (batch_id) DO NOTHING; "
        f"SELECT manifest_digest INTO existing FROM ingest_batches "
        f"WHERE batch_id = {_dquote(batch_id)}; "
        f"IF existing IS NULL OR existing <> {_dquote(digest)} THEN "
        f"RAISE EXCEPTION 'identity_conflict: batch_id reuse with different manifest digest'; "
        f"END IF; END $batch$;"
    )
    for row in rows:
        source, _native = _identity_parts(row["identity_key"])
        ident = _dquote(row["identity_key"])
        payload = _dquote(row["payload_hash"])
        context = _dquote(row.get("context_key", "default"))
        order = _dquote(row["order_key"]) if row.get("order_key") else "NULL"
        status = "candidate" if candidate_identities else "confirmed"
        parts.append(
            f"INSERT INTO source_records (source_id, identity_key, "
            f"identity_status) SELECT s.source_id, {ident}, "
            f"{_dquote(status)} FROM sources s "
            f"WHERE s.source_code = {_dquote(source)} "
            f"ON CONFLICT (source_id, identity_key) DO NOTHING;"
        )
        parts.append(
            f"INSERT INTO content_payloads (payload_hash, hash_version) "
            f"VALUES ({payload}, {_dquote(hash_version)}) "
            f"ON CONFLICT (payload_hash, hash_version) DO NOTHING;"
        )
        business = json.dumps(row.get("business", {}), ensure_ascii=False)
        states = json.dumps(row.get("field_states", {}), ensure_ascii=False)
        if "$$" in business or "$$" in states:
            raise ImportError_("contract_invalid")
        parts.append(
            f"INSERT INTO content_payload_bodies (payload_id, business, "
            f"field_states) SELECT p.payload_id, "
            f"$${business}$$::jsonb, $${states}$$::jsonb "
            f"FROM content_payloads p WHERE p.payload_hash = {payload} "
            f"AND p.hash_version = {_dquote(hash_version)} "
            f"ON CONFLICT (payload_id) DO NOTHING;"
        )
        parts.append(
            f"INSERT INTO observations (source_record_id, payload_id, batch_id, "
            f"context_key, order_key, evidence_location) "
            f"SELECT r.source_record_id, p.payload_id, {_dquote(batch_id)}, "
            f"{context}, {order}, {_dquote('sealed:' + batch_id)} "
            f"FROM source_records r, content_payloads p "
            f"WHERE r.identity_key = {ident} "
            f"AND p.payload_hash = {payload} "
            f"AND p.hash_version = {_dquote(hash_version)} "
            f"ON CONFLICT (batch_id, source_record_id, context_key, payload_id) "
            f"DO NOTHING;"
        )
    parts.append("COMMIT;")
    return "\n".join(parts)


def _identity_observations(database: str, identity: str) -> list[dict[str, Any]]:
    ident = _dquote(identity)
    result = pg_candidate.psql(
        database,
        f"SELECT o.order_key, p.payload_hash, o.observation_id "
        f"FROM observations o "
        f"JOIN content_payloads p ON p.payload_id = o.payload_id "
        f"JOIN source_records r ON r.source_record_id = o.source_record_id "
        f"WHERE r.identity_key = {ident} "
        f"ORDER BY o.order_key;",
    )
    observations = []
    for line in result.stdout.splitlines():
        if "|" not in line:
            continue
        order_key, payload_hash, observation_id = line.split("|", 2)
        observations.append(
            {
                "order_key": order_key,
                "payload": payload_hash,
                "observation_id": int(observation_id),
            }
        )
    return observations


def _update_current_pointers(database: str, rows: list[dict]) -> int:
    """Recompute affected identities' current pointers via T02 projection.

    Identities whose observations all lack a known order key get an explicit
    'unresolved' current row: unknown order never pretends to be certain.
    """
    updated = 0
    for identity in sorted({row["identity_key"] for row in rows}):
        observations = _identity_observations(database, identity)
        if not observations:
            continue
        if all(o["order_key"] in ("", "NULL", None) for o in observations):
            ident = _dquote(identity)
            first = observations[0]["observation_id"]
            pg_candidate.psql(
                database,
                "INSERT INTO source_record_current (source_record_id, "
                "observation_id, status) SELECT source_record_id, "
                f"{first}, 'unresolved' FROM source_records "
                f"WHERE identity_key = {ident} "
                "ON CONFLICT (source_record_id) DO UPDATE SET "
                "status = 'unresolved';",
            )
            updated += 1
            continue
        projection = resolve_projection(
            [
                {"order_key": o["order_key"], "payload": o["payload"]}
                for o in observations
            ]
        )
        by_slot = {
            (o["order_key"], o["payload"]): o["observation_id"] for o in observations
        }
        top_key = max(
            (o["order_key"] for o in observations if o["order_key"]), default=None
        )
        if projection["payload"] is not None:
            candidates = [
                oid
                for (key, payload), oid in by_slot.items()
                if payload == projection["payload"]
            ]
            pointer_id = max(candidates) if candidates else None
        else:
            top_observations = [o for o in observations if o["order_key"] == top_key]
            pointer_id = (
                top_observations[0]["observation_id"] if top_observations else None
            )
        if pointer_id is None:
            continue
        ident = _dquote(identity)
        pg_candidate.psql(
            database,
            f"INSERT INTO source_record_current (source_record_id, observation_id, "
            f"status) SELECT source_record_id, {_dquote(str(pointer_id))}, "
            f"{_dquote(projection['status'])} FROM source_records "
            f"WHERE identity_key = {ident} "
            f"ON CONFLICT (source_record_id) DO UPDATE SET "
            f"observation_id = EXCLUDED.observation_id, "
            f"status = EXCLUDED.status "
            f"WHERE (SELECT order_key FROM observations WHERE observation_id = "
            f"source_record_current.observation_id) IS NULL "
            f"OR (SELECT order_key FROM observations WHERE observation_id = "
            f"source_record_current.observation_id) <= "
            f"(SELECT order_key FROM observations "
            f"WHERE observation_id = EXCLUDED.observation_id);",
        )
        updated += 1
        if projection["status"] == "conflict":
            pg_candidate.psql(
                database,
                f"INSERT INTO conflicts (source_record_id, order_key) "
                f"SELECT source_record_id, {_dquote(str(top_key))} "
                f"FROM source_records WHERE identity_key = {ident} "
                f"AND NOT EXISTS (SELECT 1 FROM conflicts c "
                f"WHERE c.source_record_id = source_records.source_record_id "
                f"AND c.order_key = {_dquote(str(top_key))});",
            )
    return updated


def _batch_digest_mismatch(database: str, batch_id: str, digest: str) -> bool:
    """True when batch_id exists with a different manifest digest."""
    result = pg_candidate.psql(
        database,
        f"SELECT count(*) FROM ingest_batches "
        f"WHERE batch_id = {_dquote(batch_id)} "
        f"AND manifest_digest <> {_dquote(digest)};",
    )
    return result.stdout.strip() != "0"


def import_sealed(
    staging_dir: Path,
    sealed_dir: Path,
    database: str,
    max_rows: int = MAX_BATCH_ROWS,
) -> dict[str, Any]:
    """Import one T08-sealed batch; receipt counts come from committed state."""
    run_id = str(uuid.uuid4())
    try:
        seal, rows, manifest = _load_sealed(sealed_dir, staging_dir)
        if len(rows) > max_rows:
            raise ImportError_("batch_too_large")
    except (ImportError_, json.JSONDecodeError, UnicodeError) as exc:
        return {
            "run_id": run_id,
            "batch_id": None,
            "status": "failed",
            "error": str(exc),
            "counts": {},
        }
    batch_id = seal["batch_id"]
    pg_candidate.init_cluster()
    if not pg_candidate.database_exists(database):
        pg_candidate.create_database(database)
    # structured pre-check: batch-id reuse detected before any transaction
    if _batch_digest_mismatch(database, batch_id, seal["manifest_digest"]):
        return {
            "run_id": run_id,
            "batch_id": batch_id,
            "status": "failed",
            "error": "identity_conflict",
            "counts": {},
        }
    sql = _sql_for_batch(
        seal,
        rows,
        str(manifest.get("coverage", "unknown")),
        bool(manifest.get("scope", {}).get("candidate_identities")),
    )
    try:
        # the before-counts line is selected INSIDE the transaction, after the
        # advisory lock, so concurrent waiters read post-winner totals
        output = pg_candidate.psql(database, sql).stdout
    except pg_candidate.ClusterError as exc:
        after = _committed_counts(database, batch_id)
        if after["observations"] == 0:
            return {
                "run_id": run_id,
                "batch_id": batch_id,
                "status": "failed",
                "error": f"transaction_failed: {str(exc)[-200:]}",
                "counts": {},
            }
        return {
            "run_id": run_id,
            "batch_id": batch_id,
            "status": "committed",
            "error": "commit_unknown_resolved_by_requery",
            "counts": {
                "rows_read": len(rows),
                "inserted_observations": min(after["observations"], len(rows)),
                "unchanged_observations": max(0, len(rows) - after["observations"]),
                "failed": 0,
            },
        }
    before_line = next((line for line in output.splitlines() if line.strip()), "")
    before_values = before_line.split("|")
    before = {
        "observations": int(before_values[0]),
        "source_records": int(before_values[1]),
        "content_payloads": int(before_values[2]),
    }
    pointer_error = None
    try:
        pointer_updates = _update_current_pointers(database, rows)
    except pg_candidate.ClusterError as exc:
        pointer_updates = 0
        pointer_error = f"pointer_update_failed: {str(exc)[-200:]}"
    after = _committed_counts(database, batch_id)
    inserted = after["observations"] - before["observations"]
    receipt = {
        "run_id": run_id,
        "batch_id": batch_id,
        "status": "committed",
        "error": pointer_error,
        "counts": {
            "rows_read": len(rows),
            "inserted_observations": inserted,
            "unchanged_observations": len(rows) - inserted,
            "inserted_source_records": after["source_records"]
            - before["source_records"],
            "inserted_payloads": after["content_payloads"] - before["content_payloads"],
            "current_pointer_updates": pointer_updates,
            "failed": 0,
        },
    }
    return receipt
