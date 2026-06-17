from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .utils import now_iso, stable_hash


class SchemaValidationError(ValueError):
    pass


@dataclass
class ProjectRecord:
    source_url: str
    raw: dict[str, Any]
    crawled_at: str = field(default_factory=now_iso)
    canonical_url: str | None = None
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    category: str | None = None
    teacher: str | None = None
    university: str | None = None
    description: str | None = None
    asset_urls: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.source_url:
            raise SchemaValidationError("source_url is required")
        if not isinstance(self.raw, dict):
            raise SchemaValidationError("raw must be a dict")
        if not (self.title or self.id or self.uuid):
            raise SchemaValidationError("at least one of title/id/uuid is required")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        payload = {
            "record_hash": stable_hash(self.raw),
            "source_url": self.source_url,
            "crawled_at": self.crawled_at,
            "canonical_url": self.canonical_url,
            "id": self.id,
            "uuid": self.uuid,
            "title": self.title,
            "category": self.category,
            "teacher": self.teacher,
            "university": self.university,
            "description": self.description,
            "asset_urls": self.asset_urls,
            "raw": self.raw,
        }
        return payload
