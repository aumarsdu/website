from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_WIKI_URL = (
    "https://shuzimumin.feishu.cn/wiki/TSwJwfaxqi4vVHkWo3kcUm0Rn7d"
    "?table=tbl1zOSLAGq6NT89&view=vew620fOmi"
)
DEFAULT_TABLE_ID = "tbl1zOSLAGq6NT89"
DEFAULT_OUTPUT_DIR = Path("output/lark_sync")

EXISTING_FIELDS = ["课题信息", "教授姓名", "网页链接", "课程链接"]
WRITE_FIELDS = [
    "学校",
    "课程链接",
    "教授简介",
    "周期",
    "教授论文指导范围（CIS特有）",
    "教授级别",
    "项目方",
    "二级学科",
    "课题信息",
    "适合学生方向",
    "适合专业 (Major)",
    "招生状态",
    "建议先修课程",
    "开课日期",
    "难度",
    "项目类型",
    "适合年级",
    "教授头像",
    "教授姓名",
    "课题简介",
    "一级学科",
    "售价",
    "网页链接",
]
EXPECTED_FIELD_TYPES = {
    **{field: "text" for field in WRITE_FIELDS},
    "难度": "number",
    "开课日期": "datetime",
    "适合年级": "select",
}
READ_ONLY_FIELD_TYPES = {"auto_number", "lookup", "formula", "created_at", "updated_at", "created_by", "updated_by"}
SELECT_FIELDS = {"适合年级"}
DEFAULT_ROOTS = [
    Path("output"),
    Path("output_domestic"),
    Path("output/full_refresh/20260703-new-check/sou_tools"),
    Path("output/full_refresh/20260703-new-check/domestic"),
    Path("output/incremental/20260602-082933"),
    Path("output/incremental/20260602-082933/new_only"),
    Path("output/full_refresh/20260602-full-refresh/sou_tools"),
    Path("output/full_refresh/20260602-full-refresh/domestic"),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync local crawled topics into a Lark Base table, skipping existing topics."
    )
    parser.add_argument("--wiki-url", default=DEFAULT_WIKI_URL)
    parser.add_argument("--base-token", default=None)
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--root", action="append", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--as-identity", choices=["user", "bot"], default="user")
    parser.add_argument("--write", action="store_true", help="Actually create missing records.")
    args = parser.parse_args()

    roots = args.root or DEFAULT_ROOTS
    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_token = args.base_token or resolve_base_token(args.wiki_url)
    field_types = validate_field_schema(
        load_table_fields(base_token=base_token, table_id=args.table_id, identity=args.as_identity)
    )

    existing_keys, existing_count = load_existing_keys(
        base_token=base_token,
        table_id=args.table_id,
        identity=args.as_identity,
        output_dir=args.output_dir,
    )
    rows, meta, skipped_local_duplicate = build_missing_rows(roots, existing_keys)
    select_validation = validate_select_fields(
        base_token=base_token,
        table_id=args.table_id,
        identity=args.as_identity,
        rows=rows,
    )
    batch_files = write_batch_files(args.output_dir, rows, args.batch_size)

    summary = {
        "table_id": args.table_id,
        "roots": [str(root) for root in roots],
        "existing_records": existing_count,
        "pending_create": len(rows),
        "skipped_local_duplicate": skipped_local_duplicate,
        "batch_files": [str(path) for path in batch_files],
        "fields": WRITE_FIELDS,
        "write_enabled": args.write,
    }
    write_json(args.output_dir / "sync_summary.json", summary)
    write_json(args.output_dir / "pending_meta.json", meta)
    write_json(
        args.output_dir / "field_validation.json",
        {"field_types": field_types, "select_validation": select_validation},
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not args.write or not rows:
        return 0

    created_ids = create_records(
        base_token=base_token,
        table_id=args.table_id,
        identity=args.as_identity,
        batch_files=batch_files,
    )
    write_json(args.output_dir / "created_record_ids.json", created_ids)
    print(json.dumps({"created_total": len(created_ids)}, ensure_ascii=False))
    return 0


def resolve_base_token(wiki_url: str) -> str:
    result = run_lark(
        [
            "base",
            "+url-resolve",
            "--url",
            wiki_url,
            "--format",
            "json",
        ]
    )
    data = result.get("data") or {}
    base_token = data.get("base_token") or data.get("baseToken")
    if not base_token:
        raise RuntimeError("URL did not resolve to a Base token")
    return str(base_token)


def load_table_fields(*, base_token: str, table_id: str, identity: str) -> list[dict[str, Any]]:
    result = run_lark(
        [
            "base",
            "+field-list",
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--as",
            identity,
            "--format",
            "json",
        ]
    )
    data = result.get("data") or {}
    fields = data.get("fields") or []
    return [field for field in fields if isinstance(field, dict)]


def validate_field_schema(fields: list[dict[str, Any]]) -> dict[str, str]:
    actual_types = {
        str(field.get("name")): str(field.get("type"))
        for field in fields
        if field.get("name") not in (None, "") and field.get("type") not in (None, "")
    }
    missing = [field for field in WRITE_FIELDS if field not in actual_types]
    mismatches = {
        field: {"expected": expected, "actual": actual_types.get(field)}
        for field, expected in EXPECTED_FIELD_TYPES.items()
        if actual_types.get(field) != expected
    }
    read_only = {
        field: field_type
        for field, field_type in actual_types.items()
        if field in WRITE_FIELDS and field_type in READ_ONLY_FIELD_TYPES | {"attachment"}
    }
    if missing or mismatches or read_only:
        raise RuntimeError(
            "Target Base schema is incompatible with this sync: "
            + json.dumps(
                {"missing": missing, "mismatches": mismatches, "read_only": read_only}, ensure_ascii=False
            )
        )
    return {field: actual_types[field] for field in WRITE_FIELDS}


def validate_select_fields(
    *,
    base_token: str,
    table_id: str,
    identity: str,
    rows: list[list[Any]],
) -> list[dict[str, Any]]:
    validation: list[dict[str, Any]] = []
    for field in SELECT_FIELDS:
        index = WRITE_FIELDS.index(field)
        requested_values = sorted({row[index] for row in rows if row[index] is not None})
        result = run_lark(
            [
                "base",
                "+field-search-options",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--field-id",
                field,
                "--limit",
                "200",
                "--as",
                identity,
                "--format",
                "json",
            ]
        )
        options = (result.get("data") or {}).get("options") or []
        allowed_values = sorted(
            str(option["name"])
            for option in options
            if isinstance(option, dict) and option.get("name") not in (None, "")
        )
        unknown_values = sorted(set(requested_values) - set(allowed_values))
        if unknown_values:
            raise RuntimeError(
                f"Select field {field} has unknown values: {json.dumps(unknown_values, ensure_ascii=False)}"
            )
        validation.append(
            {
                "field": field,
                "requested_values": requested_values,
                "allowed_values": allowed_values,
            }
        )
    return validation


def load_existing_keys(
    *,
    base_token: str,
    table_id: str,
    identity: str,
    output_dir: Path,
) -> tuple[set[tuple[str, Any]], int]:
    existing: list[dict[str, Any]] = []
    offset = 0
    while True:
        cmd = [
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
            identity,
            "--format",
            "json",
        ]
        for field in EXISTING_FIELDS:
            cmd.extend(["--field-id", field])
        result = run_lark(cmd)
        data = result.get("data") or {}
        rows = data.get("data") or []
        record_ids = data.get("record_id_list") or []
        for record_id, row in zip(record_ids, rows, strict=False):
            record = dict(zip(EXISTING_FIELDS, row, strict=False))
            record["_record_id"] = record_id
            existing.append(record)
        if not data.get("has_more"):
            break
        offset += len(rows)
        time.sleep(0.2)

    keys: set[tuple[str, Any]] = set()
    for record in existing:
        for field in ("网页链接", "课程链接"):
            url = extract_url(record.get(field))
            if url:
                keys.add(("url", url))
                course_id = course_id_from_url(url)
                if course_id:
                    keys.add(("id", course_id))
        title = str(record.get("课题信息") or "").strip()
        teacher = str(record.get("教授姓名") or "").strip()
        if title and teacher:
            keys.add(("title_teacher", (title, teacher)))

    write_json(output_dir / "existing_records.json", existing)
    write_json(output_dir / "existing_keys.json", serialize_keys(keys))
    return keys, len(existing)


def build_missing_rows(
    roots: list[Path],
    existing_keys: set[tuple[str, Any]],
) -> tuple[list[list[Any]], list[dict[str, Any]], int]:
    rows: list[list[Any]] = []
    meta: list[dict[str, Any]] = []
    seen_local: set[tuple[str, Any]] = set()
    skipped_local_duplicate = 0

    for root in roots:
        organized_root = root / "organized_by_site"
        if not organized_root.exists():
            continue
        for detail_path in organized_root.glob("**/详情页信息.json"):
            info = read_json(detail_path)
            list_record = info.get("list_record") or {}
            detail_record = info.get("detail_record") or {}
            title = as_text(first(info.get("title"), detail_record.get("name"), list_record.get("name")))
            teacher = as_text(
                first(info.get("teacherName"), detail_record.get("teacherName"), list_record.get("teacherName"))
            )
            url = share_url(info)
            course_id = course_id_from_url(url) or as_text(info.get("id"))
            keys = []
            if url:
                keys.append(("url", url))
            if course_id:
                keys.append(("id", course_id))
            if title and teacher:
                keys.append(("title_teacher", (title, teacher)))
            if any(key in existing_keys for key in keys):
                continue
            if any(key in seen_local for key in keys):
                skipped_local_duplicate += 1
                continue
            for key in keys:
                seen_local.add(key)

            row_map = build_row_map(info, list_record, detail_record, title, teacher, url)
            rows.append([row_map.get(field) for field in WRITE_FIELDS])
            meta.append(
                {
                    "source_root": str(root),
                    "detail_file": str(detail_path),
                    "title": title,
                    "teacher": teacher,
                    "url": url,
                }
            )
    return rows, meta, skipped_local_duplicate


def build_row_map(
    info: dict[str, Any],
    list_record: dict[str, Any],
    detail_record: dict[str, Any],
    title: str | None,
    teacher: str | None,
    url: str | None,
) -> dict[str, Any]:
    return {
        "学校": as_text(
            first(detail_record.get("teacherSchool"), list_record.get("teacherSchool"), detail_record.get("dTeacherSchool"))
        ),
        "课程链接": url,
        "教授简介": as_text(
            first(detail_record.get("teacherDetail"), detail_record.get("teacherSchoolDetail"), detail_record.get("dTeacherDetail"))
        ),
        "周期": as_text(detail_record.get("cycle")),
        "教授论文指导范围（CIS特有）": as_text(detail_record.get("output")),
        "教授级别": as_text(first(detail_record.get("teacherLevel"), list_record.get("teacherLevel"))),
        "项目方": as_text(detail_record.get("types")),
        "二级学科": None if info.get("direction") == "未分方向" else as_text(info.get("direction")),
        "课题信息": title,
        "适合学生方向": as_text(first(detail_record.get("suggestBasics"), list_record.get("suggestBasics"))),
        "适合专业 (Major)": as_text(list_record.get("fitList")),
        "招生状态": as_text(first(detail_record.get("position"), list_record.get("position"))),
        "建议先修课程": as_text(detail_record.get("foundationCourseName")),
        "开课日期": normalize_date(first(detail_record.get("schoolBegins"), list_record.get("schoolBegins"))),
        "难度": number_or_none(first(detail_record.get("starNum"), list_record.get("starNum"))),
        "项目类型": as_text(first(detail_record.get("types"), list_record.get("types"))),
        "适合年级": grade(list_record, detail_record),
        "教授头像": as_text(first(detail_record.get("teacherHeadImgUrl"), list_record.get("teacherHeadImgUrl"))),
        "教授姓名": teacher,
        "课题简介": as_text(first(detail_record.get("introduce"), detail_record.get("projectBackground"))),
        "一级学科": as_text(info.get("category")),
        "售价": as_text(detail_record.get("managementExpense")),
        "网页链接": url,
    }


def create_records(
    *,
    base_token: str,
    table_id: str,
    identity: str,
    batch_files: list[Path],
) -> list[str]:
    created: list[str] = []
    for index, path in enumerate(batch_files, start=1):
        result = run_lark(
            [
                "base",
                "+record-batch-create",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--json",
                "@" + str(path),
                "--as",
                identity,
                "--format",
                "json",
            ]
        )
        record_ids = (result.get("data") or {}).get("record_id_list") or []
        created.extend(record_ids)
        print(json.dumps({"batch": index, "created": len(record_ids), "total_created": len(created)}, ensure_ascii=False))
        time.sleep(0.5)
    return created


def write_batch_files(output_dir: Path, rows: list[list[Any]], batch_size: int) -> list[Path]:
    paths: list[Path] = []
    for index in range(0, len(rows), batch_size):
        payload = {"fields": WRITE_FIELDS, "rows": rows[index : index + batch_size]}
        path = output_dir / f"batch_{index // batch_size + 1:03d}.json"
        write_json(path, payload)
        paths.append(path)
    return paths


def run_lark(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(["lark-cli", *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stdout + result.stderr)[-2000:])
    text = result.stdout
    start = text.find("{")
    if start < 0:
        raise RuntimeError(f"lark-cli returned no JSON: {text[-1000:]}")
    return json.loads(text[start:])


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def as_text(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    return text or None


def extract_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    markdown_match = re.search(r"\((https?://[^)]+)\)", value)
    if markdown_match:
        return markdown_match.group(1)
    raw_match = re.search(r"https?://[^\s\]]+", value)
    return raw_match.group(0) if raw_match else value.strip() or None


def collect_urls(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for inner in value.values():
            found.extend(collect_urls(inner))
    elif isinstance(value, list):
        for inner in value:
            found.extend(collect_urls(inner))
    elif isinstance(value, str):
        found.extend(match.rstrip("),.;]") for match in re.findall(r"https?://[^\s\"'<>]+", value))
    return found


def share_url(info: dict[str, Any]) -> str | None:
    for url in collect_urls(info):
        if "share?id=" in url:
            return url
    course_id = info.get("id")
    return f"https://sou-m.gecacademy.cn/share?id={course_id}" if course_id else None


def course_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"id=([^&\s)]+)", url)
    return match.group(1) if match else None


def normalize_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        candidate = text[:19] if fmt.endswith("%S") else text[:10]
        try:
            return datetime.strptime(candidate, fmt).strftime("%Y-%m-%d 00:00:00")
        except ValueError:
            pass
    return None


def number_or_none(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def grade(list_record: dict[str, Any], detail_record: dict[str, Any]) -> str | None:
    senior = bool(first(detail_record.get("suggestSenior"), list_record.get("suggestSenior")))
    college = bool(first(detail_record.get("suggestCollege"), list_record.get("suggestCollege")))
    master = bool(first(detail_record.get("suggestMaster"), list_record.get("suggestMaster")))
    middle = bool(first(detail_record.get("suggestMiddle"), list_record.get("suggestMiddle")))
    if senior and college:
        return "高中生/大学生"
    if college or master:
        return "大学生及以上"
    if senior or middle:
        return "高中生"
    return None


def serialize_keys(keys: set[tuple[str, Any]]) -> list[list[Any]]:
    serializable = []
    for kind, value in sorted(keys, key=str):
        if kind == "title_teacher":
            serializable.append([kind, list(value)])
        else:
            serializable.append([kind, value])
    return serializable


if __name__ == "__main__":
    raise SystemExit(main())
