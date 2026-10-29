from pathlib import Path

from seed_intel.extraction.rule_extractor import extract_project_from_page
from seed_intel.parsers.html_parser import parse_html


def test_project_rule_extraction():
    html = Path("tests/fixtures/sample_project.html").read_text(encoding="utf-8")
    page = parse_html(html, "https://www.seedasdan.com/research/", [".pdf", ".jpg"])
    record = extract_project_from_page(page)
    assert record.project_name == "ASDAN 科研项目"
    assert record.category == "科研项目"
    assert record.target_grade == "9-12年级"
    assert record.application_deadline == "2026年6月30日"
    assert record.price == "人民币 12800"
    assert record.evidence
