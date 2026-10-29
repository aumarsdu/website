from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CrawlConfig:
    base_url: str = "https://xntj.tv/"
    sitemap_url: str = "https://xntj.tv/sitemap.xml"
    output_dir: Path = Path("archive")
    rate_limit: float = 1.0
    timeout: float = 30.0
    retries: int = 3
    max_asset_bytes: int = 200 * 1024 * 1024
    user_agent: str = "xntj-archive/1.0 (authorized archival; contact: site-owner)"

