from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from .config import CrawlSettings
from .utils import is_allowed_url, is_public_asset_url, redact_obj

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    method: str
    status_code: int | None
    headers: dict[str, str]
    json_data: Any | None
    text: str | None
    bytes_data: bytes | None = None
    error_category: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300 and self.error_category is None


class AsyncFetcher:
    def __init__(self, settings: CrawlSettings):
        self.settings = settings
        self._client: Any | None = None
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "AsyncFetcher":
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is not installed. Run: pip install -r requirements.txt") from exc
        self._client = httpx.AsyncClient(
            timeout=self.settings.timeout,
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "application/json,text/plain,*/*",
            },
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        if not is_allowed_url(url, self.settings.allowed_domains) and not is_public_asset_url(url):
            return FetchResult(url, method, None, {}, None, None, None, "outside_authorized_scope", "URL host is not in allowed domains")
        assert self._client is not None
        retries = max(self.settings.retries, 0)
        for attempt in range(retries + 1):
            await self._throttle()
            try:
                response = await self._client.request(
                    method.upper(),
                    url,
                    params=params,
                    json=json_body,
                    data=data,
                    headers=headers,
                )
            except Exception as exc:
                category = "timeout" if "Timeout" in type(exc).__name__ else "unknown_error"
                if attempt < retries:
                    await asyncio.sleep(min(8, 2**attempt))
                    continue
                return FetchResult(url, method, None, {}, None, None, None, category, str(exc))

            category = classify_status(response.status_code)
            if not is_allowed_url(str(response.url), self.settings.allowed_domains) and not is_public_asset_url(str(response.url)):
                return await self._build_result(response, "outside_authorized_scope", "final URL after redirect is not in allowed domains")
            if category == "http_403_forbidden":
                return await self._build_result(response, category, "403 received; stopping this request without retry")
            if category == "http_401_unauthorized":
                return await self._build_result(response, category, "401 received; authentication required")
            if category in {"http_429_rate_limited", "http_5xx_server_error"} and attempt < retries:
                await asyncio.sleep(min(30, (2**attempt) * self.settings.rate_limit + 1))
                continue
            return await self._build_result(response, category, None)
        return FetchResult(url, method, None, {}, None, None, None, "unknown_error", "unreachable retry state")

    async def download(self, url: str) -> FetchResult:
        return await self.request("GET", url)

    async def _throttle(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            elapsed = loop.time() - self._last_request
            wait = self.settings.rate_limit - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = loop.time()

    async def _build_result(self, response: Any, category: str | None, message: str | None) -> FetchResult:
        text: str | None = None
        bytes_data: bytes | None = None
        json_data: Any | None = None
        content_type = response.headers.get("content-type", "")
        content = response.content or b""
        looks_like_json = content.lstrip().startswith((b"{", b"["))
        if "json" in content_type or looks_like_json:
            try:
                json_data = redact_obj(response.json())
            except (json.JSONDecodeError, ValueError):
                text = response.text
        else:
            if response.is_error:
                text = response.text
            else:
                bytes_data = response.content
        return FetchResult(
            url=str(response.url),
            method=response.request.method,
            status_code=response.status_code,
            headers=dict(response.headers),
            json_data=json_data,
            text=text,
            bytes_data=bytes_data,
            error_category=category,
            error_message=message,
        )


def classify_status(status: int) -> str | None:
    if status == 401:
        return "http_401_unauthorized"
    if status == 403:
        return "http_403_forbidden"
    if status == 404:
        return "http_404_not_found"
    if status == 429:
        return "http_429_rate_limited"
    if 500 <= status <= 599:
        return "http_5xx_server_error"
    if 400 <= status <= 499:
        return "http_client_error"
    return None
