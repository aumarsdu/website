"""T10 current projection with manual overrides and rebuild consistency.

Projection semantics: the current value of a field comes from the committed
observation stream (T02/T09 semantics); manual overrides live in a separate
ledger and are shown alongside source values, never replacing them in place.
Withdrawing an override restores the source value and keeps the audit trail.
`rebuild_consistency` recomputes currents from history + ledger and must match
the stored online pointers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import contract
import pg_candidate
from contract import resolve_projection

SIDE = Path(__file__).resolve().parent


class ProjectionError(ValueError):
    """The projection request violated a boundary."""


def _dquote(value: str) -> str:
    if "$$" in value:
        raise ProjectionError("contract_invalid")
    return f"$${value}$$"


def apply_override(
    database: str,
    entity_kind: str,
    entity_id: int,
    field_name: str,
    old_value: str | None,
    new_value: str,
    basis_version: str,
    reason: str,
    author: str,
) -> int:
    """Record a manual override; the source layer stays untouched."""
    if entity_kind not in ("source_record", "provider_project", "offering"):
        raise ProjectionError("contract_invalid")
    table = {
        "source_record": ("source_records", "source_record_id"),
        "provider_project": ("provider_projects", "provider_project_id"),
        "offering": ("offerings", "offering_id"),
    }[entity_kind]
    exists = pg_candidate.psql(
        database,
        f"SELECT count(*) FROM {table[0]} WHERE {table[1]} = {entity_id};",
    ).stdout.strip()
    if exists == "0":
        raise ProjectionError("reference_missing")
    pg_candidate.psql(
        database,
        "INSERT INTO manual_overrides (entity_kind, entity_id, field_name, "
        "old_value, new_value, basis_version, reason, author) VALUES ("
        f"{_dquote(entity_kind)}, {entity_id}, {_dquote(field_name)}, "
        f"{_dquote(old_value) if old_value is not None else 'NULL'}, "
        f"{_dquote(new_value)}, {_dquote(basis_version)}, "
        f"{_dquote(reason)}, {_dquote(author)});",
    )
    override_id = int(
        pg_candidate.psql(
            database, "SELECT max(override_id) FROM manual_overrides;"
        ).stdout.strip()
    )
    return override_id


def withdraw_override(database: str, override_id: int, author: str) -> None:
    """Revoke an override by audit reference; rows are never deleted."""
    rows = pg_candidate.psql(
        database,
        f"SELECT count(*) FROM manual_overrides WHERE override_id = {override_id} "
        f"AND reverted_by IS NULL;",
    ).stdout.strip()
    if rows == "0":
        raise ProjectionError("reference_missing")
    pg_candidate.psql(
        database,
        f"INSERT INTO manual_overrides (entity_kind, entity_id, field_name, "
        f"old_value, new_value, basis_version, reason, author, reverted_by) "
        f"SELECT entity_kind, entity_id, field_name, new_value, old_value, "
        f"basis_version, 'withdraw audit', author, {int(override_id)} "
        f"FROM manual_overrides WHERE override_id = {override_id};",
    )
    pg_candidate.psql(
        database,
        f"UPDATE manual_overrides SET reverted_by = (SELECT max(override_id) "
        f"FROM manual_overrides) WHERE override_id = {override_id};",
    )


def project_record(database: str, identity_key: str) -> dict[str, Any]:
    """Current projection for one source record: source vs manual, coexisting.

    winner_payload is the payload hash the recomputed pointer must carry, so
    rebuild_consistency can detect pointer drift, not just status drift.
    """
    ident = _dquote(identity_key)
    rows = pg_candidate.psql(
        database,
        f"SELECT o.order_key, p.payload_hash, o.observation_id "
        f"FROM observations o "
        f"JOIN content_payloads p ON p.payload_id = o.payload_id "
        f"JOIN source_records r ON r.source_record_id = o.source_record_id "
        f"WHERE r.identity_key = {ident} AND o.order_key IS NOT NULL "
        f"ORDER BY o.order_key;",
    ).stdout
    observations = []
    for line in rows.splitlines():
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
    projection = resolve_projection(
        [{"order_key": o["order_key"], "payload": o["payload"]} for o in observations]
    )
    source_value = None
    if projection["payload"] is not None:
        payload = _dquote(projection["payload"])
        match = pg_candidate.psql(
            database,
            f"SELECT b.business ->> 'title' FROM content_payload_bodies b "
            f"JOIN content_payloads p ON p.payload_id = b.payload_id "
            f"WHERE p.payload_hash = {payload};",
        ).stdout.strip()
        source_value = match or None
    overrides = []
    for line in pg_candidate.psql(
        database,
        f"SELECT override_id, field_name, new_value, author, reverted_by "
        f"FROM manual_overrides WHERE entity_kind = 'source_record' AND "
        f"entity_id = (SELECT source_record_id FROM source_records "
        f"WHERE identity_key = {ident}) ORDER BY override_id;",
    ).stdout.splitlines():
        if "|" not in line:
            continue
        override_id, field_name, new_value, author, reverted = line.split("|", 4)
        overrides.append(
            {
                "override_id": int(override_id),
                "field_name": field_name,
                "new_value": new_value,
                "author": author,
                "active": reverted in ("", "NULL", "\\N"),
            }
        )
    active_override = next(
        (o for o in overrides if o["active"] and o["field_name"] == "title"), None
    )
    return {
        "identity_key": identity_key,
        "source_status": projection["status"],
        "winner_payload": projection["payload"],
        "source_value": source_value,
        "manual_overrides": overrides,
        "active_manual_value": active_override["new_value"]
        if active_override
        else None,
        "shown_value": (
            active_override["new_value"] if active_override else source_value
        ),
    }


def rebuild_consistency(database: str) -> dict[str, Any]:
    """Recompute currents from history; report mismatches against stored state.

    A record whose observations all lack a known order key legitimately has
    no stored pointer (absent) — that is equivalent to an unresolved current
    and is not a mismatch. When the recomputed status is ok/conflict with a
    known winner payload, the stored pointer's payload must match it.
    """
    mismatches: list[dict[str, Any]] = []
    identities = [
        line
        for line in pg_candidate.psql(
            database, "SELECT DISTINCT identity_key FROM source_records;"
        ).stdout.splitlines()
        if line.strip()
    ]
    for identity in identities:
        recomputed = project_record(database, identity)
        stored = pg_candidate.psql(
            database,
            f"SELECT c.status, p.payload_hash FROM source_record_current c "
            f"JOIN source_records r ON r.source_record_id = c.source_record_id "
            f"JOIN observations o ON o.observation_id = c.observation_id "
            f"JOIN content_payloads p ON p.payload_id = o.payload_id "
            f"WHERE r.identity_key = {_dquote(identity)};",
        ).stdout.splitlines()
        stored = stored[0] if stored else ""
        stored_status, stored_payload = (
            stored.split("|", 1)
            if "|" in stored
            else (stored if stored else "absent", None)
        )
        if stored_status == "absent" or not stored:
            stored_status = "absent"
            stored_payload = None
        recomputed_status = recomputed["source_status"]
        if recomputed_status == "unresolved" and stored_status == "absent":
            continue
        if recomputed_status == "unresolved" and stored_status == "unresolved":
            continue
        if stored_status != recomputed_status:
            mismatches.append(
                {
                    "identity_key": identity,
                    "stored": stored_status,
                    "recomputed": recomputed_status,
                    "kind": "status",
                }
            )
            continue
        if (
            recomputed_status == "ok"
            and recomputed["winner_payload"] is not None
            and stored_payload != recomputed["winner_payload"]
        ):
            mismatches.append(
                {
                    "identity_key": identity,
                    "stored": stored_status,
                    "recomputed": recomputed_status,
                    "kind": "pointer_drift",
                }
            )
    return {
        "identities": len(identities),
        "mismatches": mismatches,
        "consistent": not mismatches,
    }


def not_seen_report(database: str, batch_id: str) -> list[dict[str, Any]]:
    """Flag records missing from a complete snapshot as not_seen (P2 issue).

    Missing records keep their observations and current pointers; only the
    quality queue records the gap.
    """
    coverage = pg_candidate.psql(
        database,
        f"SELECT coverage FROM ingest_batches WHERE batch_id = {_dquote(batch_id)};",
    ).stdout.strip()
    if coverage != "complete":
        raise ProjectionError("not_a_complete_snapshot")
    source_code = pg_candidate.psql(
        database,
        f"SELECT s.source_code FROM ingest_batches b "
        f"JOIN sources s USING (source_id) WHERE b.batch_id = {_dquote(batch_id)};",
    ).stdout.strip()
    in_batch = set(
        pg_candidate.psql(
            database,
            f"SELECT DISTINCT r.identity_key FROM observations o "
            f"JOIN source_records r USING (source_record_id) "
            f"JOIN ingest_batches b USING (batch_id) "
            f"WHERE b.batch_id = {_dquote(batch_id)};",
        ).stdout.splitlines()
    )
    missing = [
        line
        for line in pg_candidate.psql(
            database,
            f"SELECT DISTINCT r.identity_key FROM observations o "
            f"JOIN source_records r ON r.source_record_id = o.source_record_id "
            f"JOIN ingest_batches b ON b.batch_id = o.batch_id "
            f"JOIN sources s ON s.source_id = b.source_id "
            f"WHERE s.source_code = {_dquote(source_code)} "
            f"AND b.batch_id <> {_dquote(batch_id)};",
        ).stdout.splitlines()
        if line.strip() and line not in in_batch
    ]
    for identity in missing:
        pg_candidate.psql(
            database,
            f"INSERT INTO quality_issues (entity_kind, entity_id, severity, "
            f"description) SELECT 'source_record', r.source_record_id, 'P2', "
            f"{_dquote('not_seen_in_complete_batch:' + batch_id)} "
            f"FROM source_records r WHERE r.identity_key = {_dquote(identity)} "
            f"AND NOT EXISTS (SELECT 1 FROM quality_issues q "
            f"WHERE q.entity_kind = 'source_record' "
            f"AND q.entity_id = r.source_record_id "
            f"AND q.description = {_dquote('not_seen_in_complete_batch:' + batch_id)});",
        )
    return [
        {"identity_key": identity, "issue": "not_seen_in_complete_batch:" + batch_id}
        for identity in missing
    ]


def not_seen_run_report(
    database: str,
    source_code: str,
    baseline_input: str | None = None,
    *,
    registry: dict[str, Any] | None = None,
    staging_root: Path | None = None,
) -> dict[str, Any]:
    """Run-granularity not-seen report (R3): identities in the database that
    the source's latest complete refresh run does not contain.

    A run is one registered input file of the source. Only full_refresh runs
    (path marker) and single-input sources (the sole file is complete by
    definition) may serve as the baseline; incremental runs only ever add
    records, so using one as a baseline is rejected. The report is read-only:
    suspected disappearances are listed, never written back as states.

    Per-input identity sets come from the sealed migration staging rows
    (candidate_data/full_migration_1), mapped to input files by cumulative
    registry unit counts in registry order.
    """
    registry_data: dict[str, Any] = registry or json.loads(
        (SIDE / "source_registry.json").read_text(encoding="utf-8")
    )
    source = next(
        (s for s in registry_data["sources"] if s["source_code"] == source_code), None
    )
    if source is None:
        raise ProjectionError("unknown_source")
    inputs = source["inputs"]
    staging_root = staging_root or SIDE / "candidate_data" / "full_migration_1"

    def run_type(entry: dict[str, Any]) -> str:
        relative = entry["relative_path"]
        if "full_refresh" in relative:
            return "full_refresh"
        if "incremental" in relative:
            return "incremental"
        if len(inputs) == 1:
            return "complete_single_file"
        return "unknown"

    classified = [{**entry, "run_type": run_type(entry)} for entry in inputs]
    if baseline_input is None:
        eligible_positions = [
            position
            for position, entry in enumerate(classified)
            if entry["run_type"] in ("full_refresh", "complete_single_file")
        ]
        if not eligible_positions:
            raise ProjectionError("no_baseline_run")
        baseline_position = eligible_positions[-1]
    else:
        baseline_position = next(
            (
                position
                for position, entry in enumerate(classified)
                if entry["relative_path"] == baseline_input
            ),
            None,
        )
        if baseline_position is None:
            raise ProjectionError("unknown_baseline_input")
        if classified[baseline_position]["run_type"] == "incremental":
            raise ProjectionError("incremental_run_not_a_baseline")
        if classified[baseline_position]["run_type"] == "unknown":
            raise ProjectionError("not_a_complete_run")
    baseline = classified[baseline_position]

    # Per-input native-id sets from the sealed staging stream, mapped by
    # cumulative registry unit counts (registry input order == collect order).
    totals = [entry.get("unit_count") for entry in inputs]
    if any(not isinstance(total, int) for total in totals):
        raise ProjectionError("registry_input_missing_unit_count")
    staged_rows = _staged_native_ids(source_code, staging_root)
    single_input = len(inputs) == 1
    if not single_input and len(staged_rows) != sum(totals):
        raise ProjectionError("staging_registry_misaligned")
    per_input: list[set[str]] = [set() for _ in inputs]
    if single_input:
        per_input[0].update(staged_rows)
    else:
        index = 0
        for position, total in enumerate(totals):
            per_input[position].update(staged_rows[index : index + total])
            index += total

    baseline_ids = {
        contract.identity_key(source_code, native)
        for native in per_input[baseline_position]
    }
    # Only sightings in runs NEWER than the baseline prove aliveness: a
    # record present in an older refresh but dropped from the baseline is
    # exactly the disappearance this report exists to surface.
    sighted_after: set[str] = set()
    for position in range(baseline_position + 1, len(inputs)):
        sighted_after |= {
            contract.identity_key(source_code, native) for native in per_input[position]
        }

    in_db = set(
        pg_candidate.psql(
            database,
            f"SELECT r.identity_key FROM source_records r "
            f"JOIN sources s USING (source_id) "
            f"WHERE s.source_code = {_dquote(source_code)};",
        ).stdout.splitlines()
    ) - {""}
    not_in_baseline = sorted(in_db - baseline_ids)
    return {
        "source_code": source_code,
        "baseline_input": baseline["relative_path"],
        "baseline_run_type": baseline["run_type"],
        "baseline_unit_count": baseline["unit_count"],
        "baseline_staged_rows": len(per_input[baseline_position]),
        "db_identities": len(in_db),
        "not_seen_in_baseline": not_in_baseline,
        "not_seen_count": len(not_in_baseline),
        "sighted_after_baseline": sorted(
            identity for identity in not_in_baseline if identity in sighted_after
        ),
        "not_sighted_after_baseline": sorted(
            identity for identity in not_in_baseline if identity not in sighted_after
        ),
        "later_runs": [
            entry["relative_path"] for entry in classified[baseline_position + 1 :]
        ],
        "incremental_note": "增量运行仅含新增，不具全集语义，不作为基准（显式排除）；嫌疑分桶只认基准之后的运行 sighting",
        "readonly": True,
    }


def _staged_native_ids(source_code: str, staging_root: Path) -> list[str]:
    """Native ids of one source from sealed migration staging, batch order.

    Splits on \\n only: splitlines() would also break on bare U+2028/U+2029
    inside JSON strings and silently misalign the run mapping.
    """
    rows: list[str] = []
    for directory in sorted(staging_root.glob(f"{source_code}-*")):
        records = directory / "staging" / "records.jsonl"
        if not records.is_file():
            continue
        for line in records.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                rows.append(str(json.loads(line)["id"]))
    return rows


def quality_queue(database: str) -> list[dict[str, Any]]:
    """Open quality items: recorded conflicts, open quality issues and
    candidate identities awaiting independent confirmation (R5)."""
    queue: list[dict[str, Any]] = []
    for line in pg_candidate.psql(
        database,
        "SELECT conflict_id, source_record_id, order_key FROM conflicts "
        "ORDER BY conflict_id;",
    ).stdout.splitlines():
        if "|" in line:
            conflict_id, record_id, order_key = line.split("|", 2)
            queue.append(
                {
                    "kind": "conflict",
                    "conflict_id": int(conflict_id),
                    "source_record_id": int(record_id),
                    "order_key": order_key,
                }
            )
    for line in pg_candidate.psql(
        database,
        "SELECT issue_id, entity_kind, entity_id, severity, description "
        "FROM quality_issues WHERE status = 'open' ORDER BY issue_id;",
    ).stdout.splitlines():
        if "|" in line:
            issue_id, kind, entity_id, severity, description = line.split("|", 4)
            queue.append(
                {
                    "kind": "quality_issue",
                    "issue_id": int(issue_id),
                    "entity_kind": kind,
                    "entity_id": int(entity_id),
                    "severity": severity,
                    "description": description,
                }
            )
    for line in pg_candidate.psql(
        database,
        "SELECT r.source_record_id, s.source_code, r.identity_key, "
        "COALESCE(c.status, 'absent') FROM source_records r "
        "JOIN sources s USING (source_id) "
        "LEFT JOIN source_record_current c USING (source_record_id) "
        "WHERE r.identity_status = 'candidate' "
        "ORDER BY s.source_code, r.source_record_id;",
    ).stdout.splitlines():
        if "|" in line:
            record_id, source, identity, status = line.split("|", 3)
            queue.append(
                {
                    "kind": "identity_candidate",
                    "source_record_id": int(record_id),
                    "source_code": source,
                    "identity_key": identity,
                    "current_status": status,
                }
            )
    return queue
