from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from seed_intel.crawler.robots import RobotsCache


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    content: bytes
    headers: dict[str, str]
    error: str | None = None


def classify_http_error(status_code: int) -> str:
    if status_code == 401:
        return "http_401_unauthorized"
    if status_code == 403:
        return "http_403_forbidden"
    if status_code == 404:
        return "http_404_not_found"
    if status_code == 429:
        return "http_429_rate_limited"
    if status_code >= 500:
        return "http_5xx_server_error"
    return "unknown_error"


class Fetcher:
    def __init__(
        self,
        user_agent: str,
        timeout: float,
        retries: int,
        rate_limit: float,
        obey_robots: bool = True,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries
        self.rate_limit = rate_limit
        self.transport = transport
        self.robots = RobotsCache(user_agent, timeout, transport) if obey_robots else None
        self._client: httpx.Client | None = None
        self._last_request = 0.0

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                transport=self.transport,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def fetch(self, url: str) -> FetchResult:
        if self.robots is not None and not self.robots.allowed(url):
            return FetchResult(
                url=url,
                final_url=url,
                status_code=0,
                content_type="",
                content=b"",
                headers={},
                error="robots_disallow",
            )
        delay = self.rate_limit - (time.monotonic() - self._last_request)
        if delay > 0:
            time.sleep(delay)
        self._last_request = time.monotonic()
        attempts = self.retries + 1
        last_error = "unknown_error"
        client = self._get_client()
        for attempt in range(attempts):
            try:
                response = client.get(url)
            except httpx.TimeoutException:
                last_error = "timeout"
                continue
            except httpx.HTTPError as exc:
                last_error = f"network_error:{type(exc).__name__}"
                continue
            content_type = response.headers.get("content-type", "")
            if response.status_code < 400:
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    content=response.content,
                    headers=dict(response.headers),
                )
            error = classify_http_error(response.status_code)
            if response.status_code in {401, 403, 404}:
                return FetchResult(url, str(response.url), response.status_code, content_type, b"", dict(response.headers), error)
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 5))
        return FetchResult(url=url, final_url=url, status_code=0, content_type="", content=b"", headers={}, error=last_error)
