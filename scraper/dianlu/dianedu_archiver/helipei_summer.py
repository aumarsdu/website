from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
import argparse
import json
import re
import sqlite3

from .utils import utc_now


DEFAULT_SOURCE_DB = Path("data/processed/dianedu.sqlite")
DEFAULT_OUTPUT_DB = Path("data/processed/helipei_summer_programs.sqlite")

SUMMER_TYPES = {
    "低龄走读营",
    "无学分大学营",
    "在线夏校",
    "中学营",
    "有学分大学营",
    "艺术营",
    "综合营",
    "语言营",
    "户外体育营",
    "海外课程",
    "精英夏校",
    "天才营",
    "辩论营",
    "无忧畅学夏校",
    "科技营",
    "数学营",
    "亲子营",
    "插班",
    "探校",
}

PRIMARY_SUMMER_CATEGORY = "夏校等"
EXTENSION_CATEGORIES = {"插班", "探校"}
ADJACENT_TYPES = {"海外科研", "在线科研", "国内科研", "思维训练"}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        data = data.strip()
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


@dataclass(slots=True)
class ImportStats:
    source_projects: int = 0
    summer_programs: int = 0
    sessions: int = 0
    costs: int = 0
    tags: int = 0
    quality_issues: int = 0


def build_helipei_summer_db(source_db: Path = DEFAULT_SOURCE_DB, output_db: Path = DEFAULT_OUTPUT_DB) -> ImportStats:
    source_db = source_db.resolve()
    output_db = output_db.resolve()
    if not source_db.exists():
        raise FileNotFoundError(f"source db not found: {source_db}")
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()

    stats = ImportStats()
    source = sqlite3.connect(source_db)
    source.row_factory = sqlite3.Row
    target = sqlite3.connect(output_db)
    target.row_factory = sqlite3.Row
    try:
        create_schema(target)
        run_id = insert_import_run(target, source_db, output_db)
        rows = source.execute("SELECT canonical_url, data_json FROM projects ORDER BY title").fetchall()
        stats.source_projects = len(rows)
        for row in rows:
            record = json.loads(row["data_json"])
            entity = record.get("fields") or {}
            source_project_id = str(record.get("id") or entity.get("ID") or "")
            insert_source_project(target, run_id, record, entity)
            if not is_summer_candidate(record, entity):
                continue
            program = normalize_program(record, entity, run_id)
            insert_program(target, program)
            stats.summer_programs += 1
            stats.sessions += insert_sessions(target, program, entity)
            stats.costs += insert_costs(target, program, entity)
            stats.tags += insert_tags(target, program, record, entity)
            stats.quality_issues += insert_quality_issues(target, program)
        insert_data_dictionary(target)
        create_views(target)
        finish_import_run(target, run_id, stats)
        target.commit()
    finally:
        source.close()
        target.close()
    return stats


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE import_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_db_path TEXT NOT NULL,
          output_db_path TEXT NOT NULL,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          source_project_count INTEGER DEFAULT 0,
          summer_program_count INTEGER DEFAULT 0,
          session_count INTEGER DEFAULT 0,
          cost_count INTEGER DEFAULT 0,
          tag_count INTEGER DEFAULT 0,
          quality_issue_count INTEGER DEFAULT 0,
          notes TEXT
        );

        CREATE TABLE source_projects (
          source_project_id TEXT PRIMARY KEY,
          import_run_id INTEGER NOT NULL,
          source_url TEXT,
          source_canonical_url TEXT,
          source_category TEXT,
          source_project_type TEXT,
          source_title TEXT,
          raw_json TEXT NOT NULL,
          imported_at TEXT NOT NULL,
          FOREIGN KEY (import_run_id) REFERENCES import_runs(id)
        );

        CREATE TABLE summer_programs (
          id TEXT PRIMARY KEY,
          source_project_id TEXT NOT NULL,
          import_run_id INTEGER NOT NULL,
          title TEXT NOT NULL,
          one_line_summary TEXT,
          library_scope TEXT NOT NULL,
          source_category TEXT,
          source_project_type TEXT,
          standard_category TEXT,
          standard_subcategory TEXT,
          country TEXT,
          country_en TEXT,
          city_region TEXT,
          city_region_en TEXT,
          location_display TEXT,
          min_grade_name TEXT,
          max_grade_name TEXT,
          min_grade_order INTEGER,
          max_grade_order INTEGER,
          age_range_text TEXT,
          residential_type TEXT,
          credit_type TEXT,
          delivery_mode TEXT,
          application_deadline_raw TEXT,
          application_start_date TEXT,
          application_requirement_text TEXT,
          description_text TEXT,
          description_html TEXT,
          organization_name TEXT,
          homepage_url TEXT,
          status TEXT,
          data_quality_status TEXT NOT NULL,
          recommendation_score INTEGER NOT NULL,
          advisor_notes TEXT,
          raw_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (source_project_id) REFERENCES source_projects(source_project_id),
          FOREIGN KEY (import_run_id) REFERENCES import_runs(id)
        );

        CREATE TABLE program_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          program_id TEXT NOT NULL,
          start_date TEXT,
          end_date TEXT,
          date_range_raw TEXT NOT NULL,
          duration_days INTEGER,
          availability_status TEXT DEFAULT 'unknown',
          FOREIGN KEY (program_id) REFERENCES summer_programs(id)
        );

        CREATE TABLE program_costs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          program_id TEXT NOT NULL,
          fee_type TEXT NOT NULL,
          amount REAL,
          currency TEXT,
          raw_value TEXT,
          normalized_note TEXT,
          FOREIGN KEY (program_id) REFERENCES summer_programs(id)
        );

        CREATE TABLE program_tags (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          program_id TEXT NOT NULL,
          tag_type TEXT NOT NULL,
          tag_value TEXT NOT NULL,
          confidence INTEGER DEFAULT 80,
          source TEXT NOT NULL,
          FOREIGN KEY (program_id) REFERENCES summer_programs(id)
        );

        CREATE TABLE program_assets (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          program_id TEXT NOT NULL,
          asset_url TEXT NOT NULL,
          asset_type TEXT,
          source_field TEXT,
          authorized_download_status TEXT DEFAULT 'not_downloaded',
          FOREIGN KEY (program_id) REFERENCES summer_programs(id)
        );

        CREATE TABLE data_quality_issues (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          program_id TEXT NOT NULL,
          issue_type TEXT NOT NULL,
          severity TEXT NOT NULL,
          field_name TEXT,
          message TEXT NOT NULL,
          FOREIGN KEY (program_id) REFERENCES summer_programs(id)
        );

        CREATE TABLE data_dictionary (
          table_name TEXT NOT NULL,
          column_name TEXT NOT NULL,
          data_type TEXT NOT NULL,
          nullable TEXT NOT NULL,
          description TEXT NOT NULL,
          source_mapping TEXT,
          PRIMARY KEY (table_name, column_name)
        );

        CREATE INDEX idx_summer_programs_scope ON summer_programs(library_scope);
        CREATE INDEX idx_summer_programs_country ON summer_programs(country);
        CREATE INDEX idx_summer_programs_type ON summer_programs(standard_category, standard_subcategory);
        CREATE INDEX idx_summer_programs_grade ON summer_programs(min_grade_order, max_grade_order);
        CREATE INDEX idx_program_tags_lookup ON program_tags(tag_type, tag_value);
        """
    )


def insert_import_run(conn: sqlite3.Connection, source_db: Path, output_db: Path) -> int:
    cur = conn.execute(
        """
        INSERT INTO import_runs (source_db_path, output_db_path, started_at, notes)
        VALUES (?, ?, ?, ?)
        """,
        (
            str(source_db),
            str(output_db),
            utc_now(),
            "Converted DianEdu archive into Helipei summer program library schema.",
        ),
    )
    return int(cur.lastrowid)


def finish_import_run(conn: sqlite3.Connection, run_id: int, stats: ImportStats) -> None:
    conn.execute(
        """
        UPDATE import_runs
        SET finished_at = ?,
            source_project_count = ?,
            summer_program_count = ?,
            session_count = ?,
            cost_count = ?,
            tag_count = ?,
            quality_issue_count = ?
        WHERE id = ?
        """,
        (
            utc_now(),
            stats.source_projects,
            stats.summer_programs,
            stats.sessions,
            stats.costs,
            stats.tags,
            stats.quality_issues,
            run_id,
        ),
    )


def insert_source_project(conn: sqlite3.Connection, run_id: int, record: dict[str, Any], entity: dict[str, Any]) -> None:
    source_project_id = str(record.get("id") or entity.get("ID") or "")
    conn.execute(
        """
        INSERT INTO source_projects
        (source_project_id, import_run_id, source_url, source_canonical_url, source_category, source_project_type, source_title, raw_json, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_project_id,
            run_id,
            record.get("source_url"),
            record.get("canonical_url"),
            record.get("category"),
            record.get("project_type"),
            record.get("title"),
            json.dumps(record, ensure_ascii=False, sort_keys=True),
            utc_now(),
        ),
    )


def is_summer_candidate(record: dict[str, Any], entity: dict[str, Any]) -> bool:
    category = clean(record.get("category") or nested_name(entity.get("ProjectTypeLv1")))
    project_type = clean(record.get("project_type") or nested_name(entity.get("ProjectTypeLv2")))
    title = clean(record.get("title") or entity.get("Name"))
    if category == PRIMARY_SUMMER_CATEGORY or category in EXTENSION_CATEGORIES:
        return True
    if project_type in SUMMER_TYPES:
        return True
    text = f"{title} {category} {project_type}"
    return bool(re.search(r"夏校|夏令营|暑期|营\b|插班|探校|pre-college|camp|summer", text, re.I))


def normalize_program(record: dict[str, Any], entity: dict[str, Any], run_id: int) -> dict[str, Any]:
    source_project_id = str(record.get("id") or entity.get("ID") or "")
    source_category = clean(record.get("category") or nested_name(entity.get("ProjectTypeLv1")))
    source_project_type = clean(record.get("project_type") or nested_name(entity.get("ProjectTypeLv2")))
    country = nested_name(entity.get("Country")) or split_location(record.get("location"))[0]
    city = nested_name(entity.get("City")) or split_location(record.get("location"))[1]
    min_grade_name, min_grade_order = grade_name_and_order(entity.get("MinGrade"), record.get("grade"), first=True)
    max_grade_name, max_grade_order = grade_name_and_order(entity.get("MaxGrade"), record.get("grade"), first=False)
    description_html = first_text(entity.get("Content"), entity.get("Inctroduction"), entity.get("CourseArrangement"))
    requirement_html = first_text(entity.get("ApplicationRequirement"))
    application_fee_html = first_text(entity.get("ApplicationFee"))
    delivery_mode = infer_delivery_mode(source_project_type, record.get("title"), description_html)
    residential_type = infer_residential(entity.get("Residential"), source_project_type, record.get("title"), description_html)
    credit_type = infer_credit(entity.get("HasCredit"), source_project_type, record.get("title"), description_html)
    standard_category, standard_subcategory = standardize_category(source_category, source_project_type, record.get("title"))
    issues = quality_issue_types(entity, record, description_html)
    return {
        "id": f"hp-summer-{source_project_id}",
        "source_project_id": source_project_id,
        "import_run_id": run_id,
        "title": clean(record.get("title") or entity.get("Name")) or "未命名项目",
        "one_line_summary": summarize(record, entity, description_html),
        "library_scope": infer_library_scope(source_category, source_project_type),
        "source_category": source_category,
        "source_project_type": source_project_type,
        "standard_category": standard_category,
        "standard_subcategory": standard_subcategory,
        "country": country,
        "country_en": nested_en_name(entity.get("Country")),
        "city_region": city,
        "city_region_en": nested_en_name(entity.get("City")),
        "location_display": " / ".join(x for x in [country, city] if x),
        "min_grade_name": min_grade_name,
        "max_grade_name": max_grade_name,
        "min_grade_order": min_grade_order,
        "max_grade_order": max_grade_order,
        "age_range_text": clean(entity.get("AgeOthers")),
        "residential_type": residential_type,
        "credit_type": credit_type,
        "delivery_mode": delivery_mode,
        "application_deadline_raw": clean(entity.get("ApplicationDeadline")),
        "application_start_date": clean(entity.get("ApplicationStartDate")),
        "application_requirement_text": html_to_text(requirement_html),
        "description_text": html_to_text(description_html),
        "description_html": description_html,
        "organization_name": nested_name(entity.get("Organization")) or clean(entity.get("OrganizationName")),
        "homepage_url": clean(entity.get("HomePage")),
        "status": clean(entity.get("ProjectStatus")) or "unknown",
        "data_quality_status": "needs_review" if issues else "ready",
        "recommendation_score": recommendation_score(record, entity, issues, delivery_mode, credit_type),
        "advisor_notes": build_advisor_notes(record, entity, application_fee_html),
        "raw_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "_issues": issues,
        "_assets": sorted(set(record.get("assets") or [])),
    }


def insert_program(conn: sqlite3.Connection, program: dict[str, Any]) -> None:
    keys = [
        "id",
        "source_project_id",
        "import_run_id",
        "title",
        "one_line_summary",
        "library_scope",
        "source_category",
        "source_project_type",
        "standard_category",
        "standard_subcategory",
        "country",
        "country_en",
        "city_region",
        "city_region_en",
        "location_display",
        "min_grade_name",
        "max_grade_name",
        "min_grade_order",
        "max_grade_order",
        "age_range_text",
        "residential_type",
        "credit_type",
        "delivery_mode",
        "application_deadline_raw",
        "application_start_date",
        "application_requirement_text",
        "description_text",
        "description_html",
        "organization_name",
        "homepage_url",
        "status",
        "data_quality_status",
        "recommendation_score",
        "advisor_notes",
        "raw_json",
        "created_at",
        "updated_at",
    ]
    conn.execute(
        f"INSERT INTO summer_programs ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
        tuple(program.get(key) for key in keys),
    )
    for asset_url in program.get("_assets", []):
        conn.execute(
            """
            INSERT INTO program_assets (program_id, asset_url, asset_type, source_field, authorized_download_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (program["id"], asset_url, infer_asset_type(asset_url), "record.assets", "outside_main_domain" if "cdn.dianedu.com" in asset_url else "not_downloaded"),
        )


def insert_sessions(conn: sqlite3.Connection, program: dict[str, Any], entity: dict[str, Any]) -> int:
    ranges = collect_date_ranges(entity)
    count = 0
    for raw in ranges:
        start_date, end_date = parse_date_range(raw)
        conn.execute(
            """
            INSERT INTO program_sessions (program_id, start_date, end_date, date_range_raw, duration_days, availability_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (program["id"], start_date, end_date, raw, duration_days(start_date, end_date), "unknown"),
        )
        count += 1
    return count


def insert_costs(conn: sqlite3.Connection, program: dict[str, Any], entity: dict[str, Any]) -> int:
    mapping = [
        ("tuition", entity.get("Tuition"), entity.get("Currency"), "外币学费"),
        ("service_fee", entity.get("ServiceFee"), "CNY", "申请服务费"),
        ("hot_sale_fee", entity.get("HotSaleFee"), "CNY", "热卖价 / 当前服务费"),
        ("early_bird_service_fee", entity.get("EarlyBirdServiceFee"), "CNY", "早鸟服务费"),
        ("late_bird_service_fee", entity.get("LateBirdServiceFee"), "CNY", "晚鸟服务费"),
        ("current_price", entity.get("CurrentPrice"), "CNY", "当前价格"),
    ]
    count = 0
    for fee_type, raw_value, currency, note in mapping:
        amount = parse_amount(raw_value)
        if amount is None and not clean(raw_value):
            continue
        conn.execute(
            """
            INSERT INTO program_costs (program_id, fee_type, amount, currency, raw_value, normalized_note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (program["id"], fee_type, amount, normalize_currency(currency), clean(raw_value), note),
        )
        count += 1
    tuition_view = clean(entity.get("Tuition_View"))
    if tuition_view:
        conn.execute(
            """
            INSERT INTO program_costs (program_id, fee_type, amount, currency, raw_value, normalized_note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (program["id"], "tuition_view", parse_amount(tuition_view), None, tuition_view, "原始展示费用文本"),
        )
        count += 1
    return count


def insert_tags(conn: sqlite3.Connection, program: dict[str, Any], record: dict[str, Any], entity: dict[str, Any]) -> int:
    tags: list[tuple[str, str, int, str]] = []
    for tag_type, value in [
        ("source_category", program.get("source_category")),
        ("source_project_type", program.get("source_project_type")),
        ("standard_category", program.get("standard_category")),
        ("standard_subcategory", program.get("standard_subcategory")),
        ("country", program.get("country")),
        ("city_region", program.get("city_region")),
        ("delivery_mode", program.get("delivery_mode")),
        ("residential_type", program.get("residential_type")),
        ("credit_type", program.get("credit_type")),
    ]:
        if value:
            tags.append((tag_type, str(value), 95, "normalized_field"))
    for item in entity.get("SubjectKeywords") or []:
        value = nested_name(item) or item.get("Text") if isinstance(item, dict) else None
        if value:
            tags.append(("subject", value, 85, "source_subject_keywords"))
    description_text = program.get("description_text") or ""
    title_text = f"{record.get('title', '')} {description_text[:1000]}"
    for tag_type, pattern, value in [
        ("goal", r"美本|背景提升|申请|pre-college", "美本背景提升"),
        ("goal", r"语言|ESL|英语", "语言提升"),
        ("goal", r"领导力|辩论|演讲", "领导力/表达"),
        ("subject", r"数学|AMC|统计", "数学统计"),
        ("subject", r"AI|人工智能|科技|工程|IT", "工程科技/AI"),
        ("subject", r"艺术|设计|戏剧", "艺术设计"),
        ("student_fit", r"低龄|小学|四年级|五年级|六年级|七年级|八年级", "低龄探索"),
        ("service_feature", r"辅导员|接送", "辅导员/接送"),
        ("service_feature", r"保录|保证录取", "保录取/合作申请"),
    ]:
        if re.search(pattern, title_text, re.I):
            tags.append((tag_type, value, 70, "keyword_rule"))
    deduped = sorted(set(tags))
    for tag_type, value, confidence, source in deduped:
        conn.execute(
            """
            INSERT INTO program_tags (program_id, tag_type, tag_value, confidence, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (program["id"], tag_type, value, confidence, source),
        )
    return len(deduped)


def insert_quality_issues(conn: sqlite3.Connection, program: dict[str, Any]) -> int:
    count = 0
    for issue_type, severity, field_name, message in program.get("_issues", []):
        conn.execute(
            """
            INSERT INTO data_quality_issues (program_id, issue_type, severity, field_name, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (program["id"], issue_type, severity, field_name, message),
        )
        count += 1
    return count


def quality_issue_types(entity: dict[str, Any], record: dict[str, Any], description_html: str | None) -> list[tuple[str, str, str, str]]:
    issues: list[tuple[str, str, str, str]] = []
    if not nested_name(entity.get("Country")) and not record.get("location"):
        issues.append(("missing_location", "medium", "country/city", "缺少国家或城市信息，需要顾问复核。"))
    if not nested_name(entity.get("MinGrade")) and not record.get("grade"):
        issues.append(("missing_grade", "medium", "min_grade/max_grade", "缺少年级范围，需要顾问复核。"))
    if not entity.get("Tuition") and not entity.get("ServiceFee") and not entity.get("Tuition_View"):
        issues.append(("missing_cost", "high", "cost", "缺少学费或服务费信息，不适合直接对外展示价格。"))
    if not collect_date_ranges(entity):
        issues.append(("missing_session", "medium", "ProjectDateRanges/DateRangesStr", "缺少可结构化时间批次。"))
    if not description_html:
        issues.append(("missing_description", "low", "Content", "缺少项目详情介绍。"))
    return issues


def collect_date_ranges(entity: dict[str, Any]) -> list[str]:
    ranges: list[str] = []
    for item in entity.get("ProjectDateRanges") or []:
        if not isinstance(item, dict):
            continue
        raw = clean(item.get("DateRange") or item.get("Name") or item.get("DateRangesStr"))
        start = clean(item.get("StartDate") or item.get("StartTime"))
        end = clean(item.get("EndDate") or item.get("EndTime"))
        if raw:
            ranges.append(raw)
        elif start or end:
            ranges.append(f"{start or ''}-{end or ''}")
    raw_text = clean(entity.get("DateRangesStr") or entity.get("DateMark"))
    if raw_text:
        ranges.extend([part.strip() for part in re.split(r"[；;]", raw_text) if part.strip()])
    start = clean(entity.get("StartTime"))
    end = clean(entity.get("EndTime"))
    if start or end:
        ranges.append(f"{start or ''}-{end or ''}")
    return sorted(set(ranges))


def parse_date_range(raw: str) -> tuple[str | None, str | None]:
    raw = raw.strip()
    dates = re.findall(r"(20\d{2}[-/年.]\d{1,2}[-/月.]\d{1,2}|\d{1,2}[/月.-]\d{1,2})", raw)
    if not dates:
        return None, None
    if len(dates) == 1:
        return normalize_date_token(dates[0]), None
    return normalize_date_token(dates[0]), normalize_date_token(dates[1])


def normalize_date_token(value: str) -> str | None:
    value = value.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
    parts = [part for part in value.split("-") if part]
    if len(parts) == 3:
        y, m, d = parts
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    if len(parts) == 2:
        m, d = parts
        return f"{int(m):02d}-{int(d):02d}"
    return None


def duration_days(start_date: str | None, end_date: str | None) -> int | None:
    if not start_date or not end_date or len(start_date) != 10 or len(end_date) != 10:
        return None
    from datetime import date

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return None
    return max(0, (end - start).days + 1)


def standardize_category(source_category: str | None, source_type: str | None, title: str | None) -> tuple[str, str]:
    text = f"{source_category or ''} {source_type or ''} {title or ''}"
    rules = [
        (r"有学分", ("大学夏校", "有学分大学夏校")),
        (r"无学分|pre-college|大学营", ("大学夏校", "无学分大学夏校")),
        (r"在线", ("线上项目", "线上夏校")),
        (r"低龄|中学营|Middle School", ("低龄夏校", "低龄/中学营")),
        (r"艺术|设计|戏剧", ("主题营", "艺术设计营")),
        (r"数学", ("主题营", "数学营")),
        (r"科技|AI|IT", ("主题营", "科技/AI营")),
        (r"语言|ESL|英语", ("主题营", "语言提升营")),
        (r"辩论|演讲|领导力", ("主题营", "辩论/演讲/领导力营")),
        (r"户外|体育|Outdoor", ("主题营", "户外体育营")),
        (r"探校", ("探校项目", "探校")),
        (r"插班", ("插班项目", "插班")),
        (r"科研", ("科研型夏校", "科研项目")),
        (r"亲子", ("低龄夏校", "亲子营")),
        (r"天才|精英", ("高选择性项目", source_type or "精英/天才营")),
    ]
    for pattern, result in rules:
        if re.search(pattern, text, re.I):
            return result
    if source_category == PRIMARY_SUMMER_CATEGORY:
        return "夏校项目", source_type or "其他夏校"
    return "相邻项目", source_type or source_category or "待归类"


def infer_library_scope(source_category: str | None, source_type: str | None) -> str:
    if source_category == PRIMARY_SUMMER_CATEGORY:
        return "primary_summer"
    if source_category == "插班" or source_type == "插班":
        return "extension_join_class"
    if source_category == "探校" or source_type == "探校":
        return "extension_campus_visit"
    if source_type in ADJACENT_TYPES:
        return "adjacent_enrichment"
    return "summer_related"


def infer_delivery_mode(source_type: str | None, title: str | None, description: str | None) -> str:
    text = f"{source_type or ''} {title or ''} {description or ''}"
    if re.search(r"在线|线上|online|remote", text, re.I):
        return "online"
    if re.search(r"混合|hybrid", text, re.I):
        return "hybrid"
    return "offline"


def infer_residential(value: Any, source_type: str | None, title: str | None, description: str | None) -> str:
    if value is True or str(value).lower() == "true":
        return "residential"
    if value is False or str(value).lower() == "false":
        return "day_or_unknown"
    text = f"{source_type or ''} {title or ''} {description or ''}"
    if re.search(r"住宿|residential|boarding", text, re.I):
        return "residential"
    if re.search(r"走读|day camp", text, re.I):
        return "day"
    if re.search(r"在线|线上|online", text, re.I):
        return "online"
    return "unknown"


def infer_credit(value: Any, source_type: str | None, title: str | None, description: str | None) -> str:
    if value is True or str(value).lower() == "true":
        return "credit"
    if value is False or str(value).lower() == "false":
        return "non_credit_or_unknown"
    text = f"{source_type or ''} {title or ''} {description or ''}"
    if re.search(r"有学分|credit", text, re.I):
        return "credit"
    if re.search(r"无学分|non-credit|non credit", text, re.I):
        return "non_credit"
    return "unknown"


def recommendation_score(record: dict[str, Any], entity: dict[str, Any], issues: list[Any], delivery_mode: str, credit_type: str) -> int:
    score = 60
    if record.get("category") == PRIMARY_SUMMER_CATEGORY:
        score += 15
    if entity.get("ApplicationDeadline"):
        score += 5
    if collect_date_ranges(entity):
        score += 5
    if nested_name(entity.get("Country")):
        score += 5
    if delivery_mode in {"offline", "online"}:
        score += 3
    if credit_type == "credit":
        score += 3
    score -= min(20, len(issues) * 5)
    return max(0, min(100, score))


def build_advisor_notes(record: dict[str, Any], entity: dict[str, Any], application_fee_html: str | None) -> str:
    notes = []
    if entity.get("ApplicationDeadline"):
        notes.append(f"截止/录取节奏：{entity.get('ApplicationDeadline')}")
    if entity.get("ApplicationRequirement"):
        req = html_to_text(entity.get("ApplicationRequirement"))
        if req:
            notes.append(f"申请要求：{req[:180]}")
    if application_fee_html:
        fee_text = html_to_text(application_fee_html)
        if fee_text:
            notes.append(f"费用说明：{fee_text[:220]}")
    return "\n".join(notes)


def summarize(record: dict[str, Any], entity: dict[str, Any], description_html: str | None) -> str | None:
    for value in [record.get("summary"), entity.get("Tag"), entity.get("Inctroduction"), description_html]:
        text = html_to_text(value)
        if text:
            return text[:180]
    return None


def html_to_text(value: Any) -> str | None:
    text = first_text(value)
    if not text:
        return None
    parser = TextExtractor()
    try:
        parser.feed(text)
        output = parser.text()
    except Exception:
        output = re.sub(r"<[^>]+>", " ", text)
    output = re.sub(r"\s+", " ", output).strip()
    return output or None


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def nested_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return clean(value.get("Name") or value.get("Text") or value.get("Title"))
    return clean(value)


def nested_en_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return clean(value.get("EnName") or value.get("EnTitle"))
    return None


def split_location(value: Any) -> tuple[str | None, str | None]:
    text = clean(value)
    if not text:
        return None, None
    parts = [part.strip() for part in text.split("/") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return parts[0], None


def grade_name_and_order(value: Any, raw_grade: Any, *, first: bool) -> tuple[str | None, int | None]:
    if isinstance(value, dict):
        return clean(value.get("Name") or value.get("Text")), parse_int(value.get("Order"))
    text = clean(raw_grade)
    if not text:
        return None, None
    parts = [part.strip() for part in re.split(r"-|至|~", text) if part.strip()]
    selected = parts[0] if first else parts[-1]
    return selected, grade_order_from_text(selected)


def grade_order_from_text(text: str | None) -> int | None:
    if not text:
        return None
    if "幼" in text or "Kindergarten" in text:
        return 0
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1)) * 10
    cn = {"一": 10, "二": 20, "三": 30, "四": 40, "五": 50, "六": 60, "七": 70, "八": 80, "九": 90, "十": 100, "十一": 110, "十二": 120}
    for key, value in sorted(cn.items(), key=lambda item: len(item[0]), reverse=True):
        if key in text:
            return value
    if "成人" in text:
        return 200
    return None


def parse_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def parse_amount(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)", text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def normalize_currency(value: Any) -> str | None:
    text = clean(value)
    if not text:
        return None
    if text.upper() in {"USD", "美元"}:
        return "USD"
    if text.upper() in {"CNY", "RMB", "人民币"}:
        return "CNY"
    return text


def infer_asset_type(url: str) -> str:
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}:
        return "image"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".mp4", ".mov", ".webm"}:
        return "video"
    return "file"


def insert_data_dictionary(conn: sqlite3.Connection) -> None:
    entries = [
        ("source_projects", "source_project_id", "TEXT", "NO", "源项目 ID，来自 DianEdu 项目 Entity.ID。", "projects.data_json.id / fields.ID"),
        ("source_projects", "raw_json", "TEXT", "NO", "完整源项目 JSON 快照，用于追溯和重跑清洗。", "projects.data_json"),
        ("summer_programs", "id", "TEXT", "NO", "河狸陪夏校库内部项目 ID。", "hp-summer-{source_project_id}"),
        ("summer_programs", "library_scope", "TEXT", "NO", "项目在夏校库中的范围：primary_summer、extension_join_class、extension_campus_visit、adjacent_enrichment、summer_related。", "source category/type rules"),
        ("summer_programs", "standard_category", "TEXT", "NO", "河狸陪标准大类，如大学夏校、低龄夏校、主题营、探校项目。", "source_category/source_project_type/title mapping"),
        ("summer_programs", "standard_subcategory", "TEXT", "NO", "河狸陪标准小类，如有学分大学夏校、数学营、艺术设计营。", "source_project_type mapping"),
        ("summer_programs", "country", "TEXT", "YES", "国家中文名。", "fields.Country.Name"),
        ("summer_programs", "city_region", "TEXT", "YES", "城市或区域中文名。", "fields.City.Name"),
        ("summer_programs", "min_grade_name", "TEXT", "YES", "最低适用年级。", "fields.MinGrade.Name"),
        ("summer_programs", "max_grade_name", "TEXT", "YES", "最高适用年级。", "fields.MaxGrade.Name"),
        ("summer_programs", "residential_type", "TEXT", "NO", "住宿类型：residential、day、online、day_or_unknown、unknown。", "fields.Residential + keyword inference"),
        ("summer_programs", "credit_type", "TEXT", "NO", "学分类型：credit、non_credit、non_credit_or_unknown、unknown。", "fields.HasCredit + keyword inference"),
        ("summer_programs", "delivery_mode", "TEXT", "NO", "授课方式：offline、online、hybrid。", "source_project_type/title/content inference"),
        ("summer_programs", "recommendation_score", "INTEGER", "NO", "顾问排序用推荐分，不直接等同于项目质量。", "rule-based score"),
        ("program_sessions", "date_range_raw", "TEXT", "NO", "原始时间批次文本。", "fields.ProjectDateRanges / fields.DateRangesStr / StartTime-EndTime"),
        ("program_costs", "fee_type", "TEXT", "NO", "费用类型：tuition、service_fee、hot_sale_fee、early_bird_service_fee、late_bird_service_fee、current_price、tuition_view。", "fields fee columns"),
        ("program_tags", "tag_type", "TEXT", "NO", "标签类型，如 subject、goal、country、service_feature。", "normalized fields + keyword rules"),
        ("data_quality_issues", "issue_type", "TEXT", "NO", "数据质量问题类型，如 missing_cost、missing_session。", "quality rules"),
    ]
    conn.executemany(
        """
        INSERT INTO data_dictionary (table_name, column_name, data_type, nullable, description, source_mapping)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        entries,
    )


def create_views(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE VIEW advisor_program_search AS
        SELECT
          p.id,
          p.title,
          p.library_scope,
          p.standard_category,
          p.standard_subcategory,
          p.country,
          p.city_region,
          p.min_grade_name,
          p.max_grade_name,
          p.residential_type,
          p.credit_type,
          p.delivery_mode,
          p.application_deadline_raw,
          p.recommendation_score,
          p.data_quality_status,
          COUNT(DISTINCT s.id) AS session_count,
          COUNT(DISTINCT q.id) AS quality_issue_count
        FROM summer_programs p
        LEFT JOIN program_sessions s ON s.program_id = p.id
        LEFT JOIN data_quality_issues q ON q.program_id = p.id
        GROUP BY p.id;

        CREATE VIEW primary_summer_programs AS
        SELECT * FROM advisor_program_search
        WHERE library_scope = 'primary_summer';
        """
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dianedu_archiver.helipei_summer")
    parser.add_argument("--source-db", default=str(DEFAULT_SOURCE_DB))
    parser.add_argument("--output-db", default=str(DEFAULT_OUTPUT_DB))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    stats = build_helipei_summer_db(Path(args.source_db), Path(args.output_db))
    print(json.dumps(asdict(stats), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
