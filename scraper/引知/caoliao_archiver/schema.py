"""Small runtime validators for records persisted by the archiver."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .errors import SchemaValidationError


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ApiEnvelope:
    code: int
    message: str
    data: Any

    @classmethod
    def parse(cls, payload: Any) -> "ApiEnvelope":
        if not isinstance(payload, dict):
            raise SchemaValidationError("OpenAPI response must be an object.")
        code = payload.get("code")
        if not isinstance(code, int):
            raise SchemaValidationError("OpenAPI response code must be an integer.")
        if code != 0:
            message = str(payload.get("message", ""))
            raise SchemaValidationError(f"OpenAPI returned non-zero code={code}: {message}")
        return cls(
            code=code,
            message=str(payload.get("message", "")),
            data=payload.get("data"),
        )


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{label} must be an object.")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{label} must be a list.")
    return value
