"""Versioned migration runner for the candidate model.

Each migration runs in a single transaction together with its ledger insert.
Applied versions are skipped by checksum; a checksum mismatch fails loudly
instead of being silently skipped. Interruption leaves the ledger untouched,
so re-running resumes cleanly from the last committed checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import TextIO

import pg_candidate

EXIT_OK = 0
EXIT_SQL_ERROR = 1
EXIT_CHECKSUM_CONFLICT = 2


class Migration:
    def __init__(self, path: Path) -> None:
        self.version = path.name.split("_", 1)[0]
        self.name = path.name
        self.checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        self.sql = path.read_text(encoding="utf-8")

    def ledger_sql(self) -> str:
        # Migration body runs verbatim inside one transaction with its ledger row;
        # only version/checksum (safe charset by construction) enter the INSERT.
        return (
            "BEGIN;\n"
            + self.sql
            + "\n"
            + f"INSERT INTO schema_migrations (version, checksum) "
            f"VALUES ('{self.version}', '{self.checksum}');\n" + "COMMIT;"
        )


def applied_versions(database: str) -> dict[str, str]:
    if not pg_candidate.database_exists(database):
        return {}
    probe = pg_candidate.psql(
        database, "SELECT to_regclass('public.schema_migrations') IS NOT NULL;"
    )
    if probe.stdout.strip() != "t":
        return {}
    probe = pg_candidate.psql(
        database,
        "SELECT version, checksum FROM schema_migrations ORDER BY version;",
    )
    result: dict[str, str] = {}
    for line in probe.stdout.splitlines():
        if "|" in line:
            version, checksum = line.split("|", 1)
            result[version] = checksum
    return result


def discover(directory: Path) -> list[Migration]:
    return [
        Migration(path)
        for path in sorted(directory.glob("*.sql"))
        if path.name[0].isdigit()
    ]


def run(database: str, directory: Path, log: TextIO) -> int:
    pending_all = discover(directory)
    applied = applied_versions(database)
    for migration in pending_all:
        if migration.version in applied:
            if applied[migration.version] != migration.checksum:
                print(
                    f"checksum conflict for {migration.version}: "
                    f"applied={applied[migration.version]} current={migration.checksum}",
                    file=log,
                )
                return EXIT_CHECKSUM_CONFLICT
            print(f"skip {migration.version} (already applied)", file=log)
    for migration in pending_all:
        if migration.version in applied:
            continue
        print(f"apply {migration.version}", file=log)
        try:
            pg_candidate.psql(database, migration.ledger_sql())
        except pg_candidate.ClusterError as exc:
            print(f"migration {migration.version} failed: {exc}", file=log)
            return EXIT_SQL_ERROR
        print(f"applied {migration.version}", file=log)
    return EXIT_OK


def plan(database: str, directory: Path, log: TextIO) -> int:
    """Read-only: report applied/pending state without touching the database."""
    applied = applied_versions(database)
    for migration in discover(directory):
        if migration.version in applied:
            state = "applied"
            if applied[migration.version] != migration.checksum:
                state = "CHECKSUM_CONFLICT"
            print(f"{migration.version} {state}", file=log)
        else:
            print(f"{migration.version} pending", file=log)
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(__file__).resolve().parent / "migrations",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="read-only: list pending/applied migrations, apply nothing",
    )
    mode.add_argument("--apply", action="store_true", help="apply pending migrations")
    args = parser.parse_args()
    if args.dry_run:
        code = plan(args.database, args.dir, sys.stdout)
        print(json.dumps({"exit_code": code, "mode": "dry-run"}))
        return code
    pg_candidate.init_cluster()
    if not pg_candidate.database_exists(args.database):
        pg_candidate.create_database(args.database)
    code = run(args.database, args.dir, sys.stdout)
    print(json.dumps({"exit_code": code, "mode": "apply"}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
