"""HTTP fetcher with conservative throttling and retry policy."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .errors import (
    AuthError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    TimeoutArchiveError,
    classify_http_status,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HttpResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        charset = "utf-8"
        content_type = self.headers.get("content-type", "")
        for part in content_type.split(";"):
            if "charset=" in part:
                charset = part.split("=", 1)[1].strip()
        return self.body.decode(charset, errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class HttpFetcher:
    def __init__(
        self,
        user_agent: str,
        rate_limit_seconds: float,
        timeout_seconds: float,
        retries: int,
    ) -> None:
        self.user_agent = user_agent
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self._last_request_at = 0.0

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        return self.request("GET", url, headers=headers)

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        merged_headers = {"Content-Type": "application/json", **(headers or {})}
        return self.request("POST", url, body=body, headers=merged_headers)

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        request_headers = {"User-Agent": self.user_agent, **(headers or {})}
        attempts = self.retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            self._throttle()
            request = urllib.request.Request(
                url=url,
                data=body,
                headers=request_headers,
                method=method,
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                    response_body = resp.read()
                    return HttpResponse(
                        url=resp.geturl(),
                        status_code=resp.status,
                        headers={k.lower(): v for k, v in resp.headers.items()},
                        body=response_body,
                    )
            except TimeoutError as exc:
                last_error = TimeoutArchiveError(str(exc))
                LOGGER.warning(
                    "request_timeout",
                    extra={"url": url, "attempt": attempt, "category": "timeout"},
                )
            except urllib.error.HTTPError as exc:
                category = classify_http_status(exc.code)
                if exc.code in {401, 403, 404}:
                    raise _raise_http_error(exc.code, exc.reason)
                if exc.code == 429 or 500 <= exc.code <= 599:
                    last_error = _build_http_error(exc.code, exc.reason)
                    LOGGER.warning(
                        "request_retryable_http_error",
                        extra={"url": url, "attempt": attempt, "category": category},
                    )
                else:
                    raise _build_http_error(exc.code, exc.reason)
            except urllib.error.URLError as exc:
                last_error = TimeoutArchiveError(str(exc.reason))
                LOGGER.warning(
                    "request_url_error",
                    extra={"url": url, "attempt": attempt, "category": "timeout"},
                )

            if attempt < attempts:
                time.sleep(min(2**attempt, 10))

        if last_error:
            raise last_error
        raise TimeoutArchiveError(f"Request failed: {method} {url}")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait_seconds = self.rate_limit_seconds - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._last_request_at = time.monotonic()


def _raise_http_error(status_code: int, reason: str) -> None:
    raise _build_http_error(status_code, reason)


def _build_http_error(status_code: int, reason: str) -> Exception:
    message = f"HTTP {status_code}: {reason}"
    if status_code == 401:
        return AuthError(message)
    if status_code == 403:
        return ForbiddenError(message)
    if status_code == 404:
        return NotFoundError(message)
    if status_code == 429:
        return RateLimitedError(message)
    if 500 <= status_code <= 599:
        return ServerError(message)
    return ServerError(message)
