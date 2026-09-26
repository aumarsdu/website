from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sou_crawler.storage import read_json, write_json


BASE_TOKEN = "F6gFbhJ2xaPkhmsuRmdcrhkfncc"
TABLE_ID = "tbl4ASKBGNx84nJF"
MATERIALS_TABLE_ID = "tbl3dqRAnisDKI1z"
LEGACY_WRITE_FIELDS = [
    "课题信息",
    "课题简介",
    "难度",
    "招生状态",
    "二级学科",
    "教授姓名",
    "教授简介",
    "网页链接",
    "教授头像",
    "项目类型",
    "课程链接",
    "教授级别",
    "一级学科",
    "专业方向",
    "项目方",
    "海报文字内容",
    "学校",
    "适合学生方向",
    "建议先修课程",
]
MATERIALS_WRITE_FIELDS = [
    "教授论文指导范围（CIS特有）" if field == "海报文字内容" else field
    for field in LEGACY_WRITE_FIELDS
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Import planned PBL projects into Lark Base.")
    parser.add_argument("--base-token", default=BASE_TOKEN, help="Target Lark Base token.")
    parser.add_argument("--table-id", default=TABLE_ID, help="Target Lark table ID.")
    parser.add_argument(
        "--write-profile",
        choices=("auto", "legacy", "materials"),
        default="auto",
        help="Field mapping profile. auto selects materials for the current materials table.",
    )
    parser.add_argument("--plan", default="tmp/pbl_lark_import_plan.json", help="Plan JSON created by plan_pbl_lark_import.py.")
    parser.add_argument("--payload-dir", help="Directory for generated batch payloads. Defaults to a plan-specific tmp directory.")
    parser.add_argument("--result-output", help="Result JSON path. Defaults to a plan-specific tmp file.")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--limit", type=int, default=0, help="Limit rows for dry-run or testing. 0 means all.")
    parser.add_argument("--execute", action="store_true", help="Actually create records. Omit for local payload generation only.")
    parser.add_argument("--dry-run-lark", action="store_true", help="Call lark-cli with --dry-run for the first batch.")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = PROJECT_ROOT / plan_path
    plan = read_json(plan_path, {})
    rows = plan.get("rows") or []
    if args.limit:
        rows = rows[: args.limit]
    write_profile = resolve_write_profile(args.write_profile, args.table_id)
    write_fields = write_fields_for_profile(write_profile)
    payloads = build_payloads(rows, batch_size=args.batch_size, write_fields=write_fields, write_profile=write_profile)
    payload_dir = Path(args.payload_dir) if args.payload_dir else PROJECT_ROOT / "tmp" / f"{plan_path.stem}_batches"
    if not payload_dir.is_absolute():
        payload_dir = PROJECT_ROOT / payload_dir
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_files = []
    for idx, payload in enumerate(payloads, 1):
        path = payload_dir / f"batch_{idx:04d}.json"
        write_json(path, payload)
        payload_files.append(path)

    summary = {
        "rows": len(rows),
        "batches": len(payload_files),
        "fields": write_fields,
        "write_profile": write_profile,
        "payload_dir": str(payload_dir),
        "target_table_id": args.table_id,
        "execute": args.execute,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    if args.dry_run_lark and payload_files:
        run_lark_batch(payload_files[0], base_token=args.base_token, table_id=args.table_id, dry_run=True)

    if args.execute:
        created = 0
        created_record_ids: list[str] = []
        for path in payload_files:
            result = run_lark_batch(path, base_token=args.base_token, table_id=args.table_id, dry_run=False)
            record_ids = result.get("data", {}).get("record_id_list", []) or []
            created += len(record_ids)
            created_record_ids.extend(record_ids)
            time.sleep(0.4)
        result_path = Path(args.result_output) if args.result_output else plan_path.with_name(f"{plan_path.stem}_result.json")
        if not result_path.is_absolute():
            result_path = PROJECT_ROOT / result_path
        write_json(
            result_path,
            {"created": created, "batches": len(payload_files), "record_id_list": created_record_ids},
        )
        print(json.dumps({"created": created, "batches": len(payload_files)}, ensure_ascii=False, indent=2))
    return 0


def build_payloads(
    projects: list[dict[str, Any]],
    *,
    batch_size: int,
    write_fields: list[str],
    write_profile: str,
) -> list[dict[str, Any]]:
    rows = [project_to_row(project, write_profile=write_profile) for project in projects]
    return [
        {"fields": write_fields, "rows": rows[idx : idx + batch_size]}
        for idx in range(0, len(rows), batch_size)
    ]


def resolve_write_profile(requested_profile: str, table_id: str) -> str:
    if requested_profile != "auto":
        return requested_profile
    return "materials" if table_id == MATERIALS_TABLE_ID else "legacy"


def write_fields_for_profile(write_profile: str) -> list[str]:
    if write_profile == "materials":
        return MATERIALS_WRITE_FIELDS
    return LEGACY_WRITE_FIELDS


def project_to_row(project: dict[str, Any], *, write_profile: str) -> list[Any]:
    detail = (project.get("raw") or {}).get("detail") if isinstance(project.get("raw"), dict) else {}
    detail = detail if isinstance(detail, dict) else {}
    source_url = str(project.get("source_url") or "")
    shared_values = [
        text(project.get("title")),
        clean_html(project.get("description") or detail.get("courseDescribeCn") or detail.get("professorIntroduceCn")),
        number_or_none(project.get("course_difficulty") or detail.get("courseDifficulty")),
        enrollment_status(detail.get("enrollmentStatus") or (project.get("raw") or {}).get("enrollmentStatus")),
        text(project.get("category")),
        text(project.get("professor")),
        clean_html(detail.get("professorIntroduceCn") or detail.get("professorRemark") or project.get("description")),
        source_url,
        text(detail.get("professorAvatar") or detail.get("researchProfessorAvatar")),
        teaching_mode(project) if write_profile == "materials" else project_type(source_url, detail),
        source_url,
        text(project.get("professor_position") or detail.get("professorPosition") or detail.get("researchPositionCn")),
        text(project.get("direction") or project.get("major_name")),
        text(project.get("keywords") if isinstance(project.get("keywords"), str) else " | ".join(project.get("keywords") or [])),
        "HIREP PBL",
        text(project.get("university")),
        clean_html(detail.get("suitablePeopleCn")),
        clean_html(detail.get("courseRequireCn")),
    ]
    research_scope = clean_html(detail.get("customizedTopic") or detail.get("previousPapers"))
    return [
        *shared_values[:15],
        research_scope,
        *shared_values[15:],
    ]


def run_lark_batch(path: Path, *, base_token: str, table_id: str, dry_run: bool) -> dict[str, Any]:
    rel = path.relative_to(PROJECT_ROOT)
    cmd = [
        "lark-cli",
        "base",
        "+record-batch-create",
        "--base-token",
        base_token,
        "--table-id",
        table_id,
        "--json",
        f"@{rel}",
        "--as",
        "user",
        "--format",
        "json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, check=True, text=True, capture_output=True, cwd=PROJECT_ROOT)
    payload = json.loads(result.stdout)
    print(json.dumps(payload if dry_run else {"ok": payload.get("ok"), "created": len(payload.get("data", {}).get("record_id_list", []) or [])}, ensure_ascii=False, indent=2))
    return payload


def course_extend_id(url: str) -> str:
    query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    return str(query.get("courseExtendId") or "")


def project_type(source_url: str, detail: dict[str, Any]) -> str | None:
    try:
        h5_type = int(detail.get("h5Type") or dict(parse_qsl(urlsplit(source_url).query)).get("h5Type") or 0)
    except (TypeError, ValueError):
        h5_type = 0
    if h5_type == 1:
        return "CIS Research"
    if h5_type in {2, 3}:
        return "iFUTURE Research"
    return None


def teaching_mode(project: dict[str, Any]) -> str | None:
    """Map the source teaching-mode enum to the target table's fixed select options."""
    value = project.get("teaching_mode")
    if value in (None, "") and isinstance(project.get("raw"), dict):
        detail = (project["raw"].get("detail") or {})
        listing = (project["raw"].get("list") or {})
        value = detail.get("teachingMode") or listing.get("teachingMode")
    try:
        return {1: "线上", 2: "线下"}.get(int(value))
    except (TypeError, ValueError):
        return None


def enrollment_status(value: Any) -> str | None:
    try:
        return "招生中" if int(value) == 1 else "截止"
    except (TypeError, ValueError):
        return None


def clean_html(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text_value = str(value)
    text_value = re.sub(r"<br\s*/?>", "\n", text_value, flags=re.I)
    text_value = re.sub(r"</p\s*>", "\n", text_value, flags=re.I)
    text_value = re.sub(r"<[^>]+>", "", text_value)
    text_value = html.unescape(text_value)
    text_value = re.sub(r"[ \t\r\f\v]+", " ", text_value)
    text_value = re.sub(r"\n{3,}", "\n\n", text_value).strip()
    return text_value or None


def text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def number_or_none(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


if __name__ == "__main__":
    raise SystemExit(main())
