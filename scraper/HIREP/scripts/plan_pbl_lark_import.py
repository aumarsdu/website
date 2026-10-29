from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sou_crawler.storage import iter_jsonl, write_json


BASE_TOKEN = "F6gFbhJ2xaPkhmsuRmdcrhkfncc"
TABLE_ID = "tbl4ASKBGNx84nJF"
FIELDS = [
    "课程链接",
    "网页链接",
    "课题信息",
    "教授姓名",
    "一级学科",
    "二级学科",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan importing local PBL projects into a Lark Base table.")
    parser.add_argument("--base-token", default=BASE_TOKEN, help="Target Lark Base token.")
    parser.add_argument("--table-id", default=TABLE_ID, help="Target Lark table ID.")
    parser.add_argument("--output", default="tmp/pbl_lark_import_plan.json", help="Plan JSON output path.")
    parser.add_argument(
        "--projects-file",
        action="append",
        default=[],
        help="Normalized projects.jsonl to import. Omit to include all local PBL outputs. Can be supplied multiple times.",
    )
    parser.add_argument("--skip-remote", action="store_true", help="Do not read existing Lark records.")
    args = parser.parse_args()

    local_projects = load_local_projects(args.projects_file)
    existing = [] if args.skip_remote else fetch_existing_records(args.base_token, args.table_id)
    existing_keys = existing_record_keys(existing)
    rows = []
    skipped_existing = 0
    skipped_duplicate_local = 0
    seen_local: set[str] = set()
    for project in local_projects:
        key = project_key(project)
        if key in seen_local:
            skipped_duplicate_local += 1
            continue
        seen_local.add(key)
        if key in existing_keys["course_extend_ids"] or project.get("source_url") in existing_keys["urls"]:
            skipped_existing += 1
            continue
        rows.append(project)

    plan = {
        "local_projects": len(local_projects),
        "local_unique_projects": len(seen_local),
        "existing_records_read": len(existing),
        "existing_course_extend_ids": len(existing_keys["course_extend_ids"]),
        "existing_urls": len(existing_keys["urls"]),
        "target_table_id": args.table_id,
        "skip_existing": skipped_existing,
        "skip_duplicate_local": skipped_duplicate_local,
        "to_create": len(rows),
        "sample_to_create": [project_summary(project) for project in rows[:10]],
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    write_json(output, {"plan": plan, "rows": rows})
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def load_local_projects(project_paths: list[str] | None = None) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    paths = [Path(path) for path in project_paths or []]
    if not paths:
        paths = sorted(PROJECT_ROOT.glob("output*/processed/projects.jsonl"))
    for path in paths:
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        for project in iter_jsonl(path) or []:
            if not isinstance(project, dict):
                continue
            if not project.get("title"):
                continue
            if not course_extend_id(str(project.get("source_url") or "")):
                continue
            item = dict(project)
            item["_output_dir"] = path.parents[1].name
            projects.append(item)
    return projects


def fetch_existing_records(base_token: str, table_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        cmd = [
            "lark-cli",
            "base",
            "+record-list",
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--limit",
            "200",
            "--offset",
            str(offset),
            "--as",
            "user",
            "--format",
            "json",
        ]
        for field in FIELDS:
            cmd.extend(["--field-id", field])
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        payload = json.loads(result.stdout)
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        fields = data.get("fields") or FIELDS
        page_rows = data.get("data") or []
        for values in page_rows:
            rows.append(dict(zip(fields, values)))
        if not data.get("has_more"):
            break
        offset += len(page_rows)
        if not page_rows:
            break
    return rows


def existing_record_keys(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    course_extend_ids: set[str] = set()
    urls: set[str] = set()
    titles: set[str] = set()
    for record in records:
        for field in ("课程链接", "网页链接"):
            url = extract_url(str(record.get(field) or ""))
            if url:
                urls.add(url)
                course_id = course_extend_id(url)
                if course_id:
                    course_extend_ids.add(course_id)
        title = normalize_text(record.get("课题信息"))
        professor = normalize_text(record.get("教授姓名"))
        if title:
            titles.add(f"{title}::{professor}")
    return {"course_extend_ids": course_extend_ids, "urls": urls, "titles": titles}


def project_key(project: dict[str, Any]) -> str:
    course_id = course_extend_id(str(project.get("source_url") or ""))
    if course_id:
        return course_id
    return f"{normalize_text(project.get('title'))}::{normalize_text(project.get('professor'))}"


def project_summary(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "business_id": project.get("business_id"),
        "title": project.get("title"),
        "professor": project.get("professor"),
        "category": project.get("category"),
        "direction": project.get("direction") or project.get("major_name"),
        "source_url": project.get("source_url"),
        "output_dir": project.get("_output_dir"),
    }


def course_extend_id(url: str) -> str:
    if not url:
        return ""
    query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    return str(query.get("courseExtendId") or "")


def extract_url(value: str) -> str:
    match = re.search(r"\((https?://[^)]+)\)", value)
    if match:
        return match.group(1)
    match = re.search(r"https?://[^\s)]+", value)
    return match.group(0) if match else ""


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


if __name__ == "__main__":
    raise SystemExit(main())
