from __future__ import annotations

from typing import Any
import logging

from .config import Settings
from .discovery import save_raw_html
from .fetcher import Fetcher
from .scheduler import UrlScheduler
from .storage import append_jsonl, replace_simple_table, upsert_records, write_json

LOGGER = logging.getLogger(__name__)


async def crawl_routes(settings: Settings) -> None:
    if settings.dry_run:
        print({"command": "crawl-routes", "seeds": settings.allowed_entry_urls(), "max_pages": settings.max_pages})
        return
    scheduler = UrlScheduler(settings, settings.allowed_entry_urls())
    fetcher = Fetcher(settings)
    pages: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        while len(pages) < settings.max_pages:
            url = scheduler.pop()
            if not url:
                break
            result = await fetcher.get(url)
            if result.error:
                errors.append(result.error.model_dump())
                append_jsonl(settings.raw_dir / "errors.jsonl", result.error.model_dump())
                continue
            if not result.text or "html" not in (result.content_type or "").lower():
                continue
            from .parser import parse_page

            page = parse_page(result.text, result.final_url, result.content_type, result.status_code).model_dump()
            page["html_path"] = save_raw_html(settings, page["canonical_url"], result.text)
            pages.append(page)
            append_jsonl(settings.raw_dir / "pages_raw.jsonl", {**page, "raw_html_path": page["html_path"]})
            for link in page.get("links", []):
                if len(scheduler.seen) < settings.max_pages * 5:
                    scheduler.add(link)
    finally:
        await fetcher.close()
    upsert_records(settings.db_path, "pages", pages, "canonical_url")
    write_json(settings.reports_dir / "crawl_routes_summary.json", {"pages": len(pages), "errors": len(errors), "seen_urls": len(scheduler.seen)})


async def crawl_search(settings: Settings) -> None:
    if settings.dry_run:
        print({"command": "crawl-search", "url": settings.search_url})
        return
    fetcher = Fetcher(settings)
    try:
        result = await fetcher.get(settings.search_url)
    finally:
        await fetcher.close()
    if result.error:
        append_jsonl(settings.raw_dir / "errors.jsonl", result.error.model_dump())
        write_json(settings.reports_dir / "crawl_search_summary.json", {"error": result.error.model_dump()})
        return
    html = result.text or ""
    from .parser import extract_search_facets, parse_page

    page = parse_page(html, result.final_url, result.content_type, result.status_code).model_dump()
    page["html_path"] = save_raw_html(settings, page["canonical_url"], html)
    filters, hot_terms = extract_search_facets(html, result.final_url)
    replace_simple_table(settings.db_path, "filters", filters)
    replace_simple_table(settings.db_path, "hot_search_terms", hot_terms)
    from .api_crawler import crawl_filter_dictionaries

    api_filters, api_hot_terms = await crawl_filter_dictionaries(settings)
    filters.extend(api_filters)
    hot_terms.extend(api_hot_terms)
    replace_simple_table(settings.db_path, "filters", filters)
    replace_simple_table(settings.db_path, "hot_search_terms", hot_terms)
    write_json(settings.processed_dir / "filters.json", filters)
    write_json(settings.processed_dir / "hot_search_terms.json", hot_terms)
    append_jsonl(settings.raw_dir / "pages_raw.jsonl", page)
    write_json(settings.reports_dir / "crawl_search_summary.json", {"filters": len(filters), "hot_terms": len(hot_terms)})


async def crawl_lists(settings: Settings) -> None:
    if settings.dry_run:
        print({"command": "crawl-lists", "source": "discovered routes and search page", "max_pages": settings.max_pages})
        return
    from .api_crawler import crawl_project_lists_api

    api_items = await crawl_project_lists_api(settings)
    if not (settings.raw_dir / "pages_raw.jsonl").exists():
        await crawl_routes(settings)
    pages = list_from_raw_pages(settings)
    list_pages = [page for page in pages if looks_like_list_page(page)]
    write_json(settings.processed_dir / "list_pages.json", list_pages)
    write_json(settings.reports_dir / "crawl_lists_summary.json", {"list_pages": len(list_pages), "api_project_items": len(api_items)})


async def crawl_details(settings: Settings) -> None:
    if settings.dry_run:
        print({"command": "crawl-details", "source": "raw archived html", "max_pages": settings.max_pages})
        return
    from .api_crawler import crawl_project_details_api

    projects: list[dict[str, Any]] = await crawl_project_details_api(settings)
    if not projects:
        for page in list_from_raw_pages(settings):
            html_path = page.get("html_path") or page.get("raw_html_path")
            if not html_path:
                continue
            full_path = settings.root_dir / html_path
            if not full_path.exists():
                continue
            from .parser import parse_project_detail

            project = parse_project_detail(full_path.read_text(encoding="utf-8", errors="ignore"), page["canonical_url"])
            if project:
                projects.append(project.model_dump())
    upsert_records(settings.db_path, "projects", projects, "canonical_url")
    write_json(settings.processed_dir / "projects.json", projects)
    write_json(settings.reports_dir / "crawl_details_summary.json", {"projects": len(projects)})


async def crawl_articles(settings: Settings) -> None:
    if settings.dry_run:
        print({"command": "crawl-articles", "source": "raw archived html", "max_pages": settings.max_pages})
        return
    from .api_crawler import crawl_articles_api

    articles: list[dict[str, Any]] = await crawl_articles_api(settings)
    for page in list_from_raw_pages(settings):
        html_path = page.get("html_path") or page.get("raw_html_path")
        if not html_path:
            continue
        full_path = settings.root_dir / html_path
        if not full_path.exists():
            continue
        from .parser import parse_article

        article = parse_article(full_path.read_text(encoding="utf-8", errors="ignore"), page["canonical_url"])
        if article:
            articles.append(article.model_dump())
    upsert_records(settings.db_path, "articles", articles, "canonical_url")
    write_json(settings.processed_dir / "articles.json", articles)
    write_json(settings.reports_dir / "crawl_articles_summary.json", {"articles": len(articles)})


def list_from_raw_pages(settings: Settings) -> list[dict[str, Any]]:
    seen: set[str] = set()
    pages: list[dict[str, Any]] = []
    path = settings.raw_dir / "pages_raw.jsonl"
    if not path.exists():
        return pages
    for record in path.read_text(encoding="utf-8").splitlines():
        if not record.strip():
            continue
        import json

        page = json.loads(record)
        url = page.get("canonical_url")
        if not url or url in seen:
            continue
        seen.add(url)
        pages.append(page)
    return pages


def looks_like_list_page(page: dict[str, Any]) -> bool:
    url = (page.get("canonical_url") or "").lower()
    title = (page.get("title") or "").lower()
    return any(token in url or token in title for token in ["search", "list", "project", "program", "course", "项目", "课程", "科研", "夏校", "竞赛"])
