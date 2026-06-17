#!/usr/bin/env python3
"""Validate research DB staging JSONL files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PK_TABLES = {"project_match_profiles": "canonical_project_id"}

FK_CHECKS = [
    ("canonical_projects", "provider_id", "providers"),
    ("canonical_projects", "primary_source_record_id", "source_project_records"),
    ("source_project_record_versions", "source_project_record_id", "source_project_records"),
    ("source_project_record_versions", "ingest_batch_id", "ingest_batches"),
    ("project_source_links", "canonical_project_id", "canonical_projects"),
    ("project_source_links", "source_project_record_id", "source_project_records"),
    ("project_links", "canonical_project_id", "canonical_projects"),
    ("project_offerings", "canonical_project_id", "canonical_projects"),
    ("project_match_profiles", "canonical_project_id", "canonical_projects"),
    ("project_display_profiles", "canonical_project_id", "canonical_projects"),
    ("project_instructors", "canonical_project_id", "canonical_projects"),
    ("project_instructors", "instructor_id", "instructors"),
    ("project_taxonomy_links", "canonical_project_id", "canonical_projects"),
    ("project_taxonomy_links", "taxonomy_term_id", "taxonomy_terms"),
    ("asset_links", "asset_id", "assets"),
    ("asset_links", "canonical_project_id", "canonical_projects"),
    ("data_quality_issues", "canonical_project_id", "canonical_projects"),
    ("data_quality_issues", "source_project_record_id", "source_project_records"),
    ("enrichment_tasks", "canonical_project_id", "canonical_projects"),
    ("merge_candidates", "left_project_id", "canonical_projects"),
    ("merge_candidates", "right_project_id", "canonical_projects"),
]


def row_key(table: str, row: dict) -> str | None:
    if row.get("id"):
        return str(row["id"])
    field = PK_TABLES.get(table)
    if field and row.get(field):
        return str(row[field])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("staging_dir", nargs="?", default="data_staging/research_db/20260602")
    args = parser.parse_args()
    base = Path(args.staging_dir)

    errors: list[dict] = []
    ids: dict[str, set[str]] = {}
    counts: dict[str, int] = {}

    for path in sorted(base.glob("*.jsonl")):
        table = path.stem
        seen: set[str] = set()
        duplicate_count = 0
        row_count = 0
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    row = json.loads(line)
                except Exception as exc:  # pragma: no cover - CLI diagnostic
                    errors.append({"table": table, "line": line_number, "error": f"parse_error:{exc}"})
                    continue
                row_count += 1
                key = row_key(table, row)
                if key:
                    if key in seen:
                        duplicate_count += 1
                    seen.add(key)
        ids[table] = seen
        counts[table] = row_count
        if duplicate_count:
            errors.append({"table": table, "error": "duplicate_primary_key", "count": duplicate_count})

    for table, field, target in FK_CHECKS:
        path = base / f"{table}.jsonl"
        if not path.exists() or target not in ids:
            continue
        missing = 0
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                value = row.get(field)
                if value is not None and value not in ids[target]:
                    missing += 1
        if missing:
            errors.append({"table": table, "error": f"missing_fk:{field}->{target}", "count": missing})

    result = {"counts": counts, "error_count": len(errors), "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
