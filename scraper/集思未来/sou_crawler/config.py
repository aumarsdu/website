from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_USER_AGENT = "AuthorizedResearchCrawler/1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SiteTarget:
    name: str
    label: str
    base_url: str
    discovery_entries: tuple[str, ...]


SITE_TARGETS: tuple[SiteTarget, ...] = (
    SiteTarget(
        name="sou_tools",
        label="海外教授",
        base_url="https://sou-tools.gecacademy.cn/",
        discovery_entries=(
            "https://sou-tools.gecacademy.cn/",
            "https://sou-tools.gecacademy.cn/detailPage?level1=1",
            "https://sou-tools.gecacademy.cn/detailPage?level1=2",
            "https://sou-tools.gecacademy.cn/detailPage?level1=3",
            "https://sou-tools.gecacademy.cn/detailPage?level1=4",
            "https://sou-tools.gecacademy.cn/detailPage?level1=5",
            "https://sou-tools.gecacademy.cn/detailPage?level1=6",
            "https://sou-tools.gecacademy.cn/detailPage?level1=7",
            "https://sou-tools.gecacademy.cn/detailPage?level1=8",
            "https://sou-tools.gecacademy.cn/detailPage?level1=9",
            "https://sou-tools.gecacademy.cn/detailPage?level1=10",
        ),
    ),
    SiteTarget(
        name="domestic",
        label="华人教授",
        base_url="https://domestic.gecacademy.cn/",
        discovery_entries=(
            "https://domestic.gecacademy.cn/",
            "https://domestic.gecacademy.cn/detailPage?level1=1",
            "https://domestic.gecacademy.cn/detailPage?level1=2",
            "https://domestic.gecacademy.cn/detailPage?level1=3",
            "https://domestic.gecacademy.cn/detailPage?level1=4",
            "https://domestic.gecacademy.cn/detailPage?level1=5",
            "https://domestic.gecacademy.cn/detailPage?level1=6",
            "https://domestic.gecacademy.cn/detailPage?level1=7",
            "https://domestic.gecacademy.cn/detailPage?level1=8",
            "https://domestic.gecacademy.cn/detailPage?level1=9",
            "https://domestic.gecacademy.cn/detailPage?level1=10",
        ),
    ),
)

DEFAULT_DISCOVERY_ENTRIES = tuple(
    entry for target in SITE_TARGETS for entry in target.discovery_entries
)


@dataclass(frozen=True)
class CrawlConfig:
    base_url: str = "https://sou-tools.gecacademy.cn/"
    mobile_base_url: str = "https://sou-m.gecacademy.cn/"
    user_agent: str = DEFAULT_USER_AGENT
    output_dir: Path = PROJECT_ROOT / "output"
    timeout: float = 20.0
    retries: int = 2
    rate_limit: float = 1.5
    concurrency: int = 2
    max_pages: int = 100
    max_details: int = 10000
    discovery_wait_ms: int = 5000
    discovery_entries: tuple[str, ...] = field(default_factory=lambda: DEFAULT_DISCOVERY_ENTRIES)

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


def ensure_output_dirs(config: CrawlConfig) -> None:
    for path in (
        config.discovery_dir,
        config.raw_dir,
        config.processed_dir,
        config.assets_dir,
        config.reports_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
