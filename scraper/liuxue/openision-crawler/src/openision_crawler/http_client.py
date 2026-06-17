from __future__ import annotations

import json
import time
from dataclasses import dataclass
from http.client import IncompleteRead
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from .config import Settings
from .sanitize import sanitize_text


class ApiClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ApiResponse:
    url: str
    status_code: int
    content_type: str
    body_text: str
    json_data: dict[str, Any]


class OpenisionApiClient:
    def __init__(self, settings: Settings, *, timeout: int = 30, retries: int = 2) -> None:
        self.settings = settings
        self.timeout = timeout
        self.retries = retries
        self.api_base_url = "https://openisionapi.openision.com"
        self._fc_token: str | None = None

    def _base_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.settings.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": self.settings.base_url,
            "Referer": f"{self.settings.base_url}/",
        }

    def _request_raw(self, method: str, url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, str, str]:
        request = Request(url, data=data, headers=headers or self._base_headers(), method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
                return response.status, response.headers.get("content-type", ""), body
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ApiClientError(sanitize_text(body[:1000]) or str(exc), status_code=exc.code) from exc
        except IncompleteRead as exc:
            raise ApiClientError(f"incomplete_read: expected more bytes after {len(exc.partial)} bytes", status_code=503) from exc
        except URLError as exc:
            raise ApiClientError(str(exc), status_code=None) from exc

    def refresh_fc_token(self) -> None:
        url = urljoin(self.api_base_url, "/api/v1/fc_auth")
        status, _, body = self._request_raw("POST", url, data=b"{}", headers=self._base_headers())
        if status != 200:
            raise ApiClientError("fc_auth returned non-200 status", status_code=status)
        payload = json.loads(body)
        token = (payload.get("data") or {}).get("token")
        if payload.get("code") != 0 or not isinstance(token, str) or not token:
            raise ApiClientError("fc_auth did not return a usable token", status_code=status)
        self._fc_token = token

    def request_json(self, path: str, *, params: dict[str, Any] | None = None, method: str = "GET") -> ApiResponse:
        if not self._fc_token:
            self.refresh_fc_token()
        query = urlencode(params or {}, doseq=True)
        url = urljoin(self.api_base_url, path)
        if query:
            url = f"{url}?{query}"
        last_error: ApiClientError | None = None
        for attempt in range(self.retries + 1):
            headers = self._base_headers()
            headers["FCAuthorization"] = f"Bearer {self._fc_token}"
            try:
                status, content_type, body = self._request_raw(method, url, headers=headers)
                payload = json.loads(body)
                if isinstance(payload, dict) and payload.get("code") == 0:
                    return ApiResponse(url=url, status_code=status, content_type=content_type, body_text=sanitize_text(body), json_data=payload)
                if isinstance(payload, dict) and payload.get("code") == 401:
                    self.refresh_fc_token()
                    continue
                raise ApiClientError(sanitize_text(body[:1000]), status_code=status)
            except ApiClientError as exc:
                last_error = exc
                if exc.status_code in {401}:
                    self.refresh_fc_token()
                elif exc.status_code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    time.sleep(2**attempt)
                else:
                    break
        raise last_error or ApiClientError("unknown api error")
