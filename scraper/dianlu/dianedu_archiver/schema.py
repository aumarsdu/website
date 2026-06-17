from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PageRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_url: str
    canonical_url: str
    crawled_at: str
    title: str | None = None
    content_type: str | None = None
    status_code: int | None = None
    html_path: str | None = None
    text_hash: str | None = None
    links: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    forms: list[dict[str, Any]] = Field(default_factory=list)
    json_ld: list[Any] = Field(default_factory=list)


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_url: str
    canonical_url: str
    crawled_at: str
    title: str
    category: str | None = None
    location: str | None = None
    grade: str | None = None
    project_type: str | None = None
    summary: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    assets: list[str] = Field(default_factory=list)


class ArticleRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_url: str
    canonical_url: str
    crawled_at: str
    title: str
    category: str | None = None
    published_at: str | None = None
    author: str | None = None
    summary: str | None = None
    body_markdown: str | None = None
    assets: list[str] = Field(default_factory=list)


class AssetRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str
    source_url: str | None = None
    local_path: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    status_code: int | None = None
    downloaded_at: str | None = None


class CrawlError(BaseModel):
    url: str
    error_type: str
    message: str
    occurred_at: str
    status_code: int | None = None


class ApiObservation(BaseModel):
    method: str
    url: str
    status_code: int | None = None
    resource_type: str | None = None
    content_type: str | None = None
    observed_at: str
    request_headers: dict[str, str] = Field(default_factory=dict)
    response_summary: dict[str, Any] = Field(default_factory=dict)


def validate_http_url(value: str) -> str:
    return str(HttpUrl(value))
