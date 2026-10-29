from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-csrf-token",
    "x-xsrf-token",
}

SENSITIVE_QUERY_KEYS = {
    "security-token",
    "signature",
    "ossaccesskeyid",
    "x-oss-security-token",
    "accesskeyid",
    "access_key_id",
    "token",
}

SENSITIVE_JSON_KEYS = {
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "authorization",
    "cookie",
    "set-cookie",
    "accesskeyid",
    "accesskeysecret",
    "securitytoken",
    "stsToken",
}


def redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in (headers or {}).items():
        safe[key] = "[REDACTED]" if key.lower() in SENSITIVE_HEADER_NAMES else value
    return safe


def sanitize_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SENSITIVE_QUERY_KEYS:
            query.append((key, "[REDACTED]"))
        else:
            query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def strip_sensitive_query(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in SENSITIVE_QUERY_KEYS
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


_URL_RE = re.compile(r"https?://[^\s\"'<>\\]+")
_SIGNED_PARAM_RE = re.compile(
    r"(?i)(security-token|ossaccesskeyid|signature|x-oss-security-token|accesskeyid|access_key_id|token)=([^&\"'<>\\]+)"
)
_SENSITIVE_JSON_FIELD_RE = re.compile(
    r'(?i)("(?:access_token|refresh_token|id_token|token|authorization|cookie|set-cookie)"\s*:\s*")([^"]+)(")'
)


def sanitize_text(text: str) -> str:
    text = _SIGNED_PARAM_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _SENSITIVE_JSON_FIELD_RE.sub(lambda match: f"{match.group(1)}[REDACTED]{match.group(3)}", text)
    return _URL_RE.sub(lambda match: sanitize_url(match.group(0)), text)


def sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            if key.lower() in {item.lower() for item in SENSITIVE_JSON_KEYS}:
                safe[key] = "[REDACTED]"
            else:
                safe[key] = sanitize_json(item)
        return safe
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return sanitize_url(value)
    return value


def dumps_safe(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(sanitize_json(value), ensure_ascii=False, indent=indent)
