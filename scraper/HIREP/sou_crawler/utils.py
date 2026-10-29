from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import hashlib
import re


ASSET_RE = re.compile(r"https?://[^\s\"'<>]+?\.(?:pdf|jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?", re.I)
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)), doseq=True)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def safe_filename(value: Any, *, fallback: str = "item", max_len: int = 120) -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text[:max_len].strip() or fallback)


def flatten_json(data: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten_json(value, new_prefix))
    elif isinstance(data, list):
        out[prefix] = jsonish(data)
    else:
        out[prefix] = data
    return out


def jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def walk_values(data: Any) -> list[Any]:
    values: list[Any] = []
    if isinstance(data, dict):
        for value in data.values():
            values.extend(walk_values(value))
    elif isinstance(data, list):
        for value in data:
            values.extend(walk_values(value))
    else:
        values.append(data)
    return values


def find_asset_urls(data: Any) -> list[str]:
    urls: list[str] = []
    for value in walk_values(data):
        if isinstance(value, str):
            urls.extend(match.group(0).rstrip(").,;") for match in ASSET_RE.finditer(value))
    return sorted(set(urls))


def find_first(data: Any, keys: list[str]) -> Any | None:
    lowered = {key.lower() for key in keys}
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in lowered and value not in (None, ""):
                return value
        for value in data.values():
            found = find_first(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_first(item, keys)
            if found not in (None, ""):
                return found
    return None


def extract_records(data: Any) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    if isinstance(data, dict):
        for key in ("records", "rows", "list", "items", "courseList", "projectList", "data"):
            value = data.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if isinstance(value, dict):
                nested = extract_records(value)
                if nested:
                    return nested
        if not candidates and any(k in data for k in ("title", "name", "id", "courseId", "projectId")):
            candidates = [data]
    elif isinstance(data, list):
        candidates = data
    return [item for item in candidates if isinstance(item, dict)]


def file_extension_from_url(url: str, fallback: str = ".bin") -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix in {".pdf", ".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return fallback
