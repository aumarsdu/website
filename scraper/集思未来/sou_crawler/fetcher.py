from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from .config import CrawlConfig
from .utils import redact_headers

LOGGER = logging.getLogger(__name__)


@dataclass
class CrawlStats:
    pages_requested: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    records_extracted: int = 0
    duplicate_records: int = 0
    error_categories: dict[str, int] = field(default_factory=dict)

    def error(self, category: str) -> None:
        self.pages_failed += 1
        self.error_categories[category] = self.error_categories.get(category, 0) + 1


class Fetcher:
    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self.client = None
        if httpx is not None:
            limits = httpx.Limits(max_connections=config.concurrency, max_keepalive_connections=config.concurrency)
            self.client = httpx.AsyncClient(
                timeout=config.timeout,
                headers={"User-Agent": config.user_agent, "Accept": "application/json,text/plain,*/*"},
                follow_redirects=True,
                limits=limits,
            )
        self.stats = CrawlStats()

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any | None, dict[str, Any]]:
        last_error = "unknown_error"
        for attempt in range(self.config.retries + 1):
            if attempt:
                await asyncio.sleep(self.config.rate_limit * (2**attempt))
            else:
                await asyncio.sleep(self.config.rate_limit)
            self.stats.pages_requested += 1
            if self.client is None:
                payload, meta = await self._request_json_urllib(
                    method,
                    url,
                    params=params,
                    json_body=json_body,
                    headers=headers,
                )
                category = meta.get("error_category")
                if category:
                    if category in {"http_401_unauthorized", "http_403_forbidden", "http_404_not_found"}:
                        self.stats.error(category)
                        if category == "http_403_forbidden":
                            meta["stop_reason"] = "forbidden"
                        return None, meta
                    last_error = category
                    continue
                self.stats.pages_succeeded += 1
                return payload, meta
            try:
                response = await self.client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=redact_headers(headers) if headers else None,
                )
            except httpx.TimeoutException:
                last_error = "timeout"
                continue
            except httpx.HTTPError as exc:
                LOGGER.warning("http error %s %s: %s", method, url, exc)
                last_error = "unknown_error"
                continue

            meta = {
                "url": str(response.url),
                "method": method.upper(),
                "status": response.status_code,
                "response_headers": redact_headers(dict(response.headers)),
            }
            category = classify_status(response.status_code)
            if response.status_code == 403:
                self.stats.error(category)
                return None, {**meta, "error_category": category, "stop_reason": "forbidden"}
            if response.status_code in {401, 404}:
                self.stats.error(category)
                return None, {**meta, "error_category": category}
            if response.status_code == 429 or 500 <= response.status_code < 600:
                last_error = category
                continue
            try:
                payload = response.json()
            except ValueError:
                self.stats.error("parse_error")
                return None, {**meta, "error_category": "parse_error", "text_sample": response.text[:500]}
            self.stats.pages_succeeded += 1
            return payload, meta
        self.stats.error(last_error)
        return None, {"url": url, "method": method.upper(), "error_category": last_error}

    async def _request_json_urllib(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any | None, dict[str, Any]]:
        return await asyncio.to_thread(
            self._request_json_urllib_sync,
            method,
            url,
            params,
            json_body,
            headers,
        )

    def _request_json_urllib_sync(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        json_body: Any,
        headers: dict[str, str] | None,
    ) -> tuple[Any | None, dict[str, Any]]:
        final_url = append_params(url, params or {})
        request_headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/json,text/plain,*/*",
        }
        if headers:
            request_headers.update(redact_headers(headers))
        data = None
        if json_body is not None:
            data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(final_url, data=data, headers=request_headers, method=method.upper())
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                body = response.read()
                meta = {
                    "url": response.url,
                    "method": method.upper(),
                    "status": response.status,
                    "response_headers": redact_headers(dict(response.headers)),
                }
        except HTTPError as exc:
            return None, {
                "url": final_url,
                "method": method.upper(),
                "status": exc.code,
                "response_headers": redact_headers(dict(exc.headers)),
                "error_category": classify_status(exc.code),
            }
        except TimeoutError:
            return None, {"url": final_url, "method": method.upper(), "error_category": "timeout"}
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            category = "timeout" if isinstance(reason, TimeoutError) else "unknown_error"
            return None, {"url": final_url, "method": method.upper(), "error_category": category}

        if meta["status"] in {401, 403, 404, 429} or meta["status"] >= 500:
            return None, {**meta, "error_category": classify_status(meta["status"])}
        try:
            return json.loads(body.decode("utf-8")), meta
        except ValueError:
            return None, {**meta, "error_category": "parse_error", "text_sample": body[:500].decode("utf-8", "ignore")}


def classify_status(status: int) -> str:
    if status == 401:
        return "http_401_unauthorized"
    if status == 403:
        return "http_403_forbidden"
    if status == 404:
        return "http_404_not_found"
    if status == 429:
        return "http_429_rate_limited"
    if 500 <= status < 600:
        return "http_5xx_server_error"
    return "unknown_error"


def set_query_param(url: str, name: str, value: Any) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[name] = str(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def append_params(url: str, params: dict[str, Any]) -> str:
    if not params:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({key: str(value) for key, value in params.items()})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
