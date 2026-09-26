from __future__ import annotations

from dataclasses import dataclass, field

from .utils import canonicalize_url


@dataclass
class UrlDeduper:
    seen: set[str] = field(default_factory=set)

    def add(self, url: str) -> bool:
        canonical = canonicalize_url(url)
        if canonical in self.seen:
            return False
        self.seen.add(canonical)
        return True
