#!/usr/bin/env python3
"""Import research DB staging JSONL into a database.

PostgreSQL mode uses `psql` and the schema in `db/research_db/schema.sql`.
SQLite smoke mode is for local validation only; it is not the production schema.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

IMPORT_ORDER = [
    "sources",
    "providers",
    "ingest_batches",
    "source_project_records",
    "source_project_record_versions",
    "canonical_projects",
    "institutions",
    "instructors",
    "taxonomy_terms",
    "assets",
    "project_source_links",
    "project_links",
    "project_offerings",
    "project_match_profiles",
    "project_display_profiles",
    "project_instructors",
    "project_taxonomy_links",
    "asset_links",
    "data_quality_issues",
    "enrichment_tasks",
    "merge_candidates",
]

JSONB_COLUMNS = {
    "stats_json",
    "error_json",
    "raw_json",
    "source_evidence_json",
    "evidence_json",
    "metadata_json",
    "proposed_value_json",
    "current_value_json",
    "before_json",
    "after_json",
    "event_context_json",
    "customer_context_json",
    "best_fit_rules",
    "poor_fit_rules",
    "weight_json",
    "faq_json",
    "objection_handling_json",
}

TEXT_ARRAY_COLUMNS = {
    "authorization_scope",
    "aliases",
    "suitable_student_directions",
    "suitable_grades",
    "suitable_majors_cache",
    "prerequisite_courses",
    "application_goal_fit",
    "target_countries",
    "degree_goals",
    "student_stages",
    "major_groups",
    "grade_band",
    "time_window_tags",
    "required_foundation",
    "customer_pain_points",
    "key_selling_points",
    "recommended_scenarios",
    "not_recommended_scenarios",
    "forbidden_claims",
    "ops_flags",
}


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_literal(column: str, value: Any) -> str:
    if value is None:
        return "NULL"
    if column in JSONB_COLUMNS:
        return sql_string(json.dumps(value, ensure_ascii=False, sort_keys=True)) + "::jsonb"
    if column in TEXT_ARRAY_COLUMNS:
        values = value if isinstance(value, list) else [value]
        return "ARRAY[" + ",".join(sql_string(str(item)) for item in values if item is not None) + "]::text[]"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return sql_string(json.dumps(value, ensure_ascii=False, sort_keys=True)) + "::jsonb"
    return sql_string(str(value))


def run_psql(database_url: str, sql: str, *, quiet: bool = False) -> None:
    cmd = ["psql", database_url, "-v", "ON_ERROR_STOP=1"]
    proc = subprocess.run(cmd, input=sql, text=True, capture_output=True)
    if proc.returncode != 0:
        if proc.stdout and not quiet:
            print(proc.stdout, file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    if proc.stdout and not quiet:
        print(proc.stdout)


def run_schema(database_url: str, schema_path: Path) -> None:
    cmd = ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-f", str(schema_path)]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout, file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)


def import_postgres(database_url: str, staging_dir: Path, schema_path: Path, batch_size: int) -> dict[str, int]:
    if not shutil.which("psql"):
        raise SystemExit("psql is required for PostgreSQL import.")

    run_schema(database_url, schema_path)
    imported: dict[str, int] = {}

    cmd = ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-q"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    assert proc.stdin is not None
    try:
        proc.stdin.write("BEGIN;\nSET CONSTRAINTS ALL DEFERRED;\n")
        for table in IMPORT_ORDER:
            path = staging_dir / f"{table}.jsonl"
            if not path.exists():
                continue
            rows = read_rows(path)
            if not rows:
                continue
            columns = list(rows[0].keys())
            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            for start in range(0, len(rows), batch_size):
                chunk = rows[start:start + batch_size]
                values_sql = []
                for row in chunk:
                    values_sql.append("(" + ", ".join(sql_literal(column, row.get(column)) for column in columns) + ")")
                sql = (
                    f'INSERT INTO "{table}" ({quoted_columns}) VALUES\n'
                    + ",\n".join(values_sql)
                    + "\nON CONFLICT DO NOTHING;\n"
                )
                proc.stdin.write(sql)
            imported[table] = len(rows)
        proc.stdin.write("COMMIT;\n")
        proc.stdin.close()
        returncode = proc.wait()
        if returncode != 0:
            raise SystemExit(returncode)
    except Exception:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.write("ROLLBACK;\n")
            proc.stdin.close()
        proc.wait()
        raise
    return imported


def import_sqlite_smoke(staging_dir: Path, sqlite_path: Path) -> dict[str, int]:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        sqlite_path.unlink()
    conn = sqlite3.connect(sqlite_path)
    try:
        imported: dict[str, int] = {}
        for table in IMPORT_ORDER:
            path = staging_dir / f"{table}.jsonl"
            if not path.exists():
                continue
            rows = read_rows(path)
            if not rows:
                continue
            columns = list(rows[0].keys())
            column_defs = ", ".join(f'"{column}" TEXT' for column in columns)
            conn.execute(f'CREATE TABLE "{table}" ({column_defs})')
            placeholders = ", ".join("?" for _ in columns)
            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            for row in rows:
                values = []
                for column in columns:
                    value = row.get(column)
                    if isinstance(value, (dict, list)):
                        values.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
                    elif value is None:
                        values.append(None)
                    else:
                        values.append(str(value))
                conn.execute(f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({placeholders})', values)
            imported[table] = len(rows)
        conn.commit()
        return imported
    finally:
        conn.close()


def count_postgres(database_url: str, tables: list[str]) -> dict[str, int]:
    sql = "\n".join(
        f"SELECT '{table}' AS table_name, count(*) AS row_count FROM \"{table}\";"
        for table in tables
    )
    cmd = ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-At", "-F", "\t"]
    proc = subprocess.run(cmd, input=sql, text=True, capture_output=True)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    result: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        table, count = line.split("\t")
        result[table] = int(count)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging-dir", default="data_staging/research_db/20260602")
    parser.add_argument("--schema", default="db/research_db/schema.sql")
    parser.add_argument("--database-url", help="PostgreSQL connection string. Do not pass production credentials here.")
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--sqlite-smoke", help="Write a local SQLite smoke-test database instead of PostgreSQL.")
    args = parser.parse_args()

    staging_dir = ROOT / args.staging_dir
    schema_path = ROOT / args.schema

    if args.sqlite_smoke:
        imported = import_sqlite_smoke(staging_dir, ROOT / args.sqlite_smoke)
        print(json.dumps({"mode": "sqlite-smoke", "imported": imported, "sqlite_path": args.sqlite_smoke}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if not args.database_url:
        raise SystemExit("--database-url is required unless --sqlite-smoke is used.")

    imported = import_postgres(args.database_url, staging_dir, schema_path, args.batch_size)
    counts = count_postgres(args.database_url, list(imported.keys()))
    print(json.dumps({"mode": "postgres", "attempted": imported, "database_counts": counts}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
