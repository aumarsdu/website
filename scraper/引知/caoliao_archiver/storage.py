"""Filesystem storage for archive artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .errors import StorageError


class ArchiveStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        for child in (
            "api/form_templates",
            "api/records",
            "html",
            "external_pages",
            "assets/files",
            "reports",
            "logs",
        ):
            (self.root / child).mkdir(parents=True, exist_ok=True)

    def write_json(self, relative_path: str, payload: Any) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(
                json.dumps(_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return path
        except OSError as exc:
            raise StorageError(str(exc)) from exc

    def write_jsonl(self, relative_path: str, rows: list[Any]) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(_jsonable(row), ensure_ascii=False, sort_keys=True))
                    handle.write("\n")
            return path
        except OSError as exc:
            raise StorageError(str(exc)) from exc

    def write_text(self, relative_path: str, text: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(text, encoding="utf-8")
            return path
        except OSError as exc:
            raise StorageError(str(exc)) from exc

    def write_bytes(self, relative_path: str, payload: bytes) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(payload)
            return path
        except OSError as exc:
            raise StorageError(str(exc)) from exc

    def asset_path_for(self, url: str, body: bytes, content_type: str | None = None) -> str:
        digest = hashlib.sha256(body).hexdigest()[:16]
        name = _filename_from_url(url)
        suffix = Path(name).suffix
        if not suffix:
            suffix = _suffix_from_content_type(content_type)
        stem = _safe_name(Path(name).stem or "asset")
        return f"assets/files/{digest}-{stem}{suffix}"

    def external_page_path_for(self, url: str, body: bytes | None = None) -> str:
        digest_source = body if body is not None else url.encode("utf-8")
        digest = hashlib.sha256(digest_source).hexdigest()[:16]
        parsed = urlparse(url)
        host = _safe_name(parsed.hostname or "external")
        name = _safe_name(_filename_from_url(url))
        if not Path(name).suffix:
            name = f"{name}.html"
        return f"external_pages/{digest}-{host}-{name}"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    return name or "asset"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")[:80] or "asset"


def _suffix_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return ".bin"
    content_type = content_type.split(";", 1)[0].strip().lower()
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
        "audio/mpeg": ".mp3",
        "video/mp4": ".mp4",
        "text/html": ".html",
        "application/json": ".json",
    }.get(content_type, ".bin")
