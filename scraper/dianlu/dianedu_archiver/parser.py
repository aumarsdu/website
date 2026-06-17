from __future__ import annotations

from typing import Any
from urllib.parse import urljoin
import json
import re

from bs4 import BeautifulSoup

from .config import DEFAULT_BASE_URL, canonicalize_url
from .schema import ArticleRecord, PageRecord, ProjectRecord
from .utils import find_asset_urls, sha256_text, utc_now

PROJECT_HINT_RE = re.compile(r"(项目|科研|夏校|竞赛|program|project|course)", re.I)
ARTICLE_HINT_RE = re.compile(r"(news|article|资讯|知识|blog|case|案例)", re.I)
DATE_RE = re.compile(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2})")


def parse_page(html: str, source_url: str, content_type: str | None = None, status_code: int | None = None) -> PageRecord:
    soup = BeautifulSoup(html, "lxml")
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else None)
    canonical = _canonical_from_soup(soup, source_url)
    links = extract_links(soup, source_url)
    assets = extract_assets(soup, html, source_url)
    forms = extract_forms(soup, source_url)
    json_ld = extract_json_ld(soup)
    return PageRecord(
        source_url=source_url,
        canonical_url=canonical,
        crawled_at=utc_now(),
        title=title,
        content_type=content_type,
        status_code=status_code,
        text_hash=sha256_text(soup.get_text("\n", strip=True)),
        links=links,
        assets=assets,
        forms=forms,
        json_ld=json_ld,
    )


def parse_project_detail(html: str, source_url: str) -> ProjectRecord | None:
    soup = BeautifulSoup(html, "lxml")
    title = pick_title(soup)
    text = soup.get_text("\n", strip=True)
    if not title or not (PROJECT_HINT_RE.search(source_url) or PROJECT_HINT_RE.search(text[:1000])):
        return None
    fields = extract_key_value_fields(soup)
    return ProjectRecord(
        source_url=source_url,
        canonical_url=_canonical_from_soup(soup, source_url),
        crawled_at=utc_now(),
        title=title,
        category=first_present(fields, ["分类", "类别", "项目类别", "项目类型", "type", "category"]),
        location=first_present(fields, ["地点", "城市", "Location", "City"]),
        grade=first_present(fields, ["年级", "Grade", "适合年级"]),
        project_type=first_present(fields, ["项目类型", "Project Type", "Type of program"]),
        summary=extract_summary(soup),
        fields=fields,
        assets=extract_assets(soup, html, source_url),
    )


def parse_article(html: str, source_url: str) -> ArticleRecord | None:
    soup = BeautifulSoup(html, "lxml")
    title = pick_title(soup)
    text = soup.get_text("\n", strip=True)
    if not title or not (ARTICLE_HINT_RE.search(source_url) or ARTICLE_HINT_RE.search(text[:1200])):
        return None
    main = soup.find("article") or soup.find("main") or soup.body or soup
    body_lines = [clean_text(line) for line in main.get_text("\n", strip=True).splitlines()]
    body = "\n\n".join(line for line in body_lines if line)
    date_match = DATE_RE.search(text)
    return ArticleRecord(
        source_url=source_url,
        canonical_url=_canonical_from_soup(soup, source_url),
        crawled_at=utc_now(),
        title=title,
        category=infer_category_from_url(source_url),
        published_at=date_match.group(1) if date_match else None,
        summary=extract_summary(soup),
        body_markdown=f"# {title}\n\n{body}" if body else None,
        assets=extract_assets(soup, html, source_url),
    )


def extract_search_facets(html: str, source_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    soup = BeautifulSoup(html, "lxml")
    filters: list[dict[str, Any]] = []
    hot_terms: list[dict[str, Any]] = []
    for form in soup.find_all("form"):
        form_name = form.get("name") or form.get("id") or "form"
        for control in form.find_all(["input", "select", "option", "button"]):
            label = control.get("name") or control.get("id") or form_name
            text = clean_text(control.get_text(" ", strip=True) or control.get("placeholder") or control.get("value"))
            if text:
                filters.append(
                    {
                        "source_url": source_url,
                        "filter_name": str(label),
                        "option_text": text,
                        "option_value": control.get("value"),
                    }
                )
    for select in soup.find_all("select"):
        name = select.get("name") or select.get("id") or "select"
        for option in select.find_all("option"):
            text = clean_text(option.get_text(" ", strip=True))
            if text:
                filters.append(
                    {
                        "source_url": source_url,
                        "filter_name": str(name),
                        "option_text": text,
                        "option_value": option.get("value"),
                    }
                )
    hot_sections = soup.find_all(string=re.compile(r"(HOT|Hot|hot|热门|热搜)"))
    for marker in hot_sections:
        parent = marker.parent
        if not parent:
            continue
        container = parent.find_parent(["section", "div", "ul"]) or parent
        for item in container.find_all(["a", "span", "li", "button"]):
            term = clean_text(item.get_text(" ", strip=True))
            if term and not re.search(r"hot|热门|热搜", term, re.I):
                hot_terms.append({"term": term, "source_url": source_url, "weight": None, "crawled_at": utc_now()})
    return dedupe_dicts(filters, ("filter_name", "option_text")), dedupe_dicts(hot_terms, ("term",))


def extract_links(soup: BeautifulSoup, source_url: str) -> list[str]:
    links: set[str] = set()
    for tag in soup.find_all(["a", "link", "script"]):
        raw = tag.get("href") or tag.get("src")
        if not raw or raw.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        links.add(canonicalize_url(urljoin(source_url, raw)))
    return sorted(links)


def extract_assets(soup: BeautifulSoup, html: str, source_url: str) -> list[str]:
    assets: set[str] = set()
    for tag in soup.find_all(["img", "source", "video", "audio", "a", "link", "script"]):
        for attr in ("src", "href", "poster", "data-src"):
            raw = tag.get(attr)
            if raw:
                absolute = canonicalize_url(urljoin(source_url, raw))
                if "." in absolute.rsplit("/", 1)[-1]:
                    assets.add(absolute)
    for raw in find_asset_urls(html):
        assets.add(canonicalize_url(urljoin(source_url, raw)))
    return sorted(assets)


def extract_forms(soup: BeautifulSoup, source_url: str) -> list[dict[str, Any]]:
    forms: list[dict[str, Any]] = []
    for form in soup.find_all("form"):
        fields = []
        for field in form.find_all(["input", "select", "textarea", "button"]):
            field_type = field.get("type") or field.name
            fields.append(
                {
                    "name": field.get("name"),
                    "id": field.get("id"),
                    "type": field_type,
                    "placeholder": field.get("placeholder"),
                    "value_present": field.has_attr("value"),
                }
            )
        forms.append(
            {
                "source_url": source_url,
                "method": (form.get("method") or "GET").upper(),
                "action": canonicalize_url(urljoin(source_url, form.get("action") or source_url)),
                "fields": fields,
            }
        )
    return forms


def extract_json_ld(soup: BeautifulSoup) -> list[Any]:
    items: list[Any] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text()
        if not text:
            continue
        try:
            items.append(json.loads(text))
        except json.JSONDecodeError:
            items.append({"parse_error": True, "raw_sample": text[:500]})
    return items


def extract_key_value_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in soup.find_all(["li", "p", "div", "tr"]):
        text = clean_text(row.get_text(" ", strip=True))
        if not text:
            continue
        for sep in ("：", ":", " | "):
            if sep in text:
                key, value = text.split(sep, 1)
                key = clean_text(key)
                value = clean_text(value)
                if key and value and len(key) <= 24 and len(value) <= 300:
                    fields.setdefault(key, value)
                break
    return fields


def pick_title(soup: BeautifulSoup) -> str | None:
    for selector in ("h1", ".title", "[class*=title]", "h2", "title"):
        tag = soup.select_one(selector)
        if tag:
            title = clean_text(tag.get_text(" ", strip=True))
            if title:
                return title
    return None


def extract_summary(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        return clean_text(meta["content"])
    for p in soup.find_all("p"):
        text = clean_text(p.get_text(" ", strip=True))
        if text and len(text) > 30:
            return text[:500]
    return None


def infer_category_from_url(url: str) -> str | None:
    lowered = url.lower()
    if "case" in lowered or "案例" in lowered:
        return "case"
    if "news" in lowered or "article" in lowered or "资讯" in lowered:
        return "article"
    if "knowledge" in lowered or "知识" in lowered:
        return "knowledge"
    return None


def first_present(fields: dict[str, str], keys: list[str]) -> str | None:
    normalized = {k.lower(): v for k, v in fields.items()}
    for key in keys:
        if key in fields:
            return fields[key]
        if key.lower() in normalized:
            return normalized[key.lower()]
    return None


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def _canonical_from_soup(soup: BeautifulSoup, source_url: str) -> str:
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        return canonicalize_url(urljoin(source_url, canonical["href"]))
    return canonicalize_url(source_url, DEFAULT_BASE_URL)


def dedupe_dicts(records: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        marker = tuple(record.get(key) for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(record)
    return out
