"""R6-B Option A switch driver: build research_projects_candidate on the
legacy cluster (/tmp:55432) by redirecting the verified tooling connection,
apply migrations 0001-0003, import the 24 sealed batches, then verify.

Runbook: evidence/switch_runbook.md; authorization: Owner receipt (Option A).
Window discipline: single writer; legacy research_projects_clean untouched.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pg_candidate

# Option A: target = new candidate database on the legacy cluster.
pg_candidate.HOST = "/tmp"
pg_candidate.PORT = 55432
pg_candidate.SUPERUSER = "research_ops"

DB = "research_projects_candidate"
SIDE = Path(__file__).resolve().parent
STATE = Path("/tmp/r6b_driver_state.json")

EXPECTED_DIGEST = "e05ebc98123cee35636d805c19e2318986a367be1ad83ca80d9b0c382205d44e"
EXPECTED_COUNTS = {
    "sources": 6,
    "source_records": 7972,
    "observations": 9453,
    "content_payloads": 5181,
    "content_payload_bodies": 5181,
    "ingest_batches": 24,
    "source_record_current": 7972,
}


def save_state(step: str, data: dict) -> None:
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    state[step] = data
    STATE.write_text(json.dumps(state, indent=2))


def main() -> int:
    started = time.perf_counter()
    save_state("window", {"opened_at": "2026-09-28", "budget_seconds": 7200})

    if pg_candidate.database_exists(DB):
        pg_candidate.drop_database(DB)
        save_state("recreate", {"dropped_preexisting": True})
    pg_candidate.create_database(DB)
    save_state("recreate", {"created": DB})
    print("created", DB, flush=True)

    import run_migrations

    exit_code = run_migrations.run(DB, SIDE / "migrations", sys.stdout)
    if exit_code != run_migrations.EXIT_OK:
        raise SystemExit(f"migrations failed: exit {exit_code}")
    bridge = pg_candidate.psql(
        DB, "SELECT legacy_replica_present, migrated_counts FROM legacy_bridge_status;"
    ).stdout.strip()
    save_state("migrations", {"exit_ok": True, "bridge_status": bridge})
    print("migrations applied; bridge:", bridge, flush=True)

    import importer

    receipts = []
    batch_dirs = sorted(
        d for d in (SIDE / "candidate_data" / "full_migration_1").iterdir() if d.is_dir()
    )
    for d in batch_dirs:
        staging, sealed = d / "staging", d / "sealed"
        receipt = importer.import_sealed(staging, sealed, DB, max_rows=500)
        if receipt["status"] != "committed":
            raise SystemExit(f"import failed at {d.name}: {receipt}")
        receipts.append(
            {
                "batch": receipt.get("batch_id", d.name),
                "rows": receipt["counts"]["rows_read"],
                "inserted": receipt["counts"]["inserted_observations"],
                "unchanged": receipt["counts"]["unchanged_observations"],
            }
        )
        print("imported", d.name, receipt["counts"], flush=True)
    save_state("imports", {"receipts": receipts, "count": len(receipts)})

    digest_input = pg_candidate.psql(
        DB,
        "SELECT r.identity_key, p.payload_hash, o.order_key, o.context_key "
        "FROM observations o "
        "JOIN content_payloads p ON p.payload_id = o.payload_id "
        "JOIN source_records r ON r.source_record_id = o.source_record_id "
        "ORDER BY 1,2,3,4;",
    ).stdout.splitlines()
    current_map = pg_candidate.psql(
        DB,
        "SELECT r.identity_key, c.status FROM source_record_current c "
        "JOIN source_records r ON r.source_record_id = c.source_record_id "
        "ORDER BY 1;",
    ).stdout.splitlines()
    import hashlib

    digest = hashlib.sha256(
        ("\n".join(sorted(digest_input)) + "\n" + "\n".join(sorted(current_map))).encode()
    ).hexdigest()

    counts = {
        t: int(pg_candidate.psql(DB, f"SELECT count(*) FROM {t};").stdout.strip())
        for t in EXPECTED_COUNTS
    }
    unresolved = int(
        pg_candidate.psql(
            DB, "SELECT count(*) FROM source_record_current WHERE status='unresolved';"
        ).stdout.strip()
    )
    import projection

    consistency = projection.rebuild_consistency(DB)
    verify = {
        "digest": digest,
        "digest_matches": digest == EXPECTED_DIGEST,
        "counts": counts,
        "counts_match": counts == EXPECTED_COUNTS,
        "current_unresolved": unresolved,
        "rebuild_consistency": consistency["consistent"],
        "elapsed_seconds": round(time.perf_counter() - started, 1),
    }
    save_state("verify", verify)
    print(json.dumps(verify, indent=1), flush=True)
    if not (
        verify["digest_matches"]
        and verify["counts_match"]
        and verify["rebuild_consistency"]
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
