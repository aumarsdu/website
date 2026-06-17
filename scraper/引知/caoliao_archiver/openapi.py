"""Caoliao OpenAPI V2 client."""

from __future__ import annotations

from typing import Any, Iterator

from .fetcher import HttpFetcher
from .schema import ApiEnvelope, require_list, require_object

BASE_URL = "https://open.cli.im"


class CaoliaoOpenApiClient:
    def __init__(self, fetcher: HttpFetcher, api_key: str) -> None:
        self.fetcher = fetcher
        self.api_key = api_key

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def get_content(self, qrcode_url: str, output_format: str = "json") -> dict[str, Any]:
        return require_object(
            self._rpc(
                "qrcodes/getContent",
                {"qrcode": qrcode_url, "format": output_format},
            ),
            "qrcodes/getContent data",
        )

    def get_operations(self, qrcode_url: str) -> list[dict[str, Any]]:
        rows = require_list(
            self._rpc("qrcodes/getOperation", {"qrcode": qrcode_url}),
            "qrcodes/getOperation data",
        )
        return [require_object(row, "operation item") for row in rows]

    def get_form_template(self, tpl_id: int) -> dict[str, Any]:
        return require_object(
            self._rpc("forms/getTemplate", {"tpl_id": tpl_id}),
            "forms/getTemplate data",
        )

    def iter_records(
        self,
        *,
        tpl_id: int,
        qrcode_id: int | None,
        page_size: int,
        max_pages: int,
    ) -> Iterator[dict[str, Any]]:
        page_token: str | None = None
        pages_seen = 0
        while pages_seen < max_pages:
            payload: dict[str, Any] = {
                "filters": {"record_template": {"id": tpl_id}},
                "format": "json",
                "page_size": page_size,
                "get_total_count": 1,
            }
            if qrcode_id is not None:
                payload["filters"]["qrcode"] = {"id": qrcode_id}
            if page_token:
                payload["page_token"] = page_token

            data = require_object(
                self._rpc("record/getRecords", payload),
                "record/getRecords data",
            )
            rows = _extract_records(data)
            for row in rows:
                yield require_object(row, "record item")

            pages_seen += 1
            next_token = _extract_next_token(data)
            if not next_token:
                return
            page_token = next_token

    def _rpc(self, route: str, payload: dict[str, Any]) -> Any:
        url = f"{BASE_URL}/api/v2/rpc/{route}"
        response = self.fetcher.post_json(url, payload, headers=self.auth_headers)
        envelope = ApiEnvelope.parse(response.json())
        return envelope.data


def _extract_records(data: dict[str, Any]) -> list[Any]:
    for key in ("list", "records", "items", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _extract_next_token(data: dict[str, Any]) -> str | None:
    for key in ("next_page_token", "page_token", "next_token"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    page = data.get("pagination")
    if isinstance(page, dict):
        value = page.get("next_page_token") or page.get("next_token")
        if isinstance(value, str) and value:
            return value
    return None
