"""Extract resource URLs and form template IDs from API/H5 content."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from html import unescape
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

URL_RE = re.compile(r"https?://[^\s\"'<>）)]+")
CSS_URL_RE = re.compile(r"url\(([^)]+)\)")
NAV_LINK_PREFIX = "navLink:"


class ResourceExtractor(HTMLParser):
    URL_ATTRS = {
        "src",
        "href",
        "poster",
        "data-src",
        "data-original",
        "data-href",
        "data-url",
        "download",
    }
    SRCSET_ATTRS = {"srcset", "data-srcset"}

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if not value:
                continue
            if name in self.URL_ATTRS:
                self.urls.update(_extract_urls_from_text(value, self.base_url))
            elif name in self.SRCSET_ATTRS:
                self.urls.update(_extract_urls_from_srcset(value, self.base_url))
            elif name == "style":
                self.urls.update(_extract_urls_from_text(value, self.base_url))


def extract_urls_from_html(html: str, base_url: str) -> set[str]:
    parser = ResourceExtractor(base_url)
    parser.feed(html)
    parser.urls.update(_extract_urls_from_text(html, base_url))
    return {url for url in parser.urls if _is_http_url(url)}


def extract_urls_from_json(value: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            urls.update(extract_urls_from_json(item))
    elif isinstance(value, list):
        for item in value:
            urls.update(extract_urls_from_json(item))
    elif isinstance(value, str):
        urls.update(_extract_urls_from_text(value))
    return {url for url in urls if _is_http_url(url)}


def extract_tpl_ids(operations: Iterable[dict[str, Any]]) -> list[int]:
    tpl_ids: list[int] = []
    for operation in operations:
        if operation.get("element_type") != 2:
            continue
        raw_value = operation.get("element_value")
        try:
            tpl_id = int(raw_value)
        except (TypeError, ValueError):
            continue
        if tpl_id not in tpl_ids:
            tpl_ids.append(tpl_id)
    return tpl_ids


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _extract_urls_from_text(value: str, base_url: str | None = None) -> set[str]:
    text = unescape(value)
    urls: set[str] = set()
    for raw_value in _candidate_url_values(text):
        candidate = raw_value.strip().strip("'\"")
        if candidate.startswith(NAV_LINK_PREFIX):
            candidate = candidate[len(NAV_LINK_PREFIX) :]
        if base_url:
            candidate = urljoin(base_url, candidate)
        urls.add(_strip_trailing_punctuation(candidate))
    for match in URL_RE.finditer(text):
        urls.add(_strip_trailing_punctuation(match.group(0)))
    return {url for url in urls if _is_http_url(url)}


def _candidate_url_values(text: str) -> set[str]:
    values = set()
    if text.startswith(NAV_LINK_PREFIX):
        values.add(text)
    if text.startswith(("http://", "https://", "/")):
        values.add(text)
    for match in CSS_URL_RE.finditer(text):
        values.add(match.group(1))
    return values


def _extract_urls_from_srcset(value: str, base_url: str) -> set[str]:
    urls = set()
    for item in value.split(","):
        candidate = item.strip().split(" ", 1)[0]
        if candidate:
            urls.update(_extract_urls_from_text(candidate, base_url))
    return urls


def _strip_trailing_punctuation(url: str) -> str:
    return url.rstrip(".,;!?)）]}")
