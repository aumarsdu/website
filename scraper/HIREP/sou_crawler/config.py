from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import json


DEFAULT_ENTRY_URLS = [
    "https://pbl.hirepglobal.com/",
    "https://pbl.hirepglobal.com/Professor",
    "https://pbl.hirepglobal.com/customizePoster",
]


DEFAULT_ALLOWED_HOSTS = {
    "edu4-crm-api.neoschool.com",
    "pbl.hirepglobal.com",
    "mio-crm.neoschool.com",
    "mio.neoschool.com",
}

DEFAULT_ALLOWED_ASSET_HOST_SUFFIXES = {
    "aliyuncs.com",
    "alicdn.com",
    "hirepglobal.com",
    "neoschool.com",
}


@dataclass(frozen=True)
class Settings:
    base_dir: Path = Path(".")
    output_dir: Path = Path("output")
    config_dir: Path = Path("config")
    user_agent: str = "AuthorizedResearchCrawler/1.0"
    rate_limit: float = 2.0
    timeout: float = 20.0
    retries: int = 2
    concurrency: int = 2
    max_pages: int = 100
    dry_run: bool = False
    trust_env: bool = False
    allowed_hosts: set[str] = field(default_factory=lambda: set(DEFAULT_ALLOWED_HOSTS))
    allowed_asset_host_suffixes: set[str] = field(default_factory=lambda: set(DEFAULT_ALLOWED_ASSET_HOST_SUFFIXES))
    entry_urls: list[str] = field(default_factory=lambda: list(DEFAULT_ENTRY_URLS))

    @property
    def discovery_dir(self) -> Path:
        return self.output_dir / "discovery"

    @property
    def raw_dir(self) -> Path:
        return self.output_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.output_dir / "processed"

    @property
    def assets_dir(self) -> Path:
        return self.output_dir / "assets"

    @property
    def reports_dir(self) -> Path:
        return self.output_dir / "reports"

    @property
    def api_targets_path(self) -> Path:
        return self.config_dir / "api_targets.json"

    def ensure_dirs(self) -> None:
        for path in [
            self.output_dir,
            self.discovery_dir,
            self.raw_dir,
            self.processed_dir,
            self.assets_dir,
            self.reports_dir,
            self.config_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def is_allowed_url(self, url: str, *, allow_assets: bool = False) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        hostname = parsed.hostname or ""
        if hostname in self.allowed_hosts:
            return True
        if allow_assets and parsed.scheme == "https" and self.is_allowed_asset_host(hostname):
            return True
        return False

    def is_allowed_asset_host(self, hostname: str) -> bool:
        normalized = hostname.lower().strip(".")
        return any(
            normalized == suffix or normalized.endswith(f".{suffix}")
            for suffix in self.allowed_asset_host_suffixes
        )


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_settings(args: Any | None = None) -> Settings:
    output_dir = Path(getattr(args, "output_dir", "output") or "output")
    config_dir = Path(getattr(args, "config_dir", "config") or "config")
    rate_limit = float(getattr(args, "rate_limit", 2.0) or 2.0)
    timeout = float(getattr(args, "timeout", 20.0) or 20.0)
    retries = int(getattr(args, "retries", 2) if getattr(args, "retries", None) is not None else 2)
    concurrency = int(getattr(args, "concurrency", 2) if getattr(args, "concurrency", None) is not None else 2)
    max_pages = int(getattr(args, "max_pages", 100) if getattr(args, "max_pages", None) is not None else 100)
    user_agent = getattr(args, "user_agent", None) or "AuthorizedResearchCrawler/1.0"
    dry_run = bool(getattr(args, "dry_run", False))
    trust_env = bool(getattr(args, "trust_env", False))
    entry_urls = list(getattr(args, "entry_url", None) or DEFAULT_ENTRY_URLS)
    return Settings(
        output_dir=output_dir,
        config_dir=config_dir,
        rate_limit=rate_limit,
        timeout=timeout,
        retries=retries,
        concurrency=max(1, min(3, concurrency)),
        max_pages=max_pages,
        user_agent=user_agent,
        dry_run=dry_run,
        trust_env=trust_env,
        entry_urls=entry_urls,
    )
