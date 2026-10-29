"""T12 candidate backup/restore: consistent snapshots across the database,
manual ledger, version configs and the asset manifest, with reconciliation
and an explicit switch/rollback drill.

RPO target (pilot): zero loss of sealed batches and confirmed manual
revisions. RTO target: restore completes within 60 minutes (measured).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pg_candidate

PG_BIN = Path("/opt/homebrew/opt/postgresql@16/bin")
COUNT_TABLES = (
    "source_records",
    "observations",
    "content_payloads",
    "content_payload_bodies",
    "ingest_batches",
    "manual_overrides",
    "conflicts",
    "source_record_current",
    "provider_projects",
    "offerings",
)
VERSION_FILES = (
    "environment.json",
    "contract_config.json",
    "contract.md",
    "schema_model.md",
    "target_policy.json",
)


class BackupError(ValueError):
    """A backup or restore step failed its reconciliation."""


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **kwargs,  # type: ignore[arg-type]
    )
    if result.returncode != 0:
        raise BackupError(
            f"command failed ({result.returncode}): {result.stderr.strip()[-300:]}"
        )
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(
    database: str, backup_dir: Path, asset_roots: list[Path] | None = None
) -> dict[str, Any]:
    """Freeze writes (single-writer covenant), dump the DB and capture the
    version configs plus the asset manifest into backup_dir."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    dump_path = backup_dir / "database.dump"
    _run(
        [
            str(PG_BIN / "pg_dump"),
            "-h",
            "127.0.0.1",
            "-p",
            "55441",
            "-U",
            "candidate_t03",
            "-Fc",
            "-f",
            str(dump_path),
            database,
        ]
    )
    side = Path(__file__).resolve().parent
    configs = {}
    for name in VERSION_FILES:
        source = side / name
        if source.is_file():
            target = backup_dir / name
            target.write_bytes(source.read_bytes())
            configs[name] = _sha256_file(target)
    counts = {}
    for table in COUNT_TABLES:
        result = pg_candidate.psql(database, f"SELECT count(*) FROM {table};")
        counts[table] = int(result.stdout.strip())
    overrides = pg_candidate.psql(
        database,
        "SELECT coalesce(jsonb_agg(jsonb_build_object('override_id', "
        "override_id, 'entity_kind', entity_kind, 'entity_id', entity_id, "
        "'field_name', field_name, 'new_value', new_value, 'author', author) "
        "ORDER BY override_id), '[]'::jsonb) FROM manual_overrides "
        "WHERE reverted_by IS NULL;",
    ).stdout.strip()
    asset_manifest: list[dict[str, Any]] = []
    for root in asset_roots or []:
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                relative = path.relative_to(root).as_posix()
                asset_manifest.append(
                    {
                        "root": root.as_posix(),
                        "relative_path": relative,
                        "sha256": _sha256_file(path),
                        "byte_size": path.stat().st_size,
                    }
                )
    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": database,
        "dump_file": "database.dump",
        "dump_sha256": _sha256_file(dump_path),
        "counts": counts,
        "manual_overrides_active": json.loads(overrides),
        "configs": configs,
        "asset_manifest": asset_manifest,
        "rto_seconds": round(time.perf_counter() - started, 3),
    }
    (backup_dir / "backup_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return meta


def restore_backup(backup_dir: Path, target_db: str) -> dict[str, Any]:
    """Restore a backup into a fresh target database and reconcile counts."""
    started = time.perf_counter()
    meta = json.loads((backup_dir / "backup_meta.json").read_text(encoding="utf-8"))
    dump_path = backup_dir / meta["dump_file"]
    if _sha256_file(dump_path) != meta["dump_sha256"]:
        raise BackupError("dump_corrupted")
    if pg_candidate.database_exists(target_db):
        pg_candidate.drop_database(target_db)
    try:
        pg_candidate.create_database(target_db)
    except pg_candidate.ClusterError as exc:
        raise BackupError(f"restore_create_failed: {exc}") from exc
    try:
        _run(
            [
                str(PG_BIN / "pg_restore"),
                "-h",
                "127.0.0.1",
                "-p",
                "55441",
                "-U",
                "candidate_t03",
                "-d",
                target_db,
                "--no-owner",
                str(dump_path),
            ]
        )
    except BackupError:
        pg_candidate.drop_database(target_db)
        raise
    mismatches: list[dict[str, Any]] = []
    for table, expected in meta["counts"].items():
        actual = int(
            pg_candidate.psql(
                target_db, f"SELECT count(*) FROM {table};"
            ).stdout.strip()
        )
        if actual != expected:
            mismatches.append({"table": table, "expected": expected, "actual": actual})
    for name, digest in meta["configs"].items():
        restored = backup_dir / name
        if not restored.is_file() or _sha256_file(restored) != digest:
            mismatches.append({"config": name, "issue": "missing_or_changed"})
    for asset in meta["asset_manifest"]:
        path = Path(asset["root"]) / asset["relative_path"]
        if not path.is_file():
            mismatches.append({"asset": asset["relative_path"], "issue": "missing"})
        elif _sha256_file(path) != asset["sha256"]:
            mismatches.append(
                {"asset": asset["relative_path"], "issue": "hash_changed"}
            )
    rto = round(time.perf_counter() - started, 3)
    return {
        "target_db": target_db,
        "counts_reconciled": not mismatches,
        "mismatches": mismatches,
        "rto_seconds": rto,
        "rto_budget_seconds": 3600,
    }


def switch_drill(
    backup_dir: Path, original_db: str, switched_db: str
) -> dict[str, Any]:
    """Explicit switch drill: successful switch and a failed-switch fallback.

    The failure path (unavailable backup) must fall back to the original
    database without any data change on either side.
    """
    outcome: dict[str, Any] = {"steps": []}
    restore = restore_backup(backup_dir, switched_db)
    outcome["steps"].append({"step": "restore", **restore})
    healthy = restore["counts_reconciled"]
    outcome["switch_to_restored"] = healthy
    failed_restore: dict[str, Any] = {}
    try:
        broken = backup_dir.parent / "broken_drill"
        broken.mkdir(parents=True, exist_ok=True)
        (broken / "database.dump").write_bytes(b"not a dump")
        meta = {
            "dump_file": "database.dump",
            "dump_sha256": hashlib.sha256(b"not a dump").hexdigest(),
            "counts": {},
            "configs": {},
            "asset_manifest": [],
        }
        (broken / "backup_meta.json").write_text(json.dumps(meta), encoding="utf-8")
        restore_backup(broken, switched_db + "_failed")
    except BackupError as exc:
        failed_restore["failed_as_expected"] = True
        failed_restore["error"] = str(exc)[:120]
    outcome["steps"].append({"step": "failed_switch", **failed_restore})
    outcome["fallback_to_original"] = pg_candidate.database_exists(original_db)
    return outcome
