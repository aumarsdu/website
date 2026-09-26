from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_HEADER_RE = re.compile(
    r"(authorization|cookie|token|secret|password|session|x-csrf|csrf|set-cookie)",
    re.I,
)
ASSET_URL_RE = re.compile(
    r"https?://[^\s\"<>]+?\.(?:pdf|jpg|jpeg|png|webp|gif|svg|doc|docx|xls|xlsx|ppt|pptx)(?:\?[^\s\"<>]*)?",
    re.I,
)
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.I,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        redacted[key] = "[REDACTED]" if SENSITIVE_HEADER_RE.search(key) else value
    return redacted


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, item: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def iter_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    rows: list[Any] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)), doseq=True)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


def content_hash(value: Any) -> str:
    return hashlib.sha256(stable_json_dumps(value).encode("utf-8")).hexdigest()


def safe_filename(value: str, suffix: str = "") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    if not name:
        name = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    if suffix and not name.lower().endswith(suffix.lower()):
        name += suffix
    return name[:180]


def deep_find_asset_urls(value: Any) -> list[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for inner in node.values():
                walk(inner)
        elif isinstance(node, list):
            for inner in node:
                walk(inner)
        elif isinstance(node, str):
            found.update(match.rstrip("),.;]") for match in ASSET_URL_RE.findall(node))

    walk(value)
    return sorted(found)


def flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, inner in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(inner, (dict, list)):
                nested = flatten_json(inner, child)
                if nested:
                    out.update(nested)
                else:
                    out[child] = None
            else:
                out[child] = inner
    elif isinstance(value, list):
        out[prefix or "items"] = json.dumps(value, ensure_ascii=False)
    return out
