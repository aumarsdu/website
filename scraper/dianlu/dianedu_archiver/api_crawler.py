from __future__ import annotations

from typing import Any
import json
import math

from .config import Settings
from .fetcher import Fetcher
from .storage import append_jsonl, replace_simple_table, upsert_records, write_json
from .utils import find_asset_urls, utc_now


PROJECT_SEARCH_URL = "https://www.dianedu.com/api/Project/Search"
ARTICLE_SEARCH_URL = "https://www.dianedu.com/api/Article/Search"


def default_project_payload(page: int, limit: int = 100) -> dict[str, Any]:
    return {
        "Page": page,
        "Limit": limit,
        "Residential": None,
        "ProjectTypeLv1Id": None,
        "ProjectTypeLv2Id": None,
        "Name": None,
        "CountryId": None,
        "CityId": None,
        "SelectedSubjectKeywordsIDs": [],
        "GradeId": None,
        "StartDate": None,
        "EndDate": None,
        "Longitude": None,
        "Latitude": None,
        "Range": None,
    }


async def crawl_project_lists_api(settings: Settings) -> list[dict[str, Any]]:
    fetcher = Fetcher(settings)
    records: list[dict[str, Any]] = []
    try:
        first = await fetcher.post_json(PROJECT_SEARCH_URL, default_project_payload(1))
        payload = parse_api_payload(first.text or "{}")
        append_jsonl(settings.raw_dir / "project_search_pages.jsonl", {"page": 1, "request": default_project_payload(1), "response": payload, "crawled_at": utc_now()})
        total = int(payload.get("Count") or 0)
        records.extend(payload.get("Data") or [])
        pages = min(math.ceil(total / 100), max(1, math.ceil(settings.max_pages / 100)))
        for page in range(2, pages + 1):
            request = default_project_payload(page)
            result = await fetcher.post_json(PROJECT_SEARCH_URL, request)
            if result.error:
                append_jsonl(settings.raw_dir / "errors.jsonl", result.error.model_dump())
                continue
            data = parse_api_payload(result.text or "{}")
            append_jsonl(settings.raw_dir / "project_search_pages.jsonl", {"page": page, "request": request, "response": data, "crawled_at": utc_now()})
            records.extend(data.get("Data") or [])
    finally:
        await fetcher.close()
    normalized = [normalize_project_list_item(item) for item in dedupe_by_id(records)]
    write_json(settings.processed_dir / "project_list_items.json", normalized)
    return normalized


async def crawl_project_details_api(settings: Settings, list_items: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if list_items is None:
        list_items = load_json_list(settings.processed_dir / "project_list_items.json")
    fetcher = Fetcher(settings)
    details: list[dict[str, Any]] = []
    try:
        for idx, item in enumerate(list_items[: settings.max_pages], 1):
            project_id = item.get("id") or item.get("ID")
            if not project_id:
                continue
            url = f"https://www.dianedu.com/api/Project/{project_id}"
            result = await fetcher.get(url)
            if result.error:
                append_jsonl(settings.raw_dir / "errors.jsonl", result.error.model_dump())
                continue
            data = parse_api_payload(result.text or "{}")
            record = normalize_project_detail(data, item, url)
            details.append(record)
            append_jsonl(settings.raw_dir / "project_details.jsonl", {"source_url": url, "data": data, "crawled_at": utc_now()})
            if idx % 100 == 0:
                write_json(settings.reports_dir / "crawl_details_progress.json", {"completed": idx, "total": len(list_items), "updated_at": utc_now()})
    finally:
        await fetcher.close()
    write_json(settings.processed_dir / "projects.json", details)
    upsert_records(settings.db_path, "projects", details, "canonical_url")
    return details


async def crawl_articles_api(settings: Settings) -> list[dict[str, Any]]:
    fetcher = Fetcher(settings)
    records: list[dict[str, Any]] = []
    try:
        first_payload = {"Page": 1, "Limit": 100}
        first = await fetcher.post_json(ARTICLE_SEARCH_URL, first_payload)
        data = parse_api_payload(first.text or "{}")
        append_jsonl(settings.raw_dir / "article_search_pages.jsonl", {"page": 1, "request": first_payload, "response": data, "crawled_at": utc_now()})
        total = int(data.get("Count") or 0)
        records.extend(data.get("Data") or [])
        pages = math.ceil(total / 100)
        for page in range(2, pages + 1):
            request = {"Page": page, "Limit": 100}
            result = await fetcher.post_json(ARTICLE_SEARCH_URL, request)
            if result.error:
                append_jsonl(settings.raw_dir / "errors.jsonl", result.error.model_dump())
                continue
            page_data = parse_api_payload(result.text or "{}")
            append_jsonl(settings.raw_dir / "article_search_pages.jsonl", {"page": page, "request": request, "response": page_data, "crawled_at": utc_now()})
            records.extend(page_data.get("Data") or [])
    finally:
        await fetcher.close()
    articles = [normalize_article_item(item) for item in dedupe_by_id(records)]
    write_json(settings.processed_dir / "articles.json", articles)
    upsert_records(settings.db_path, "articles", articles, "canonical_url")
    return articles


async def crawl_filter_dictionaries(settings: Settings) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    endpoints = {
        "project_type": "https://www.dianedu.com/api/Project/GetProjectTypes",
        "country_city": "https://www.dianedu.com/api/Project/GetCountryAndCities",
        "grade": "https://www.dianedu.com/api/Project/GetGrades",
        "hot_city": "https://www.dianedu.com/api/Project/GetHotAndCities",
        "subject_keyword": "https://www.dianedu.com/api/Project/GetSubjectKeywords?lang=zh",
        "article_category": "https://www.dianedu.com/api/Article/GetArticleCategorys",
        "special_topic": "https://www.dianedu.com/api/Article/GetSpecialTopics",
    }
    filters: list[dict[str, Any]] = []
    fetcher = Fetcher(settings)
    try:
        for name, url in endpoints.items():
            result = await fetcher.get(url)
            if result.error:
                append_jsonl(settings.raw_dir / "errors.jsonl", result.error.model_dump())
                continue
            data = parse_api_payload(result.text or "null")
            write_json(settings.raw_dir / f"{name}.json", data)
            filters.extend(flatten_filter_options(name, url, data))
        hot = await fetcher.get("https://www.dianedu.com/api/HomeBanner/HotKeywords")
        hot_data = parse_api_payload(hot.text or "[]") if not hot.error else []
    finally:
        await fetcher.close()
    hot_terms = [
        {
            "term": item.get("Word") or item.get("EnWord"),
            "source_url": "https://www.dianedu.com/api/HomeBanner/HotKeywords",
            "weight": item.get("Order"),
            "crawled_at": utc_now(),
            "raw": item,
        }
        for item in hot_data
        if isinstance(item, dict) and (item.get("Word") or item.get("EnWord"))
    ]
    replace_simple_table(settings.db_path, "filters", filters)
    replace_simple_table(settings.db_path, "hot_search_terms", hot_terms)
    write_json(settings.processed_dir / "filters.json", filters)
    write_json(settings.processed_dir / "hot_search_terms.json", hot_terms)
    return filters, hot_terms


def parse_api_payload(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_text": text}


def normalize_project_list_item(item: dict[str, Any]) -> dict[str, Any]:
    project_id = item.get("ID")
    return {
        "id": project_id,
        "canonical_url": f"https://www.dianedu.com/project/{project_id}",
        "source_url": PROJECT_SEARCH_URL,
        "title": item.get("Name") or "",
        "category": item.get("ProjectType1Name"),
        "project_type": item.get("ProjectType2Name") or item.get("ProjectType1Name"),
        "location": " / ".join(part for part in [item.get("Country"), item.get("City")] if part),
        "grade": " - ".join(part for part in [item.get("MinGrade"), item.get("MaxGrade")] if part),
        "summary": item.get("Tag") or None,
        "crawled_at": utc_now(),
        "raw": item,
        "assets": find_asset_urls(json.dumps(item, ensure_ascii=False)),
    }


def normalize_project_detail(data: dict[str, Any], list_item: dict[str, Any], source_url: str) -> dict[str, Any]:
    entity = data.get("Entity") if isinstance(data, dict) else {}
    entity = entity or {}
    project_id = entity.get("ID") or list_item.get("id") or list_item.get("ID")
    title = entity.get("Name") or list_item.get("title") or list_item.get("Name") or ""
    payload_text = json.dumps(data, ensure_ascii=False)
    return {
        "id": project_id,
        "canonical_url": f"https://www.dianedu.com/project/{project_id}",
        "source_url": source_url,
        "title": title,
        "category": nested_name(entity.get("ProjectTypeLv1")) or list_item.get("category"),
        "project_type": nested_name(entity.get("ProjectTypeLv2")) or list_item.get("project_type"),
        "location": " / ".join(part for part in [nested_name(entity.get("Country")), nested_name(entity.get("City"))] if part) or list_item.get("location"),
        "grade": " - ".join(part for part in [nested_name(entity.get("MinGrade")), nested_name(entity.get("MaxGrade"))] if part) or list_item.get("grade"),
        "summary": entity.get("Description") or entity.get("Tag") or list_item.get("summary"),
        "crawled_at": utc_now(),
        "fields": entity,
        "raw": data,
        "assets": find_asset_urls(payload_text),
    }


def normalize_article_item(item: dict[str, Any]) -> dict[str, Any]:
    article_id = item.get("ID")
    title = item.get("Title") or ""
    body = item.get("Content") or item.get("Abstract") or ""
    return {
        "id": article_id,
        "canonical_url": f"https://www.dianedu.com/article/{article_id}",
        "source_url": ARTICLE_SEARCH_URL,
        "title": title,
        "category": item.get("Title_view") or item.get("Title_view2"),
        "published_at": item.get("ArticleDate"),
        "author": item.get("Author"),
        "summary": item.get("Abstract"),
        "body_markdown": f"# {title}\n\n{body}" if body else None,
        "crawled_at": utc_now(),
        "raw": item,
        "assets": find_asset_urls(json.dumps(item, ensure_ascii=False)),
    }


def flatten_filter_options(name: str, source_url: str, data: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(value: Any, parent: str | None = None) -> None:
        if isinstance(value, dict):
            text = value.get("Text") or value.get("Name") or value.get("Title")
            option_value = value.get("Value") or value.get("ID") or value.get("Id")
            if text:
                out.append(
                    {
                        "source_url": source_url,
                        "filter_name": name if parent is None else f"{name}:{parent}",
                        "option_text": str(text),
                        "option_value": str(option_value) if option_value is not None else None,
                        "raw": value,
                    }
                )
                parent = str(text)
            for child_key in ("Children", "Country", "City", "Articles", "SpecialTopicArticles"):
                if child_key in value:
                    walk(value[child_key], parent)
        elif isinstance(value, list):
            for item in value:
                walk(item, parent)

    walk(data)
    return out


def dedupe_by_id(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        marker = str(record.get("ID") or record.get("id") or json.dumps(record, ensure_ascii=False, sort_keys=True))
        if marker in seen:
            continue
        seen.add(marker)
        out.append(record)
    return out


def nested_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("Name") or value.get("Text") or value.get("Title")
    if isinstance(value, str):
        return value
    return None


def load_json_list(path: Any) -> list[dict[str, Any]]:
    from .storage import read_json

    data = read_json(path, [])
    return data if isinstance(data, list) else []
