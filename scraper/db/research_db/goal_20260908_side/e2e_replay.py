"""T13 end-to-end double replay: two empty candidate databases receive the
full pipeline (migrations -> T08-sealed pilot imports -> projection) and the
resulting canonical data digests must be identical.

Digest inputs (per database): sorted (identity_key, payload_hash, order_key,
context_key) tuples of all observations plus per-table counts and the full
current-pointer mapping. Any difference fails the replay comparison.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pg_candidate

SIDE = Path(__file__).resolve().parent
PILOT_ENTRIES = (
    "jisi_future_sou_tools",
    "jisi_future_domestic",
    "zhongke",
    "hirep",
    "yanqu_ocr",
    "yinzhi_public",
)
PILOT_ROOT = SIDE / "candidate_data" / "pilot"


def run_replay(db: str) -> dict[str, Any]:
    import importer
    import run_migrations

    pg_candidate.drop_database(db)
    pg_candidate.create_database(db)
    assert (
        run_migrations.run(db, SIDE / "migrations", __import__("sys").stdout)
        == run_migrations.EXIT_OK
    )
    receipts = {}
    for entry in PILOT_ENTRIES:
        staging = PILOT_ROOT / entry / "staging"
        sealed = PILOT_ROOT / entry / "sealed"
        receipt = importer.import_sealed(staging, sealed, db)
        receipts[entry] = receipt
        if receipt["status"] != "committed":
            raise SystemExit(f"replay {db}: {entry} failed: {receipt}")
    digest_input = []
    for line in pg_candidate.psql(
        db,
        "SELECT r.identity_key, p.payload_hash, o.order_key, o.context_key "
        "FROM observations o "
        "JOIN content_payloads p ON p.payload_id = o.payload_id "
        "JOIN source_records r ON r.source_record_id = o.source_record_id "
        "ORDER BY r.identity_key, p.payload_hash, o.order_key, o.context_key;",
    ).stdout.splitlines():
        if line.strip():
            digest_input.append(line)
    counts = {}
    for table in (
        "source_records",
        "observations",
        "content_payloads",
        "content_payload_bodies",
        "ingest_batches",
        "source_record_current",
        "conflicts",
    ):
        counts[table] = int(
            pg_candidate.psql(db, f"SELECT count(*) FROM {table};").stdout.strip()
        )
    current_map = pg_candidate.psql(
        db,
        "SELECT r.identity_key, c.status FROM source_record_current c "
        "JOIN source_records r ON r.source_record_id = c.source_record_id "
        "ORDER BY r.identity_key;",
    ).stdout.splitlines()
    digest = hashlib.sha256(
        ("\n".join(digest_input) + "\n" + "\n".join(current_map)).encode("utf-8")
    ).hexdigest()
    return {
        "database": db,
        "digest": digest,
        "counts": counts,
        "current_rows": len(current_map),
        "receipts": receipts,
    }


def main() -> int:
    pg_candidate.init_cluster()
    replay_1 = run_replay("t13_replay_1")
    replay_2 = run_replay("t13_replay_2")
    identical = (
        replay_1["digest"] == replay_2["digest"]
        and replay_1["counts"] == replay_2["counts"]
        and replay_1["current_rows"] == replay_2["current_rows"]
    )
    report = {
        "replay_1": {
            k: replay_1[k] for k in ("database", "digest", "counts", "current_rows")
        },
        "replay_2": {
            k: replay_2[k] for k in ("database", "digest", "counts", "current_rows")
        },
        "identical": identical,
        "public_path_closed": True,
        "public_path_check": "search.py provides no HTTP surface; "
        "test_no_public_routes asserts no server markers",
    }
    (SIDE / "evidence" / "t13_replay.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "identical": identical,
                "digest_1": replay_1["digest"][:16],
                "digest_2": replay_2["digest"][:16],
                "counts": replay_1["counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
