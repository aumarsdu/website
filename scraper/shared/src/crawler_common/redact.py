from __future__ import annotations

import re
from typing import Mapping

# Header names whose values must never be persisted.
SENSITIVE_HEADER_RE = re.compile(
    r"authorization|cookie|set-cookie|token|secret|password|api[-_]?key|session",
    re.IGNORECASE,
)

# Common credential shapes inside JSON bodies / payloads worth masking on disk.
SENSITIVE_KEY_RE = SENSITIVE_HEADER_RE

REDACTED = "[REDACTED]"


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of headers safe to write to logs or disk artifacts."""
    return {
        name: (REDACTED if SENSITIVE_HEADER_RE.search(name) else value)
        for name, value in headers.items()
    }


def redact_mapping(mapping: Mapping[str, object]) -> dict[str, object]:
    """Redact sensitive keys of a flat mapping (e.g. parsed JSON payloads)."""
    out: dict[str, object] = {}
    for key, value in mapping.items():
        if isinstance(value, Mapping):
            out[str(key)] = redact_mapping(value)
        elif SENSITIVE_KEY_RE.search(str(key)):
            out[str(key)] = REDACTED
        else:
            out[str(key)] = value
    return out
