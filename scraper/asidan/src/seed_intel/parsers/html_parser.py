from __future__ import annotations

import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from seed_intel.common.url_utils import is_asset_url, join_and_normalize, normalize_url
from seed_intel.extraction.schema import ParsedPage


def _text_or_none(value: object) -> str | None:
    text = value.get_text(" ", strip=True) if hasattr(value, "get_text") else None
    return text or None


def _simple_markdown(soup: BeautifulSoup) -> str:
    lines: list[str] = []
    for node in soup.find_all(["h1", "h2", "h3", "p", "li", "th", "td"]):
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.name == "h1":
            lines.append(f"# {text}")
        elif node.name == "h2":
            lines.append(f"## {text}")
        elif node.name == "h3":
            lines.append(f"### {text}")
        elif node.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _select_content_root(soup: BeautifulSoup):
    selectors = [
        "article",
        ".entry-content",
        ".portfolio-content",
        ".postclass",
        "#content",
        "main",
        ".contentclass",
    ]
    candidates = []
    for selector in selectors:
        candidates.extend(soup.select(selector))
    if candidates:
        return max(candidates, key=lambda node: len(node.get_text("\n", strip=True)))
    return soup.body or soup


def parse_html(html: str, source_url: str, asset_extensions: list[str]) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")
    json_ld: list[dict] = []
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            parsed = json.loads(node.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            json_ld.append(parsed)

    for selector in ["script", "style", "noscript"]:
        for node in soup.select(selector):
            node.decompose()

    title = _text_or_none(soup.find("title"))
    h1 = _text_or_none(soup.find("h1"))
    meta = soup.find("meta", attrs={"name": "description"})
    canonical = soup.find("link", attrs={"rel": "canonical"})
    language = soup.html.get("lang") if soup.html else None
    canonical_url = None
    if canonical and canonical.get("href"):
        canonical_url = normalize_url(urljoin(source_url, str(canonical["href"])))

    links: set[str] = set()
    images: set[str] = set()
    assets: set[str] = set()
    pdfs: set[str] = set()
    for tag in soup.find_all(["a", "img", "source"]):
        href = tag.get("href") or tag.get("src")
        if not href or str(href).startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = join_and_normalize(source_url, str(href))
        if tag.name in {"img", "source"}:
            images.add(absolute)
        elif is_asset_url(absolute, asset_extensions):
            assets.add(absolute)
            if absolute.lower().split("?", 1)[0].endswith(".pdf"):
                pdfs.add(absolute)
        else:
            links.add(absolute)

    content_root = _select_content_root(soup)
    body_text = content_root.get_text("\n", strip=True)
    clean_html = str(content_root)
    markdown = _simple_markdown(content_root)
    return ParsedPage(
        source_url=source_url,
        title=title,
        h1=h1,
        meta_description=str(meta.get("content")) if meta and meta.get("content") else None,
        canonical_url=canonical_url,
        language=language,
        body_text=body_text,
        clean_html=clean_html,
        markdown=markdown,
        links=sorted(links),
        image_urls=sorted(images),
        asset_urls=sorted(assets),
        pdf_urls=sorted(pdfs),
        structured_data_json_ld=json_ld,
    )
