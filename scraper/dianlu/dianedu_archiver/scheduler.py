from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from .config import Settings, canonicalize_url


class UrlScheduler:
    def __init__(self, settings: Settings, seeds: Iterable[str]) -> None:
        self.settings = settings
        self.queue: deque[str] = deque()
        self.seen: set[str] = set()
        for seed in seeds:
            self.add(seed)

    def add(self, url: str) -> bool:
        canonical = canonicalize_url(url, self.settings.base_url)
        if canonical in self.seen:
            return False
        if not self.settings.is_allowed_url(canonical):
            return False
        self.seen.add(canonical)
        self.queue.append(canonical)
        return True

    def pop(self) -> str | None:
        if not self.queue:
            return None
        return self.queue.popleft()

    def __len__(self) -> int:
        return len(self.queue)
