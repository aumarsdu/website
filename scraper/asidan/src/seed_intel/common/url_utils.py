from __future__ import annotations

import posixpath
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}


def extract_domain(url: str) -> str:
    return urlsplit(url).netloc.lower()


def remove_tracking_params(url: str) -> str:
    parsed = urlsplit(url)
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(sorted(kept)), ""))


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    scheme = "https"
    domain = parsed.netloc.lower()
    path = parsed.path or "/"
    path = posixpath.normpath(path)
    if parsed.path.endswith("/") and not path.endswith("/"):
        path += "/"
    if not path.startswith("/"):
        path = "/" + path
    query = urlencode(sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ))
    return urlunsplit((scheme, domain, path, query, ""))


def join_and_normalize(base_url: str, href: str) -> str:
    return normalize_url(urljoin(base_url, href))


def is_allowed_domain(url: str, allowed_domains: list[str]) -> bool:
    domain = extract_domain(url)
    allowed = {item.lower() for item in allowed_domains}
    return domain in allowed


def should_block_url(url: str, blocked_patterns: list[str]) -> bool:
    lowered = url.lower()
    return any(pattern.lower() in lowered for pattern in blocked_patterns)


def is_asset_url(url: str, extensions: list[str]) -> bool:
    suffix = PurePosixPath(urlsplit(url).path.lower()).suffix
    return suffix in {item.lower() for item in extensions}
