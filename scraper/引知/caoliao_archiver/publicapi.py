"""Public H5 frontend API client for the authorized QR page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SchemaValidationError
from .fetcher import HttpFetcher
from .schema import require_object

PUBLIC_CONTENT_URL = "https://data.caoliao.net/x-llm/api/aicraft/getContentByRoute"


@dataclass(frozen=True)
class PublicH5Content:
    route: str
    markdown: str
    headers: str
    raw: dict[str, Any]


class PublicH5Client:
    def __init__(self, fetcher: HttpFetcher) -> None:
        self.fetcher = fetcher

    def get_content_by_route(self, route: str) -> PublicH5Content:
        response = self.fetcher.post_json(PUBLIC_CONTENT_URL, {"route": route})
        payload = require_object(response.json(), "public H5 content response")
        code = payload.get("code")
        if code not in {0, 1}:
            raise SchemaValidationError(f"public H5 content returned unexpected code={code}")
        data = require_object(payload.get("data"), "public H5 content data")
        markdown = data.get("markdown")
        headers = data.get("headers", "")
        if not isinstance(markdown, str):
            raise SchemaValidationError("public H5 content markdown must be a string.")
        if not isinstance(headers, str):
            raise SchemaValidationError("public H5 content headers must be a string.")
        return PublicH5Content(route=route, markdown=markdown, headers=headers, raw=payload)
