from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlparse
import hashlib
import re

ASSET_URL_RE = re.compile(
    r"""https?://[^\s"'<>]+\.(?:jpg|jpeg|png|gif|webp|svg|ico|pdf|docx?|xlsx?|pptx?|zip|rar|7z|mp4|webm|mov|mp3|wav)(?:\?[^\s"'<>]*)?""",
    re.I,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_filename_from_url(url: str, default_suffix: str = ".html") -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/") or "index"
    if parsed.query:
        path = f"{path}_{hashlib.sha1(parsed.query.encode()).hexdigest()[:10]}"
    quoted = quote(path, safe="._-")
    suffix = Path(parsed.path).suffix
    if not suffix and default_suffix:
        quoted += default_suffix
    return quoted.replace("%2F", "__")


def find_asset_urls(text: str) -> list[str]:
    return sorted(set(ASSET_URL_RE.findall(text or "")))
