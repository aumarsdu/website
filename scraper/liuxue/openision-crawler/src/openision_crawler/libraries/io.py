from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SENSITIVE_KEY_PARTS = (
    "authorization",
    "fcauthorization",
    "cookie",
    "token",
    "secret",
    "signature",
    "ossaccesskeyid",
    "security-token",
    "password",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                return True
            if contains_sensitive_key(child):
                return True
    if isinstance(value, list):
        return any(contains_sensitive_key(item) for item in value)
    return False
