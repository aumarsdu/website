from __future__ import annotations

import json
from pathlib import Path

from seed_intel.crawler.storage import write_csv, write_jsonl
from seed_intel.crm.crm_card_generator import generate_crm_card
from seed_intel.content.xhs_topic_generator import generate_topics
from seed_intel.enrichment.business_scorer import ProjectScore, score_project
from seed_intel.extraction.schema import ProjectRecord


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0] if files else None


def load_latest_projects(root: Path) -> list[ProjectRecord]:
    project_dir = root / "data" / "gold" / "projects"
    path = latest_file(project_dir, "projects_*.jsonl") or (project_dir / "projects.jsonl")
    rows = read_jsonl(path) if path else []
    return [ProjectRecord.model_validate(row) for row in rows]


def export_projects(root: Path, records: list[ProjectRecord]) -> Path:
    rows = []
    for record in records:
        score = score_project(record)
        rows.append({
            "项目ID": record.project_uid,
            "项目名称": record.project_name,
            "项目类型": record.category,
            "适合年级": record.target_grade,
            "适合学生": record.suitable_for,
            "项目地点": record.location,
            "项目模式": record.delivery_mode,
            "开始时间": record.start_date,
            "结束时间": record.end_date,
            "报名截止": record.application_deadline,
            "主办方": record.organizer,
            "合作机构": record.partner_institution,
            "证书/成果": record.certificate or record.output_result,
            "价格": record.price,
            "升学价值": record.admissions_value,
            "项目亮点": record.highlights,
            "风险点": record.risks,
            "营销优先级": score.marketing_priority_score,
            "内容潜力": score.content_potential_score,
            "销售难度": score.sales_difficulty_score,
            "是否需要人工复核": record.needs_human_review,
            "来源链接": record.source_url,
            "证据摘要": " | ".join(item.evidence_text or "" for item in record.evidence[:3]),
            "最近更新时间": record.crawled_at.isoformat(),
        })
    path = root / "data" / "gold" / "projects" / "projects.csv"
    write_csv(path, rows, [
        "项目ID", "项目名称", "项目类型", "适合年级", "适合学生", "项目地点", "项目模式", "开始时间", "结束时间",
        "报名截止", "主办方", "合作机构", "证书/成果", "价格", "升学价值", "项目亮点", "风险点", "营销优先级",
        "内容潜力", "销售难度", "是否需要人工复核", "来源链接", "证据摘要", "最近更新时间",
    ])
    return path


def export_topics(root: Path, records: list[ProjectRecord]) -> Path:
    rows: list[dict[str, object]] = []
    for record in records:
        rows.extend(generate_topics(record, score_project(record)))
    path = root / "data" / "gold" / "xhs_topics" / "xhs_topics.jsonl"
    write_jsonl(path, rows)
    csv_path = root / "data" / "gold" / "xhs_topics" / "xhs_topics.csv"
    write_csv(csv_path, rows, [
        "project_uid", "project_name", "title", "title_style", "content_angle", "target_audience",
        "user_pain_point", "key_selling_point", "opening_hook", "outline", "cover_text", "cta",
        "wechat_conversion_script", "compliance_risk", "priority_score", "source_url",
    ])
    return csv_path


def export_crm_cards(root: Path, records: list[ProjectRecord]) -> Path:
    rows = [generate_crm_card(record) for record in records]
    path = root / "data" / "gold" / "crm_cards" / "crm_cards.jsonl"
    write_jsonl(path, rows)
    csv_path = root / "data" / "gold" / "crm_cards" / "crm_cards.csv"
    write_csv(csv_path, rows, [
        "project_uid", "project_name", "project_summary", "who_should_buy", "who_should_not_buy",
        "opening_script", "qualification_questions", "objection_handling", "recommended_next_steps",
        "risk_warnings", "required_followup_info", "source_url",
    ])
    return csv_path


def write_scores(root: Path, records: list[ProjectRecord]) -> Path:
    rows = [score_project(record).to_dict() for record in records]
    path = root / "data" / "gold" / "projects" / "project_scores.jsonl"
    write_jsonl(path, rows)
    return path


def write_coverage_report(root: Path, records: list[ProjectRecord]) -> Path:
    path = root / "data" / "gold" / "reports" / "coverage_report.md"
    domains = sorted({record.source_domain or "" for record in records if record.source_domain})
    content = [
        "# Coverage Report",
        "",
        f"- projects_extracted: {len(records)}",
        f"- source_domains: {', '.join(domains) if domains else 'none'}",
        f"- needs_human_review: {sum(1 for item in records if item.needs_human_review)}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(content) + "\n", encoding="utf-8")
    return path


def write_quality_report(root: Path, records: list[ProjectRecord]) -> Path:
    path = root / "data" / "gold" / "reports" / "quality_report.md"
    missing = {
        "project_name": sum(1 for item in records if not item.project_name),
        "category": sum(1 for item in records if not item.category),
        "target_grade": sum(1 for item in records if not item.target_grade),
        "deadline": sum(1 for item in records if not item.application_deadline),
        "price": sum(1 for item in records if not item.price),
    }
    lines = ["# Quality Report", "", "## Missing Fields"]
    lines.extend(f"- {key}: {value}" for key, value in missing.items())
    lines.append("")
    lines.append("## Review Queue")
    for record in records:
        if record.needs_human_review:
            lines.append(f"- {record.project_uid}: {record.project_name or 'unnamed'} ({record.source_url})")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def export_all(root: Path, records: list[ProjectRecord]) -> dict[str, str]:
    return {
        "projects_csv": str(export_projects(root, records)),
        "topics_csv": str(export_topics(root, records)),
        "crm_cards_csv": str(export_crm_cards(root, records)),
        "scores_jsonl": str(write_scores(root, records)),
        "coverage_report": str(write_coverage_report(root, records)),
        "quality_report": str(write_quality_report(root, records)),
    }
