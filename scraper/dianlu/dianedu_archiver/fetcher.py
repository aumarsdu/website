from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
import json
import logging

from .config import Settings
from .schema import CrawlError
from .utils import utc_now

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str
    status_code: int | None
    content_type: str | None
    text: str | None = None
    content: bytes | None = None
    error: CrawlError | None = None


class Fetcher:
    def __init__(self, settings: Settings) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise SystemExit("缺少 httpx。请先运行 `python -m pip install -r requirements.txt`。") from exc
        self.settings = settings
        self._last_request = 0.0
        self._client = httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent, "Accept": "*/*"},
            timeout=settings.timeout,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, url: str, *, binary: bool = False) -> FetchResult:
        if not self.settings.is_allowed_url(url):
            return FetchResult(
                url=url,
                final_url=url,
                status_code=None,
                content_type=None,
                error=CrawlError(url=url, error_type="out_of_scope", message="URL is outside allowed www.dianedu.com scope.", occurred_at=utc_now()),
            )
        for attempt in range(self.settings.retries + 1):
            await self._throttle()
            try:
                response = await self._client.get(url)
            except TimeoutError as exc:
                error = CrawlError(url=url, error_type="timeout", message=str(exc), occurred_at=utc_now())
                if attempt < self.settings.retries:
                    await asyncio.sleep(self.settings.rate_limit * (attempt + 1))
                    continue
                return FetchResult(url=url, final_url=url, status_code=None, content_type=None, error=error)
            except Exception as exc:  # noqa: BLE001 - network client surfaces multiple transport exceptions.
                if exc.__class__.__name__ == "TimeoutException":
                    error = CrawlError(url=url, error_type="timeout", message=str(exc), occurred_at=utc_now())
                    if attempt < self.settings.retries:
                        await asyncio.sleep(self.settings.rate_limit * (attempt + 1))
                        continue
                    return FetchResult(url=url, final_url=url, status_code=None, content_type=None, error=error)
                return FetchResult(
                    url=url,
                    final_url=url,
                    status_code=None,
                    content_type=None,
                    error=CrawlError(url=url, error_type="unknown_error", message=str(exc), occurred_at=utc_now()),
                )

            content_type = response.headers.get("content-type")
            error_type = classify_status(response.status_code)
            if error_type in {"http_401_unauthorized", "http_403_forbidden"}:
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    error=CrawlError(url=url, status_code=response.status_code, error_type=error_type, message="Access denied; no bypass attempted.", occurred_at=utc_now()),
                )
            if error_type in {"http_429_rate_limited", "http_5xx_server_error"} and attempt < self.settings.retries:
                delay = self.settings.rate_limit * (attempt + 2) * (3 if response.status_code == 429 else 1)
                LOGGER.info("可重试响应 %s，退避 %.1fs: %s", response.status_code, delay, url)
                await asyncio.sleep(delay)
                continue
            if error_type:
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    error=CrawlError(url=url, status_code=response.status_code, error_type=error_type, message=f"HTTP {response.status_code}", occurred_at=utc_now()),
                )
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=content_type,
                text=None if binary else response.text,
                content=response.content if binary else None,
            )
        return FetchResult(url=url, final_url=url, status_code=None, content_type=None)

    async def post_json(self, url: str, payload: dict[str, Any]) -> FetchResult:
        if not self.settings.is_allowed_url(url):
            return FetchResult(
                url=url,
                final_url=url,
                status_code=None,
                content_type=None,
                error=CrawlError(url=url, error_type="out_of_scope", message="URL is outside allowed www.dianedu.com scope.", occurred_at=utc_now()),
            )
        for attempt in range(self.settings.retries + 1):
            await self._throttle()
            try:
                response = await self._client.post(url, json=payload)
            except TimeoutError as exc:
                error = CrawlError(url=url, error_type="timeout", message=str(exc), occurred_at=utc_now())
                if attempt < self.settings.retries:
                    await asyncio.sleep(self.settings.rate_limit * (attempt + 1))
                    continue
                return FetchResult(url=url, final_url=url, status_code=None, content_type=None, error=error)
            except Exception as exc:  # noqa: BLE001
                if exc.__class__.__name__ == "TimeoutException":
                    error = CrawlError(url=url, error_type="timeout", message=str(exc), occurred_at=utc_now())
                    if attempt < self.settings.retries:
                        await asyncio.sleep(self.settings.rate_limit * (attempt + 1))
                        continue
                    return FetchResult(url=url, final_url=url, status_code=None, content_type=None, error=error)
                return FetchResult(
                    url=url,
                    final_url=url,
                    status_code=None,
                    content_type=None,
                    error=CrawlError(url=url, error_type="unknown_error", message=str(exc), occurred_at=utc_now()),
                )
            content_type = response.headers.get("content-type")
            error_type = classify_status(response.status_code)
            if error_type in {"http_401_unauthorized", "http_403_forbidden"}:
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    error=CrawlError(url=url, status_code=response.status_code, error_type=error_type, message="Access denied; no bypass attempted.", occurred_at=utc_now()),
                )
            if error_type in {"http_429_rate_limited", "http_5xx_server_error"} and attempt < self.settings.retries:
                await asyncio.sleep(self.settings.rate_limit * (attempt + 2) * (3 if response.status_code == 429 else 1))
                continue
            if error_type:
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    error=CrawlError(url=url, status_code=response.status_code, error_type=error_type, message=f"HTTP {response.status_code}", occurred_at=utc_now()),
                )
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=content_type,
                text=response.text,
            )
        return FetchResult(url=url, final_url=url, status_code=None, content_type=None)

    async def _throttle(self) -> None:
        loop = asyncio.get_running_loop()
        now = loop.time()
        wait = self.settings.rate_limit - (now - self._last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request = loop.time()


def classify_status(status_code: int) -> str | None:
    if status_code == 401:
        return "http_401_unauthorized"
    if status_code == 403:
        return "http_403_forbidden"
    if status_code == 404:
        return "http_404_not_found"
    if status_code == 429:
        return "http_429_rate_limited"
    if 500 <= status_code <= 599:
        return "http_5xx_server_error"
    if status_code >= 400:
        return "unknown_error"
    return None
