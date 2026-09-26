from __future__ import annotations

import asyncio
import logging
from typing import Any

from .config import Settings
from .logging_utils import log_event

LOGGER = logging.getLogger(__name__)


class CrawlStopped(RuntimeError):
    pass


class HttpFetcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_request_at = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "HttpFetcher":
        try:
            import httpx
        except ImportError as exc:
            raise SystemExit("httpx 未安装。请先运行 `python -m pip install -r requirements.txt`。") from exc
        self._httpx = httpx
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.timeout),
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "application/json,text/plain,*/*",
            },
            follow_redirects=True,
            trust_env=self.settings.trust_env,
        )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.client.aclose()

    async def request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        response = await self.request(method, url, **kwargs)
        try:
            return response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"JSON 解析失败: {url}: {exc}") from exc

    async def request_bytes(self, method: str, url: str, **kwargs: Any) -> tuple[bytes, dict[str, str]]:
        response = await self.request(method, url, **kwargs)
        return response.content, dict(response.headers)

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        if not self.settings.is_allowed_url(url, allow_assets=kwargs.pop("allow_assets", False)):
            raise ValueError(f"URL 不在授权范围内: {url}")

        retryable_statuses = {429, 500, 502, 503, 504}
        for attempt in range(self.settings.retries + 1):
            await self._throttle()
            try:
                response = await self.client.request(method, url, **kwargs)
            except self._httpx.TimeoutException as exc:
                if attempt >= self.settings.retries:
                    raise RuntimeError("timeout") from exc
                await asyncio.sleep(self._backoff(attempt))
                continue
            except self._httpx.TransportError as exc:
                if attempt >= self.settings.retries:
                    raise RuntimeError("transport_error") from exc
                await asyncio.sleep(self._backoff(attempt))
                continue

            if response.status_code in {401, 403}:
                log_event(LOGGER, logging.ERROR, "访问控制状态，停止相关任务", url=url, status=response.status_code)
                raise CrawlStopped(f"http_{response.status_code}_access_control")
            if response.status_code in retryable_statuses and attempt < self.settings.retries:
                await asyncio.sleep(self._backoff(attempt, response.status_code))
                continue
            response.raise_for_status()
            return response
        raise RuntimeError(f"请求失败: {url}")

    async def _throttle(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            elapsed = now - self._last_request_at
            wait_for = max(0.0, self.settings.rate_limit - elapsed)
            if wait_for:
                await asyncio.sleep(wait_for)
            self._last_request_at = loop.time()

    def _backoff(self, attempt: int, status: int | None = None) -> float:
        multiplier = 3 if status == 429 else 1
        return multiplier * self.settings.rate_limit * (2**attempt)
