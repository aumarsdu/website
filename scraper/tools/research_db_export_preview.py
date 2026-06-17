#!/usr/bin/env python3
"""Export a compact research project preview dataset from PostgreSQL."""

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


def export_projects(database_url: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    query = r"""
select jsonb_build_object(
    'id', p.id,
    'title', p.title,
    'provider', pr.name,
    'source', src.code,
    'status', p.status,
    'readiness', p.readiness,
    'project_type', p.project_type,
    'summary', nullif(coalesce(dp.card_summary, p.canonical_summary, p.topic_info, ''), ''),
    'topic_info', nullif(coalesce(p.topic_info, ''), ''),
    'duration', o.duration,
    'start_date_text', o.start_date_text,
    'enrollment_status', o.enrollment_status,
    'instructors', coalesce(ins.instructors, '[]'::jsonb),
    'institutions', coalesce(ins.institutions, '[]'::jsonb),
    'taxonomy', coalesce(tax.taxonomy, '[]'::jsonb),
    'suitable_grades', coalesce(to_jsonb(pm.suitable_grades), '[]'::jsonb),
    'prerequisite_courses', coalesce(to_jsonb(pm.prerequisite_courses), '[]'::jsonb),
    'quality_issue_count', coalesce(qi.issue_count, 0),
    'asset_count', coalesce(asset.asset_count, 0),
    'source_url', web.url
  )::text
  from canonical_projects p
  left join providers pr on pr.id = p.provider_id
  left join source_project_records spr on spr.id = p.primary_source_record_id
  left join sources src on src.id = spr.source_id
  left join project_offerings o on o.canonical_project_id = p.id
  left join project_display_profiles dp on dp.canonical_project_id = p.id and dp.version = 1
  left join project_match_profiles pm on pm.canonical_project_id = p.id
  left join lateral (
    select
      jsonb_agg(distinct i.name) filter (where i.name is not null) as instructors,
      jsonb_agg(distinct coalesce(inst.name, i.institution_name_raw)) filter (where coalesce(inst.name, i.institution_name_raw) is not null) as institutions
    from project_instructors pi
    join instructors i on i.id = pi.instructor_id
    left join institutions inst on inst.id = i.institution_id
    where pi.canonical_project_id = p.id
  ) ins on true
  left join lateral (
    select jsonb_agg(distinct jsonb_build_object('type', ptl.term_type, 'name', tt.name)) as taxonomy
    from project_taxonomy_links ptl
    join taxonomy_terms tt on tt.id = ptl.taxonomy_term_id
    where ptl.canonical_project_id = p.id
  ) tax on true
  left join lateral (
    select count(*)::int as issue_count
    from data_quality_issues dqi
    where dqi.canonical_project_id = p.id
  ) qi on true
  left join lateral (
    select count(distinct al.asset_id)::int as asset_count
    from asset_links al
    where al.canonical_project_id = p.id
  ) asset on true
  left join lateral (
    select pl.url
    from project_links pl
    where pl.canonical_project_id = p.id and pl.link_type = 'web_page'
    order by pl.created_at asc nulls last
    limit 1
  ) web on true
  order by p.created_at desc, p.title asc;
"""
    text = run_psql(database_url, query)
    (out_dir / "projects.jsonl").write_text(text, encoding="utf-8")


def export_summary(database_url: str, out_dir: Path) -> None:
    sql = """
select jsonb_build_object(
  'project_count', (select count(*) from canonical_projects),
  'asset_count', (select count(*) from assets),
  'provider_count', (select count(*) from providers),
  'quality_issue_count', (select count(*) from data_quality_issues),
  'enrichment_task_count', (select count(*) from enrichment_tasks),
  'source_counts', (
    select jsonb_object_agg(code, row_count)
    from (
      select s.code, count(*) as row_count
      from source_project_records r
      join sources s on s.id = r.source_id
      group by s.code
      order by s.code
    ) x
  ),
  'provider_counts', (
    select jsonb_object_agg(provider_name, row_count)
    from (
      select provider_name, count(*) as row_count
      from ops_project_cards
      group by provider_name
      order by count(*) desc
    ) x
  )
);
"""
    summary = run_psql(database_url, sql).strip()
    parsed = json.loads(summary)
    (out_dir / "summary.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default="postgresql://research_ops@/research_projects_clean?host=/tmp&port=55432")
    parser.add_argument("--out-dir", default="db/research_db/web_preview/data")
    args = parser.parse_args()
    out_dir = ROOT / args.out_dir
    export_projects(args.database_url, out_dir)
    export_summary(args.database_url, out_dir)
    print(json.dumps({"out_dir": args.out_dir, "files": ["projects.jsonl", "summary.json"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
