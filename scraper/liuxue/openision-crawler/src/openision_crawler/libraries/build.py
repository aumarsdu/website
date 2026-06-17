from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openision_crawler.libraries.cases import build_cases, count_cases_by_program
from openision_crawler.libraries.io import contains_sensitive_key, read_jsonl, write_jsonl
from openision_crawler.libraries.programs import build_programs
from openision_crawler.libraries.quality import build_quality_report
from openision_crawler.libraries.schools import build_schools


def _raw_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = read_jsonl(path)
    records = [row.get("record") for row in rows if isinstance(row.get("record"), dict)]
    return [record for record in records if isinstance(record, dict)]


def _source_rows(project_root: Path, name: str) -> list[dict[str, Any]]:
    raw = _raw_records(project_root / "data" / "raw" / f"{name}_list.jsonl")
    if raw:
        return raw
    return read_jsonl(project_root / "data" / "normalized" / f"{name}_list.jsonl")


def _markdown_report(report: dict[str, Any]) -> str:
    counts = report["counts"]
    joins = report["joins"]
    quality = report["quality"]
    security = report.get("security", {})
    lines = [
        "# Library Quality Report",
        "",
        "## Counts",
        f"- programs: {counts['programs']}",
        f"- schools: {counts['schools']}",
        f"- cases: {counts['cases']}",
        "",
        "## Joins",
        f"- case_program_join_failures: {joins['case_program_join_failures']}",
        f"- case_school_join_failures: {joins['case_school_join_failures']}",
        "",
        "## Quality",
        f"- unknown_fee_programs: {quality['unknown_fee_programs']}",
        f"- invalid_year_cases: {quality['invalid_year_cases']}",
        f"- unknown_english_score_cases: {quality['unknown_english_score_cases']}",
        f"- unknown_school_tag_cases: {quality['unknown_school_tag_cases']}",
        "",
        "## Security",
        f"- sensitive_key_rows: {security.get('sensitive_key_rows', 0)}",
        "",
    ]
    return "\n".join(lines)


def build_libraries(project_root: Path) -> dict[str, Any]:
    output_dir = project_root / "data" / "libraries"
    report_dir = project_root / "data" / "reports"

    major_rows = _source_rows(project_root, "majors")
    case_rows = _source_rows(project_root, "cases")
    cases = build_cases(case_rows)
    programs = build_programs(major_rows, count_cases_by_program(case_rows))
    schools = build_schools(programs, cases)

    program_rows = [item.to_dict() for item in programs]
    case_output_rows = [item.to_dict() for item in cases]
    school_rows = [item.to_dict() for item in schools]
    sensitive_count = sum(
        1
        for row in [*program_rows, *case_output_rows, *school_rows]
        if contains_sensitive_key(row)
    )

    write_jsonl(output_dir / "program_library.jsonl", program_rows)
    write_jsonl(output_dir / "admission_case_library.jsonl", case_output_rows)
    write_jsonl(output_dir / "school_library.jsonl", school_rows)

    report = build_quality_report(programs, cases, schools)
    report["security"] = {"sensitive_key_rows": sensitive_count}
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "library_quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    (report_dir / "library_quality_report.md").write_text(_markdown_report(report), encoding="utf-8")
    return report
