from datetime import date

from seed_intel.enrichment.business_scorer import score_project
from seed_intel.extraction.schema import ProjectRecord


def test_business_scoring():
    record = ProjectRecord(
        project_uid="p1",
        project_name="科研项目",
        category="科研项目",
        target_grade="G9-G12",
        application_deadline="2026年7月10日",
        organizer="ASDAN",
        certificate="证书",
        price="人民币 12800",
        source_url="https://www.seedasdan.com/a/",
        extraction_method="rule",
        extraction_confidence=0.9,
    )
    score = score_project(record, today=date(2026, 7, 1))
    assert score.urgency_score == 100
    assert score.marketing_priority_score > 60
