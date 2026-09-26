from __future__ import annotations

from typing import Any


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    candidates: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in ("records", "rows", "list", "items", "courseList", "data"):
                value = node.get(key)
                if isinstance(value, list):
                    candidates.extend(value)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            candidates.extend(node)

    walk(payload)
    return [item for item in candidates if isinstance(item, dict)]
