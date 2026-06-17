"""Bounded URL queue and deterministic URL deduplication."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

from .config import canonicalize_url


@dataclass
class UrlScheduler:
    max_pages: int
    allow_url: Callable[[str], bool]
    skipped_out_of_scope: int = 0
    skipped_over_limit: int = 0
    duplicates: int = 0
    _seen: set[str] = field(default_factory=set)
    _queue: deque[str] = field(default_factory=deque)

    def add_many(self, urls: Iterable[str]) -> None:
        for url in urls:
            self.add(url)

    def add(self, url: str) -> None:
        normalized = canonicalize_url(url)
        if normalized in self._seen:
            self.duplicates += 1
            return
        self._seen.add(normalized)
        if not self.allow_url(normalized):
            self.skipped_out_of_scope += 1
            return
        if len(self._queue) >= self.max_pages:
            self.skipped_over_limit += 1
            return
        self._queue.append(normalized)

    def __iter__(self) -> Iterator[str]:
        while self._queue:
            yield self._queue.popleft()
