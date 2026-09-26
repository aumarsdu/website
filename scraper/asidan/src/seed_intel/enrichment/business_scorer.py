from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
import re

from seed_intel.extraction.schema import ProjectRecord


@dataclass
class ProjectScore:
    project_uid: str
    marketing_priority_score: float
    admissions_value_score: float
    urgency_score: float
    differentiation_score: float
    content_potential_score: float
    sales_difficulty_score: float
    risk_score: float
    score_reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _urgency_score(deadline: str | None, today: date | None = None) -> float:
    if not deadline:
        return 30.0
    today = today or date.today()
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", deadline)
    if not match:
        return 40.0
    deadline_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    days = (deadline_date - today).days
    if days < 0:
        return 10.0
    if days <= 14:
        return 100.0
    if days <= 30:
        return 80.0
    if days <= 60:
        return 60.0
    return 45.0


def score_project(record: ProjectRecord, today: date | None = None) -> ProjectScore:
    admissions = 35.0
    if record.certificate:
        admissions += 15
    if record.organizer:
        admissions += 15
    if record.category in {"科研项目", "论文发表", "国际竞赛", "世界名校夏校"}:
        admissions += 20
    admissions = min(admissions, 100.0)

    urgency = _urgency_score(record.application_deadline, today)
    differentiation = 55.0 + (15 if record.category not in {None, "其他"} else 0) + (10 if record.location else 0)
    content = 25.0
    content += 20 if record.target_grade else 0
    content += 15 if record.application_deadline else 0
    content += 15 if record.certificate else 0
    content += 10 if record.pdf_links else 0
    content = min(content, 100.0)

    sales_difficulty = 35.0
    sales_difficulty += 15 if not record.price else 0
    sales_difficulty += 15 if not record.application_requirement else 0
    sales_difficulty += 10 if record.needs_human_review else 0
    sales_difficulty = min(sales_difficulty, 100.0)

    risk = 20.0
    risk += 20 if record.needs_human_review else 0
    risk += 15 if not record.price else 0
    risk += 15 if not record.application_deadline else 0
    risk += 10 if not record.organizer else 0
    risk = min(risk, 100.0)

    marketing = (
        admissions * 0.25
        + urgency * 0.20
        + differentiation * 0.20
        + content * 0.20
        + (100 - sales_difficulty) * 0.10
        + (100 - risk) * 0.05
    )
    return ProjectScore(
        project_uid=record.project_uid or "",
        marketing_priority_score=round(marketing, 2),
        admissions_value_score=round(admissions, 2),
        urgency_score=round(urgency, 2),
        differentiation_score=round(differentiation, 2),
        content_potential_score=round(content, 2),
        sales_difficulty_score=round(sales_difficulty, 2),
        risk_score=round(risk, 2),
        score_reason="规则评分：基于截止时间、证书/主办方、资料完整度和人工复核风险。",
    )
