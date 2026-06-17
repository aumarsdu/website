from pathlib import Path

from dianedu_archiver.parser import extract_search_facets, parse_article, parse_page, parse_project_detail


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_page_extracts_links_assets_forms() -> None:
    html = (FIXTURES / "search.html").read_text(encoding="utf-8")
    page = parse_page(html, "https://www.dianedu.com/Search")
    assert page.title == "DianEdu Search"
    assert "https://www.dianedu.com/projects/biology-research" in page.links
    assert "https://www.dianedu.com/assets/logo.png" in page.assets
    assert page.forms[0]["method"] == "GET"


def test_extract_search_facets_and_hot_terms() -> None:
    html = (FIXTURES / "search.html").read_text(encoding="utf-8")
    filters, hot_terms = extract_search_facets(html, "https://www.dianedu.com/Search")
    assert any(item["filter_name"] == "city" and item["option_text"] == "Shanghai" for item in filters)
    assert {item["term"] for item in hot_terms} >= {"Biology", "Summer School"}


def test_parse_project_detail() -> None:
    html = (FIXTURES / "project.html").read_text(encoding="utf-8")
    project = parse_project_detail(html, "https://www.dianedu.com/projects/biology-research")
    assert project is not None
    assert project.title == "Biology Research Project"
    assert project.project_type == "科研项目"
    assert project.location == "上海"
    assert "https://www.dianedu.com/files/project.pdf" in project.assets


def test_parse_article_can_extract_article_like_page() -> None:
    html = """<html><head><title>知识中心：科研规划</title></head><body><article><h1>科研规划</h1><p>2026-06-01</p><p>知识中心内容，帮助学生理解科研项目申请路径和准备方式。</p></article></body></html>"""
    article = parse_article(html, "https://www.dianedu.com/news/research-plan")
    assert article is not None
    assert article.title == "科研规划"
    assert article.category == "article"
