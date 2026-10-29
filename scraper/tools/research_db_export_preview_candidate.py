#!/usr/bin/env python3
"""Export the R6 candidate-model preview dataset (same consumer contract as
research_db_export_preview.py) from a candidate-schema database.

Field contract (web_preview/app.js): id/title/provider/source/status/readiness/
project_type/summary/topic_info/duration/start_date_text/enrollment_status/
instructors/institutions/taxonomy/suitable_grades/prerequisite_courses/
quality_issue_count/asset_count/source_url. Candidate-model fields the legacy
contract expects but the model does not carry are exported as honest nulls or
empty arrays; taxonomy carries the payload category; one card per identity via
the current pointer's winning payload.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_psql(database_url: str, sql: str) -> str:
    cmd = ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc.stdout


PROJECTS_SQL = r"""
select jsonb_build_object(
    'id', r.identity_key,
    'title', coalesce(b.business ->> 'title', ''),
    'provider', pr.provider_name,
    'source', s.source_code,
    'status', r.identity_status,
    'readiness', case when c.status = 'ok' then 'searchable' else 'unresolved' end,
    'project_type', null,
    'summary', null,
    'topic_info', null,
    'duration', nullif(b.business ->> 'duration', ''),
    'start_date_text', nullif(b.business ->> 'start_date', ''),
    'enrollment_status', null,
    'instructors', case when coalesce(b.business ->> 'instructor', '') = ''
        then '[]'::jsonb else jsonb_build_array(b.business ->> 'instructor') end,
    'institutions', case when coalesce(b.business ->> 'institution', '') = ''
        then '[]'::jsonb else jsonb_build_array(b.business ->> 'institution') end,
    'taxonomy', case when coalesce(b.business ->> 'category', '') = ''
        then '[]'::jsonb
        else jsonb_build_array(jsonb_build_object(
            'type', 'category', 'name', b.business ->> 'category')) end,
    'suitable_grades', '[]'::jsonb,
    'prerequisite_courses', '[]'::jsonb,
    'quality_issue_count', 0,
    'asset_count', 0,
    'source_url', null
  )::text
  from source_record_current c
  join source_records r on r.source_record_id = c.source_record_id
  join sources s on s.source_id = r.source_id
  join providers pr on pr.provider_id = s.provider_id
  left join observations o on o.observation_id = c.observation_id
  left join content_payload_bodies b on b.payload_id = o.payload_id
  order by s.source_code, r.source_record_id;
"""

SUMMARY_SQL = r"""
select jsonb_build_object(
  'project_count', (select count(*) from source_records),
  'asset_count', 0,
  'provider_count', (select count(*) from providers),
  'quality_issue_count', (select count(*) from quality_issues where status = 'open'),
  'enrichment_task_count', 0,
  'source_counts', (
    select jsonb_object_agg(source_code, row_count) from (
      select s.source_code, count(*) as row_count
      from source_records r join sources s on s.source_id = r.source_id
      group by s.source_code order by s.source_code
    ) x
  ),
  'provider_counts', (
    select jsonb_object_agg(provider_name, row_count) from (
      select pr.provider_name, count(*) as row_count
      from source_records r
      join sources s on s.source_id = r.source_id
      join providers pr on pr.provider_id = s.provider_id
      group by pr.provider_name order by count(*) desc
    ) x
  )
);
"""


def export_projects(database_url: str, out_dir: Path) -> None:
    text = run_psql(database_url, PROJECTS_SQL)
    (out_dir / "projects.jsonl").write_text(text, encoding="utf-8")


def export_summary(database_url: str, out_dir: Path) -> None:
    parsed = json.loads(run_psql(database_url, SUMMARY_SQL).strip())
    (out_dir / "summary.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_projects(args.database_url, out_dir)
    export_summary(args.database_url, out_dir)
    print(
        json.dumps(
            {"out_dir": str(out_dir), "files": ["projects.jsonl", "summary.json"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
