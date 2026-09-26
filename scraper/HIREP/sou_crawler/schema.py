from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CrawlStats:
    started_at: str
    target_domain: str = ""
    pages_requested: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    records_extracted: int = 0
    duplicate_records: int = 0
    errors: dict[str, int] = field(default_factory=dict)

    def add_error(self, category: str) -> None:
        self.errors[category] = self.errors.get(category, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "target_domain": self.target_domain,
            "pages_requested": self.pages_requested,
            "pages_succeeded": self.pages_succeeded,
            "pages_failed": self.pages_failed,
            "records_extracted": self.records_extracted,
            "duplicate_records": self.duplicate_records,
            "errors": dict(sorted(self.errors.items())),
        }
