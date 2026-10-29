from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

EPISODE_RE = re.compile(r"(?:^|/)live-ep(?P<number>\d{4})(?:/|$)", re.IGNORECASE)


@dataclass
class PageRecord:
    title: str | None
    canonical_url: str | None
    description: str | None
    published_at: str | None
    episode: int | None
    summary: str | None
    transcript: str | None
    headings: list[str]
    text: str
    json_ld: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            decoded = json.loads(node.get_text())
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            values.append(decoded)
        elif isinstance(decoded, list):
            values.extend(item for item in decoded if isinstance(item, dict))
    return values


def _blog_posting(items: list[dict[str, Any]]) -> dict[str, Any]:
    for item in items:
        candidates = item.get("@graph", []) if isinstance(item.get("@graph"), list) else [item]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            kind = candidate.get("@type")
            if kind == "BlogPosting" or (isinstance(kind, list) and "BlogPosting" in kind):
                return candidate
    return {}


def parse_page(html: str, url: str) -> PageRecord:
    soup = BeautifulSoup(html, "html.parser")
    ld = _json_ld(soup)
    post = _blog_posting(ld)
    title = post.get("headline") or (soup.title.get_text(" ", strip=True) if soup.title else None)
    canonical = soup.find("link", rel="canonical")
    description = post.get("description")
    if not description:
        meta = soup.find("meta", attrs={"name": "description"})
        description = meta.get("content") if meta else None
    match = EPISODE_RE.search(url)
    episode = int(match.group("number")) if match else None
    content = soup.select_one(".content-body")
    transcript = content.get_text("\n", strip=True) if content else None
    summary_node = soup.select_one(".preview-body")
    summary = summary_node.get_text("\n", strip=True) if summary_node else description
    text_root = soup.select_one("main") or soup.body or soup
    return PageRecord(
        title=title,
        canonical_url=canonical.get("href") if canonical else url,
        description=description,
        published_at=post.get("datePublished"),
        episode=episode,
        summary=summary,
        transcript=transcript,
        headings=[node.get_text(" ", strip=True) for node in soup.select("h1, h2, h3")],
        text=text_root.get_text("\n", strip=True),
        json_ld=ld,
    )


def extract_links(html: str, page_url: str) -> tuple[set[str], set[str]]:
    """Return normal links and static resource links discovered in a document."""
    soup = BeautifulSoup(html, "html.parser")
    pages: set[str] = set()
    assets: set[str] = set()
    asset_extensions = (".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico", ".pdf", ".zip", ".mp3", ".mp4", ".webm", ".json", ".md", ".txt", ".woff", ".woff2")
    for tag, attr in (("a", "href"), ("img", "src"), ("script", "src"), ("link", "href"), ("source", "src"), ("video", "src"), ("audio", "src")):
        for node in soup.find_all(tag):
            value = node.get(attr)
            if not value:
                continue
            absolute = urljoin(page_url, value).split("#", 1)[0]
            if absolute.lower().split("?", 1)[0].endswith(asset_extensions) or tag != "a":
                assets.add(absolute)
            else:
                pages.add(absolute)
    for image in soup.select("img[srcset], source[srcset]"):
        for candidate in image["srcset"].split(","):
            assets.add(urljoin(page_url, candidate.strip().split(" ", 1)[0]).split("#", 1)[0])
    return pages, assets


def extract_css_urls(css: str, asset_url: str) -> set[str]:
    return {
        urljoin(asset_url, value.strip(" '\""))
        for value in re.findall(r"url\(([^)]+)\)", css, flags=re.IGNORECASE)
        if not value.strip().startswith("data:")
    }


def render_markdown(record: PageRecord, source_url: str) -> str:
    lines = [f"# {record.title or source_url}", "", f"来源：{source_url}"]
    if record.published_at:
        lines.append(f"发布时间：{record.published_at}")
    if record.episode is not None:
        lines.append(f"EP：EP{record.episode:04d}")
    if record.summary:
        lines.extend(["", "## 摘要", "", record.summary])
    if record.transcript:
        lines.extend(["", "## 完整逐字稿", "", record.transcript])
    elif record.text:
        lines.extend(["", "## 正文", "", record.text])
    return "\n".join(lines) + "\n"
