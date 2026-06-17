from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

SENSITIVE_KEY_PATTERNS = (
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "secret",
    "password",
    "session",
    "credential",
    "x-api-key",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(pattern in lowered for pattern in SENSITIVE_KEY_PATTERNS)


def is_auth_header_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in {"authorization", "proxy-authorization", "x-api-key"} or "token" in lowered


def redact_value(value: Any) -> str:
    return f"<redacted:{type(value).__name__}>"


def redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: redact_value(item) if is_sensitive_key(str(key)) else redact_obj(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    return value


def contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(is_sensitive_key(str(key)) or contains_sensitive_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_sensitive_key(item) for item in value)
    return False


def contains_redacted_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_redacted_value(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_redacted_value(item) for item in value)
    return isinstance(value, str) and value.startswith("<redacted:")


def redact_headers(headers: dict[str, str] | None) -> tuple[dict[str, str], bool]:
    if not headers:
        return {}, False
    redacted: dict[str, str] = {}
    had_sensitive = False
    for key, value in headers.items():
        if is_sensitive_key(key):
            redacted[key] = redact_value(value)
            had_sensitive = True
        else:
            redacted[key] = value
    return redacted, had_sensitive


def headers_have_auth_indicator(headers: dict[str, str] | None) -> bool:
    return any(is_auth_header_key(key) for key in (headers or {}).keys())


def parse_post_data(post_data: str | None) -> Any:
    if not post_data:
        return None
    try:
        return redact_obj(json.loads(post_data))
    except json.JSONDecodeError:
        pairs = parse_qsl(post_data, keep_blank_values=True)
        if pairs:
            return redact_obj(dict(pairs))
        return "<non-json-payload>"


def normalize_url_for_key(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def query_params(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlparse(url).query, keep_blank_values=True))


def with_query_params(url: str, params: dict[str, Any]) -> str:
    parsed = urlparse(url)
    merged = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value is not None:
            merged[key] = str(value)
    return urlunparse(parsed._replace(query=urlencode(merged, doseq=True)))


def is_allowed_url(url: str, allowed_domains: set[str]) -> bool:
    host = urlparse(url).hostname
    return bool(host and any(host == domain or host.endswith("." + domain) for domain in allowed_domains))


def is_public_asset_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    path = urlparse(url).path.lower()
    return (
        "aliyuncs.com" in host
        or "oss-" in host
        or path.endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp"))
    )


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def slugify(value: str, fallback: str = "item", max_len: int = 80) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", str(value)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.rstrip(".")
    if not cleaned:
        cleaned = fallback
    return cleaned[:max_len].strip() or fallback


def file_extension_from_url_or_type(url: str, content_type: str | None = None) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix
    if suffix and len(suffix) <= 8:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    return ".bin"


def compact_json_summary(value: Any, depth: int = 0, max_keys: int = 12) -> Any:
    if depth >= 4:
        return type(value).__name__
    if isinstance(value, dict):
        summary: dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= max_keys:
                summary["..."] = f"{len(value) - max_keys} more keys"
                break
            summary[key] = compact_json_summary(item, depth + 1, max_keys)
        return summary
    if isinstance(value, list):
        if not value:
            return []
        return {
            "type": "array",
            "length": len(value),
            "first": compact_json_summary(value[0], depth + 1, max_keys),
        }
    return type(value).__name__
