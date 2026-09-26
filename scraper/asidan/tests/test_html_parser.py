from pathlib import Path

from seed_intel.parsers.html_parser import parse_html


def test_html_text_extraction():
    html = Path("tests/fixtures/sample_project.html").read_text(encoding="utf-8")
    page = parse_html(html, "https://www.seedasdan.com/research/", [".pdf", ".jpg"])
    assert page.title == "ASDAN 科研项目"
    assert page.h1 == "ASDAN 科研项目"
    assert "报名截止" in page.body_text
    assert "导航" not in page.body_text
    assert page.canonical_url == "https://www.seedasdan.com/research/"
    assert page.pdf_urls == ["https://www.seedasdan.com/files/brochure.pdf"]
    assert page.structured_data_json_ld[0]["@type"] == "Course"
