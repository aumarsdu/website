"""Configuration loading and URL scope enforcement."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from .errors import ConfigError, ScopeError

DEFAULT_ENTRY_URL = (
    "https://h5.clewm.net/?url=h.qr61.cn%2FodBU6p%2FqYtCDec"
    "&hasredirect=1&lid=blpnggjbbhctbq2o9&rlid=irerkrbt5rhta8it8&from=timeline"
)
DEFAULT_QRCODE_URL = "https://h.qr61.cn/odBU6p/qYtCDec"


@dataclass(frozen=True)
class ArchiveConfig:
    entry_url: str = DEFAULT_ENTRY_URL
    api_key_env: str = "CAOLIAO_API_KEY"
    output_dir: Path = Path("data/archive")
    user_agent: str = (
        "caoliao-authorized-archiver/0.1 "
        "(+authorized local archive; contact: replace@example.com)"
    )
    rate_limit_seconds: float = 1.0
    timeout_seconds: float = 20.0
    retries: int = 2
    max_pages: int = 200
    max_assets: int = 500
    max_external_pages: int = 20
    records_page_size: int = 50
    download_assets: bool = True
    fetch_h5_snapshot: bool = True
    include_records: bool = True
    allowed_qrcode_urls: tuple[str, ...] = (DEFAULT_QRCODE_URL,)
    allowed_resource_hosts: tuple[str, ...] = (
        "h.qr61.cn",
        "qr61.cn",
        "h.qr71.cn",
        "qr71.cn",
        "h5.clewm.net",
        "gstatic.clewm.net",
        "static.clewm.net",
        "ncstatic.clewm.net",
        "blogcdnimg.clewm.net",
        "oss.cli.im",
        "cli.im",
        "open.cli.im",
    )
    external_page_whitelist: tuple[str, ...] = field(default_factory=tuple)

    @property
    def qrcode_url(self) -> str:
        return normalize_entry_to_qrcode(self.entry_url)

    @property
    def qrcode_route(self) -> str:
        return qrcode_route_from_url(self.qrcode_url)

    @property
    def api_key(self) -> str | None:
        value = os.environ.get(self.api_key_env)
        return value.strip() if value and value.strip() else None

    def assert_qrcode_in_scope(self) -> None:
        normalized = self.qrcode_url
        allowed = {canonicalize_url(url) for url in self.allowed_qrcode_urls}
        if canonicalize_url(normalized) not in allowed:
            raise ScopeError(
                f"qrcode_url is outside allowed_qrcode_urls: {normalized}"
            )

    def is_resource_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = (parsed.hostname or "").lower()
        if host in {h.lower() for h in self.allowed_resource_hosts}:
            return True
        return canonicalize_url(url) in {
            canonicalize_url(item) for item in self.external_page_whitelist
        }

    def is_external_page_allowed(self, url: str) -> bool:
        return canonicalize_url(url) in {
            canonicalize_url(item) for item in self.external_page_whitelist
        }


def load_config(path: str | Path | None) -> ArchiveConfig:
    if not path:
        cfg = ArchiveConfig()
        cfg.assert_qrcode_in_scope()
        return cfg

    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError("Config file must contain a JSON object.")

    allowed_keys = {field.name for field in ArchiveConfig.__dataclass_fields__.values()}
    unknown = set(data) - allowed_keys
    if unknown:
        raise ConfigError(f"Unknown config keys: {sorted(unknown)}")

    if "output_dir" in data:
        data["output_dir"] = Path(data["output_dir"])
    for tuple_key in (
        "allowed_qrcode_urls",
        "allowed_resource_hosts",
        "external_page_whitelist",
    ):
        if tuple_key in data:
            data[tuple_key] = tuple(data[tuple_key])

    cfg = ArchiveConfig(**data)
    cfg.assert_qrcode_in_scope()
    if cfg.records_page_size < 1 or cfg.records_page_size > 50:
        raise ConfigError("records_page_size must be between 1 and 50.")
    if cfg.max_pages < 1:
        raise ConfigError("max_pages must be greater than 0.")
    if cfg.max_assets < 0:
        raise ConfigError("max_assets must be >= 0.")
    if cfg.max_external_pages < 0:
        raise ConfigError("max_external_pages must be >= 0.")
    if cfg.rate_limit_seconds < 0:
        raise ConfigError("rate_limit_seconds must be >= 0.")
    return cfg


def normalize_entry_to_qrcode(entry_url: str) -> str:
    parsed = urlparse(entry_url)
    if parsed.hostname == "h5.clewm.net":
        query = parse_qs(parsed.query)
        raw_url = query.get("url", [None])[0]
        if not raw_url:
            raise ConfigError("h5.clewm.net entry URL must include a url= parameter.")
        return normalize_qrcode_url(unquote(raw_url))
    return normalize_qrcode_url(entry_url)


def normalize_qrcode_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url:
        raise ConfigError("QR code URL is empty.")
    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise ConfigError(f"Unsupported QR code URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ConfigError("QR code URL must include a host.")
    parsed = parsed._replace(scheme="https", query="", fragment="")
    return canonicalize_url(urlunparse(parsed))


def qrcode_route_from_url(qrcode_url: str) -> str:
    parsed = urlparse(normalize_qrcode_url(qrcode_url))
    return f"{parsed.netloc}{parsed.path}"


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    host = (parsed.hostname or "").lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunparse((scheme, f"{host}{port}", path, "", parsed.query, ""))


def redact_headers(headers: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(headers)
    if "Authorization" in redacted:
        redacted["Authorization"] = "Bearer <redacted>"
    return redacted
