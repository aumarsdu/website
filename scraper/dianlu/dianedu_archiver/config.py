from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse


DEFAULT_BASE_URL = "https://www.dianedu.com/"
DEFAULT_SEARCH_URL = "https://www.dianedu.com/Search"
DEFAULT_USER_AGENT = "AuthorizedDianEduArchiveCrawler/1.0"
DENIED_HOSTS = {"admin.dianedu.com"}
ALLOWED_HOSTS = {"www.dianedu.com", "dianedu.com"}
ASSET_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
    ".mp4",
    ".webm",
    ".mov",
    ".mp3",
    ".wav",
    ".css",
    ".js",
}


@dataclass(slots=True)
class Settings:
    root_dir: Path
    base_url: str = DEFAULT_BASE_URL
    search_url: str = DEFAULT_SEARCH_URL
    user_agent: str = DEFAULT_USER_AGENT
    rate_limit: float = 2.0
    timeout: float = 30.0
    retries: int = 2
    concurrency: int = 2
    max_pages: int = 100
    dry_run: bool = False
    verbose: bool = False
    entry_urls: list[str] = field(default_factory=list)

    @property
    def raw_dir(self) -> Path:
        return self.root_dir / "data" / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.root_dir / "data" / "processed"

    @property
    def assets_dir(self) -> Path:
        return self.root_dir / "data" / "assets"

    @property
    def discovery_dir(self) -> Path:
        return self.root_dir / "discovery"

    @property
    def reports_dir(self) -> Path:
        return self.root_dir / "reports"

    @property
    def archives_dir(self) -> Path:
        return self.root_dir / "archives"

    @property
    def db_path(self) -> Path:
        return self.processed_dir / "dianedu.sqlite"

    def ensure_dirs(self) -> None:
        for path in (
            self.raw_dir,
            self.processed_dir,
            self.assets_dir,
            self.discovery_dir,
            self.reports_dir,
            self.archives_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def allowed_entry_urls(self) -> list[str]:
        urls = self.entry_urls or [self.base_url, self.search_url]
        return [canonicalize_url(url, self.base_url) for url in urls if self.is_allowed_url(url)]

    def is_allowed_url(self, url: str) -> bool:
        parsed = urlparse(canonicalize_url(url, self.base_url))
        host = parsed.netloc.lower()
        if host in DENIED_HOSTS:
            return False
        return host in ALLOWED_HOSTS

    def is_asset_url(self, url: str) -> bool:
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix.lower()
        return suffix in ASSET_EXTENSIONS


def canonicalize_url(url: str, base_url: str = DEFAULT_BASE_URL) -> str:
    absolute = urljoin(base_url, url)
    parsed = urlparse(absolute)
    scheme = parsed.scheme.lower() or "https"
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((scheme, host, path, "", parsed.query, ""))


def load_settings(args: object) -> Settings:
    root = Path(getattr(args, "root_dir", None) or Path.cwd()).resolve()
    concurrency = max(1, min(int(getattr(args, "concurrency", 2)), 3))
    rate_limit = max(1.0, min(float(getattr(args, "rate_limit", 2.0)), 10.0))
    return Settings(
        root_dir=root,
        base_url=getattr(args, "base_url", DEFAULT_BASE_URL),
        search_url=getattr(args, "search_url", DEFAULT_SEARCH_URL),
        user_agent=getattr(args, "user_agent", DEFAULT_USER_AGENT),
        rate_limit=rate_limit,
        timeout=float(getattr(args, "timeout", 30.0)),
        retries=max(0, int(getattr(args, "retries", 2))),
        concurrency=concurrency,
        max_pages=max(1, int(getattr(args, "max_pages", 100))),
        dry_run=bool(getattr(args, "dry_run", False)),
        verbose=bool(getattr(args, "verbose", False)),
        entry_urls=list(getattr(args, "entry_url", None) or []),
    )
