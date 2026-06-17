#!/usr/bin/env python3
"""Local admin/public server for research project visibility operations."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "db/research_db/admin_web"
DEFAULT_DATABASE_URL = "postgresql://research_ops@/research_projects_clean?host=/tmp&port=55432"


def run_psql_json(database_url: str, sql: str) -> object:
    cmd = ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    text = proc.stdout.strip()
    if not text:
        return None
    return json.loads(text)


def run_psql(database_url: str, sql: str) -> None:
    cmd = ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-q", "-c", sql]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def slug_for(title: str | None, project_id: str) -> str:
    source = title or "project"
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", source).strip("-")
    cleaned = cleaned[:48].strip("-") or "project"
    return f"{cleaned}-{project_id[:8]}"


def int_param(params: dict[str, list[str]], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(params.get(key, [str(default)])[0])
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


class AdminHandler(BaseHTTPRequestHandler):
    database_url = DEFAULT_DATABASE_URL

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def send_json(self, payload: object, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_static(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        content_type = "text/html; charset=utf-8"
        if path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/admin", "/admin/"}:
            self.send_static(WEB_ROOT / "admin.html")
            return
        if parsed.path in {"/public", "/public/"}:
            self.send_static(WEB_ROOT / "public.html")
            return
        if parsed.path == "/admin.css":
            self.send_static(WEB_ROOT / "admin.css")
            return
        if parsed.path == "/admin.js":
            self.send_static(WEB_ROOT / "admin.js")
            return
        if parsed.path == "/public.js":
            self.send_static(WEB_ROOT / "public.js")
            return
        if parsed.path == "/api/admin/summary":
            self.handle_admin_summary()
            return
        if parsed.path == "/api/admin/projects":
            self.handle_admin_projects(parse_qs(parsed.query))
            return
        if parsed.path == "/api/public/projects":
            self.handle_public_projects(parse_qs(parsed.query))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        match = re.fullmatch(r"/api/admin/projects/([0-9a-fA-F-]+)/visibility", parsed.path)
        if match:
            self.handle_visibility(match.group(1))
            return
        self.send_error(404)

    def read_body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        data = self.rfile.read(length)
        return json.loads(data.decode("utf-8"))

    def handle_admin_summary(self) -> None:
        sql = """
select jsonb_build_object(
  'total_projects', (select count(*) from canonical_projects),
  'visible_projects', (
    select count(*)
    from canonical_projects p
    join project_display_profiles d on d.canonical_project_id = p.id and d.version = 1
    where p.status = 'published' and d.status = 'published'
  ),
  'hidden_projects', (
    select count(*)
    from canonical_projects p
    left join project_display_profiles d on d.canonical_project_id = p.id and d.version = 1
    where not (p.status = 'published' and d.status = 'published')
  ),
  'provider_count', (select count(*) from providers),
  'providers', (
    select coalesce(jsonb_agg(jsonb_build_object('provider', provider, 'count', project_count) order by provider), '[]'::jsonb)
    from (
      select pr.name as provider, count(p.id)::int as project_count
      from providers pr
      left join canonical_projects p on p.provider_id = pr.id
      group by pr.name
    ) x
  ),
  'sources', (
    select coalesce(jsonb_agg(jsonb_build_object('source_system', source_system, 'count', project_count) order by source_system), '[]'::jsonb)
    from (
      select s.code as source_system, count(p.id)::int as project_count
      from sources s
      left join source_project_records spr on spr.source_id = s.id
      left join canonical_projects p on p.primary_source_record_id = spr.id
      group by s.code
    ) x
  )
);
"""
        self.send_json(run_psql_json(self.database_url, sql))

    def project_query_sql(self, params: dict[str, list[str]], *, public_only: bool) -> str:
        q = params.get("q", [""])[0].strip()
        provider = params.get("provider", [""])[0].strip()
        source = params.get("source", [""])[0].strip()
        visibility = params.get("visibility", [""])[0].strip()
        page = int_param(params, "page", 1, 1, 10000)
        page_size = int_param(params, "page_size", 50, 1, 200)
        offset = (page - 1) * page_size

        where = []
        if public_only:
            where.append("p.status = 'published' and d.status = 'published'")
        elif visibility == "visible":
            where.append("p.status = 'published' and d.status = 'published'")
        elif visibility == "hidden":
            where.append("not (p.status = 'published' and d.status = 'published')")
        if provider:
            where.append(f"pr.name = {sql_string(provider)}")
        if source:
            where.append(f"s.code = {sql_string(source)}")
        if q:
            pattern = sql_string(f"%{q}%")
            where.append(
                "("
                f"p.title ilike {pattern} or "
                f"coalesce(p.topic_info, '') ilike {pattern} or "
                f"coalesce(d.project_summary, '') ilike {pattern} or "
                f"exists ("
                f"  select 1"
                f"  from project_instructors pi"
                f"  join instructors i on i.id = pi.instructor_id"
                f"  left join institutions inst on inst.id = i.institution_id"
                f"  where pi.canonical_project_id = p.id"
                f"    and (i.name ilike {pattern} or coalesce(inst.name, i.institution_name_raw, '') ilike {pattern})"
                f") or "
                f"exists ("
                f"  select 1"
                f"  from project_taxonomy_links ptl"
                f"  join taxonomy_terms tt on tt.id = ptl.taxonomy_term_id"
                f"  where ptl.canonical_project_id = p.id and tt.name ilike {pattern}"
                f")"
                ")"
            )
        where_sql = "where " + " and ".join(where) if where else ""

        return f"""
with candidates as (
  select
    p.id,
    (p.status = 'published' and d.status = 'published') as is_visible,
    p.updated_at,
    p.title,
    count(*) over() as total_count
  from canonical_projects p
  left join providers pr on pr.id = p.provider_id
  left join source_project_records spr on spr.id = p.primary_source_record_id
  left join sources s on s.id = spr.source_id
  left join project_display_profiles d on d.canonical_project_id = p.id and d.version = 1
  {where_sql}
  order by is_visible desc, p.updated_at desc nulls last, p.title asc
  limit {page_size} offset {offset}
),
base as (
  select
    p.id,
    p.title,
    coalesce(d.display_title, p.title) as display_title,
    p.status,
    p.readiness,
    p.project_type,
    p.topic_info,
    p.canonical_summary,
    pr.name as provider,
    s.code as source,
    d.status as display_status,
    d.public_slug,
    d.card_summary,
    d.project_summary,
    d.topic_information_display,
    d.research_question,
    d.research_method,
    d.expected_outputs,
    d.instructor_bio_display,
    d.suitable_for_display,
    ops.priority,
    o.duration,
    o.start_date_text,
    o.enrollment_status,
    coalesce(o.price_amount, commercial.suggested_sale_price_amount, commercial.list_price_amount) as price_amount,
    coalesce(o.price_currency, commercial.currency) as price_currency,
    match.difficulty_level as difficulty,
    match.suitable_student_directions as suitable_student_direction,
    match.suitable_grades,
    match.suitable_majors_cache as suitable_majors,
    match.prerequisite_courses as prerequisites,
    primary_inst.name as professor_name,
    primary_inst.academic_title as professor_level,
    primary_inst.country,
    primary_inst.bio_raw as professor_bio,
    primary_inst.bio_edited as professor_bio_edited,
    primary_inst.paper_guidance_scope as thesis_supervision_scope,
    primary_inst.institution_name as school_name,
    coalesce(search.primary_subject, '') as primary_subject,
    coalesce(search.secondary_subject, '') as secondary_subject,
    coalesce(search.specialization, '') as major_direction,
    c.is_visible,
    coalesce(qi.issue_count, 0) as quality_issue_count,
    coalesce(asset.asset_count, 0) as asset_count,
    coalesce(search.instructors_json, '[]'::jsonb) as instructors,
    coalesce(search.institutions_json, '[]'::jsonb) as institutions,
    coalesce(search.taxonomy_json, '[]'::jsonb) as taxonomy,
    web.url as source_url,
    coalesce(web.urls, '[]'::jsonb) as source_urls,
    c.total_count
  from candidates c
  join canonical_projects p on p.id = c.id
  left join providers pr on pr.id = p.provider_id
  left join source_project_records spr on spr.id = p.primary_source_record_id
  left join sources s on s.id = spr.source_id
  left join project_display_profiles d on d.canonical_project_id = p.id and d.version = 1
  left join project_offerings o on o.canonical_project_id = p.id
  left join project_ops ops on ops.canonical_project_id = p.id
  left join project_commercial_profiles commercial on commercial.canonical_project_id = p.id
  left join project_match_profiles match on match.canonical_project_id = p.id
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
    select
      string_agg(distinct i.name, ' ') as instructors,
      string_agg(distinct coalesce(inst.name, i.institution_name_raw), ' ') as institutions,
      jsonb_agg(distinct i.name) filter (where i.name is not null) as instructors_json,
      jsonb_agg(distinct coalesce(inst.name, i.institution_name_raw)) filter (where coalesce(inst.name, i.institution_name_raw) is not null) as institutions_json,
      string_agg(distinct tt.name, ' ') as taxonomy_text,
      jsonb_agg(distinct jsonb_build_object('type', ptl.term_type, 'name', tt.name)) filter (where tt.name is not null) as taxonomy_json,
      string_agg(distinct tt.name, '、') filter (where ptl.term_type = 'primary_discipline') as primary_subject,
      string_agg(distinct tt.name, '、') filter (where ptl.term_type = 'secondary_discipline') as secondary_subject,
      string_agg(distinct tt.name, '、') filter (where ptl.term_type = 'specialization') as specialization
    from project_instructors pi
    left join instructors i on i.id = pi.instructor_id
    left join institutions inst on inst.id = i.institution_id
    left join project_taxonomy_links ptl on ptl.canonical_project_id = p.id
    left join taxonomy_terms tt on tt.id = ptl.taxonomy_term_id
    where pi.canonical_project_id = p.id
  ) search on true
  left join lateral (
    select
      i.name,
      i.academic_title,
      i.country,
      i.bio_raw,
      i.bio_edited,
      i.paper_guidance_scope,
      coalesce(inst.name, i.institution_name_raw) as institution_name
    from project_instructors pi
    join instructors i on i.id = pi.instructor_id
    left join institutions inst on inst.id = i.institution_id
    where pi.canonical_project_id = p.id
    order by case when pi.role = 'primary' then 0 else 1 end, i.name
    limit 1
  ) primary_inst on true
  left join lateral (
    select
      min(pl.url) as url,
      jsonb_agg(pl.url order by pl.created_at asc nulls last) as urls
    from project_links pl
    where pl.canonical_project_id = p.id and pl.link_type = 'web_page'
  ) web on true
  order by c.is_visible desc, c.updated_at desc nulls last, c.title asc
)
select jsonb_build_object(
  'page', {page},
  'page_size', {page_size},
  'total', coalesce(max(total_count), 0),
  'items', coalesce(jsonb_agg(to_jsonb(base) - 'total_count'), '[]'::jsonb)
) from base;
"""

    def handle_admin_projects(self, params: dict[str, list[str]]) -> None:
        self.send_json(run_psql_json(self.database_url, self.project_query_sql(params, public_only=False)))

    def handle_public_projects(self, params: dict[str, list[str]]) -> None:
        self.send_json(run_psql_json(self.database_url, self.project_query_sql(params, public_only=True)))

    def handle_visibility(self, project_id: str) -> None:
        body = self.read_body_json()
        visible = bool(body.get("visible"))
        title_sql = f"select title from canonical_projects where id = {sql_string(project_id)};"
        title = run_psql_json(self.database_url, f"select to_jsonb(title) from ({title_sql[:-1]}) x;")
        slug = slug_for(title, project_id)
        if visible:
            sql = f"""
begin;
update canonical_projects
set status = 'published', readiness = 'publish_ready', updated_at = now()
where id = {sql_string(project_id)};
update project_display_profiles
set status = 'published',
    public_slug = coalesce(public_slug, {sql_string(slug)}),
    published_at = coalesce(published_at, now()),
    updated_at = now()
where canonical_project_id = {sql_string(project_id)} and version = 1;
commit;
"""
        else:
            sql = f"""
begin;
update canonical_projects
set status = 'approved', readiness = 'review_ready', updated_at = now()
where id = {sql_string(project_id)};
update project_display_profiles
set status = 'draft',
    published_at = null,
    updated_at = now()
where canonical_project_id = {sql_string(project_id)} and version = 1;
commit;
"""
        run_psql(self.database_url, sql)
        self.send_json({"id": project_id, "visible": visible})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    args = parser.parse_args()

    AdminHandler.database_url = args.database_url
    server = ThreadingHTTPServer((args.host, args.port), AdminHandler)
    print(f"Research DB admin server: http://{args.host}:{args.port}/admin/")
    print(f"Public preview: http://{args.host}:{args.port}/public/")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
