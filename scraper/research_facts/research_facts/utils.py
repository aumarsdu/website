"""Pure helpers: text normalization, stable hashing, JSON path reads, redaction.

Everything in this module is deterministic and side-effect free except the file
digest helper, so it is safe to use from tests and from the redaction path.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Plan section 4.2: keys that must never be persisted verbatim.
SENSITIVE_KEY_PATTERNS = (
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "secret",
    "password",
    "session",
    "credential",
    "apikey",
    "api_key",
    "access_key",
    "private_key",
)

REDACTED = "[REDACTED]"

_WS_RE = re.compile(r"[\s\u00a0\u200b\u200c\u200d\ufeff]+")
_TAG_RE = re.compile(r"<[^>]+>")
_PUNCT_RE = re.compile(r"[\s\-_·•,，、。.；;：:！!？?（）()\[\]【】<>《》\"'“”‘’/\\|~`@#$%^&*+=]+")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------


def clean_text(value: Any) -> str:
    """Return a tidy single-spaced string, or ``""`` when there is no text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    return text.strip()


def strip_html(value: Any) -> str:
    """Flatten the small HTML subset found in partner course descriptions.

    Line breaks are preserved: a bullet list must stay a bullet list, because
    item-level comparison and promotional filtering both depend on it.
    """
    text = str(value or "")
    if "<" in text and ">" in text:
        text = _TAG_RE.sub("\n", text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return clean_multiline(text)


def clean_multiline(value: Any) -> str:
    """Normalize a multi-line block: NFC, line breaks preserved, no trailing space."""
    text = str(value or "")
    text = unicodedata.normalize("NFC", text)
    lines = [clean_text(line) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def comparison_key(value: str) -> str:
    """Aggressive key used only to decide whether two strings say the same thing.

    Whitespace, punctuation, and case are removed. Digits and CJK characters are
    never touched, so ``4周`` and ``8周`` stay different.
    """
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return _PUNCT_RE.sub("", text)


def truncate(value: str, limit: int = 120) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


# --------------------------------------------------------------------------
# Hashing / identity
# --------------------------------------------------------------------------


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_hash(value: Any, length: int = 16) -> str:
    """Short deterministic hash of any JSON-able value.

    Used for record keys and report digests, so the same input always yields
    the same string across runs and machines.
    """
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# Minimal JSON path
# --------------------------------------------------------------------------


def _normalize_key(key: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(key)).casefold()


def _deep_find(payload: Any, key: str) -> Any:
    """First value whose key matches, in document order (breadth-agnostic)."""
    target = _normalize_key(key)
    if isinstance(payload, dict):
        for existing_key, value in payload.items():
            if _normalize_key(existing_key) == target:
                return value
        for value in payload.values():
            found = _deep_find(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _deep_find(item, key)
            if found is not None:
                return found
    return None


def json_path_get(payload: Any, path: str) -> Any:
    """Read a small JSONPath subset used by the web source profiles.

    Supported forms:

    * ``$.a.b.c``        -- dotted lookup, key matching ignores spaces/underscores
    * ``$.a.b[0].c``     -- explicit array index
    * ``$..name``        -- recursive lookup, first match in document order

    Returns ``None`` when the path does not resolve. It never raises, so a
    layout change in a partner payload becomes a *missing field* rather than a
    crash or an invented value.
    """
    if not path or not path.startswith("$"):
        return None
    if path.startswith("$.."):
        return _deep_find(payload, path[3:])

    current: Any = payload
    for token in re.findall(r"\[(\d+)\]|\.?([^.\[\]]+)", path[1:]):
        index, name = token
        if index:
            position = int(index)
            if not isinstance(current, list) or position >= len(current):
                return None
            current = current[position]
            continue
        if not name:
            continue
        if isinstance(current, dict):
            match = None
            for key, value in current.items():
                if _normalize_key(key) == _normalize_key(name):
                    match = value
                    break
            if match is None:
                return None
            current = match
        elif isinstance(current, list):
            found = None
            for item in current:
                if isinstance(item, dict):
                    for key, value in item.items():
                        if _normalize_key(key) == _normalize_key(name):
                            found = value
                            break
                if found is not None:
                    break
            if found is None:
                return None
            current = found
        else:
            return None
    return current


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------


def is_sensitive_key(key: str) -> bool:
    lowered = str(key).lower()
    return any(pattern in lowered for pattern in SENSITIVE_KEY_PATTERNS)


def redact(value: Any) -> Any:
    """Replace secret-like values before anything is written to disk."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result[key] = REDACTED if is_sensitive_key(key) else redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def find_sensitive_keys(value: Any) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if is_sensitive_key(key):
                    found.append(str(key))
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return sorted(set(found))


# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------


def dedupe(values: Iterable[str]) -> list[str]:
    """Order-preserving de-duplication; the order stays stable across runs."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
