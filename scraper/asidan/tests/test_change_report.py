from __future__ import annotations

from pathlib import Path

from seed_intel.extraction.rule_extractor import extract_project_from_page
from seed_intel.extraction.schema import ProjectRecord
from seed_intel.parsers.html_parser import parse_html
from seed_intel.reports.export_report import write_change_report


def test_application_requirement_is_extracted():
    html = """
    <html><head><title>科研项目 A</title></head><body>
    <h1>科研项目 A</h1>
    <p>报名要求：需提交一页个人陈述与在校成绩单。</p>
    </body></html>
    """
    page = parse_html(html, "https://www.seedasdan.com/research/", [".pdf"])
    record = extract_project_from_page(page)
    assert record.application_requirement == "需提交一页个人陈述与在校成绩单"
    assert any(item.field_name == "application_requirement" for item in record.evidence)


def test_change_report_baseline_then_diff(tmp_path: Path):
    root = tmp_path

    def record(uid: str, name: str, price: str) -> ProjectRecord:
        return ProjectRecord(
            project_uid=uid,
            project_name=name,
            price=price,
            source_url=f"https://www.seedasdan.com/{uid}/",
            extraction_method="rule",
            extraction_confidence=0.9,
        )

    result = write_change_report(root, [record("a", "项目A", "100")])
    assert result["baseline"] is True
    assert result["added"] == 1

    result = write_change_report(root, [record("a", "项目A", "120"), record("b", "项目B", "80")])
    assert result["baseline"] is False
    assert result["added"] == 1
    assert result["changed"] == 1
    assert result["removed"] == 0

    report = (root / "data" / "gold" / "reports" / "change_report.md").read_text(encoding="utf-8")
    assert "- added: 1" in report
    assert "- changed: 1" in report
    assert "项目B" in report
