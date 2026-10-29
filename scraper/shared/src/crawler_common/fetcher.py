from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from crawler_common.errors import RETRYABLE_STATUS_CODES, classify_http_error
from crawler_common.robots import RobotsCache
from crawler_common.url_rules import hostname_of


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    content: bytes
    headers: dict[str, str]
    error: str | None = None
    attempts: int = field(default=1)


class Fetcher:
    """Sync, single-threaded fetcher with the workspace compliance defaults:

    - exact-hostname whitelist, re-checked after every redirect;
    - honest User-Agent (required);
    - per-origin minimum request interval (rate limiting);
    - retries only transient failures (timeout, network errors, 429/5xx),
      never 401/403/404;
    - optional robots.txt gating (on by default).
    """

    def __init__(
        self,
        user_agent: str,
        allowed_hostnames: frozenset[str] | set[str],
        *,
        timeout: float = 30.0,
        retries: int = 2,
        rate_limit: float = 1.5,
        obey_robots: bool = True,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not user_agent or not user_agent.strip():
            raise ValueError("Fetcher requires a transparent User-Agent string")
        self.user_agent = user_agent
        self.allowed_hostnames = {host.lower() for host in allowed_hostnames}
        self.timeout = timeout
        self.retries = retries
        self.rate_limit = rate_limit
        self.robots = RobotsCache(user_agent, timeout, transport) if obey_robots else None
        self._transport = transport
        self._client: httpx.Client | None = None
        self._last_request = 0.0

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                transport=self._transport,
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

    def _throttle(self) -> None:
        delay = self.rate_limit - (time.monotonic() - self._last_request)
        if delay > 0:
            time.sleep(delay)
        self._last_request = time.monotonic()

    def fetch(self, url: str) -> FetchResult:
        if hostname_of(url) not in self.allowed_hostnames:
            return self._failure(url, "host_not_allowed")
        if self.robots is not None and not self.robots.allowed(url):
            return self._failure(url, "robots_disallow")

        attempts = self.retries + 1
        last_error = "unknown_error"
        client = self._get_client()
        for attempt in range(attempts):
            self._throttle()
            try:
                response = client.get(url)
            except httpx.TimeoutException:
                last_error = "timeout"
                continue
            except httpx.HTTPError as exc:
                last_error = f"network_error:{type(exc).__name__}"
                continue
            if hostname_of(str(response.url)) not in self.allowed_hostnames:
                return self._failure(url, "host_not_allowed_after_redirect")
            content_type = response.headers.get("content-type", "")
            if response.status_code < 400:
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    content=response.content,
                    headers=dict(response.headers),
                    attempts=attempt + 1,
                )
            error = classify_http_error(response.status_code)
            if response.status_code in (401, 403, 404):
                return FetchResult(url, str(response.url), response.status_code, content_type, b"", dict(response.headers), error)
            last_error = error
            if attempt + 1 < attempts and response.status_code in RETRYABLE_STATUS_CODES:
                time.sleep(min(2**attempt, 5))
        return self._failure(url, last_error)

    @staticmethod
    def _failure(url: str, error: str) -> FetchResult:
        return FetchResult(url=url, final_url=url, status_code=0, content_type="", content=b"", headers={}, error=error)
