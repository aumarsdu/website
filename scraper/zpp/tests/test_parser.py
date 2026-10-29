from pathlib import Path

from xntj_archive.parser import extract_links, parse_page, render_markdown


def test_episode_parser_extracts_structured_content() -> None:
    html = (Path(__file__).parent / "fixtures" / "episode.html").read_text()
    result = parse_page(html, "https://xntj.tv/ep/live-ep0001/")
    assert result.episode == 1
    assert result.title == "测试标题"
    assert result.published_at == "2026-01-02T00:00:00Z"
    assert result.summary == "页面摘要"
    assert "完整逐字稿第一段" in (result.transcript or "")
    assert "## 完整逐字稿" in render_markdown(result, "https://xntj.tv/ep/live-ep0001/")


def test_link_extraction_classifies_pages_and_assets() -> None:
    html = (Path(__file__).parent / "fixtures" / "episode.html").read_text()
    pages, assets = extract_links(html, "https://xntj.tv/ep/live-ep0001/")
    assert "https://xntj.tv/ep/live-ep0002/" in pages
    assert "https://xntj.tv/site.css" in assets
    assert "https://xntj.tv/cover.webp" in assets
    assert "https://example.com/outside.pdf" in assets
