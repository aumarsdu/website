from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_USER_AGENT = "AuthorizedResearchCrawler/1.0"

DEFAULT_ENTRY_URLS = [
    "https://jf.cas-harbour.cn/avocado/#/",
    "https://jf.cas-harbour.cn/mini/#/pages/topic/topic",
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
]

AUTHORIZED_DOMAINS = {
    "gec-api.gecacademy.cn",
    "sou-tools.gecacademy.cn",
    "jf.cas-harbour.cn",
}

LIST_KEYWORDS = {
    "list",
    "project",
    "course",
    "search",
    "topic",
    "page",
    "records",
    "rows",
    "sou",
}

DETAIL_KEYWORDS = {
    "detail",
    "info",
    "project",
    "course",
    "topic",
    "share",
}

CATEGORY_KEYWORDS = {
    "category",
    "classify",
    "level",
    "subject",
    "filter",
    "option",
}

ID_KEYS = ("id", "uuid", "projectId", "courseId", "topicId", "itemId")
PAGE_KEYS = ("page", "pageNo", "pageNum", "current", "currentPage")
PAGE_SIZE_KEYS = ("pageSize", "size", "limit", "rows")

TEXT_FIELD_HINTS = (
    "title",
    "name",
    "teacher",
    "instructor",
    "professor",
    "university",
    "major",
    "prerequisite",
    "intro",
    "description",
)

ASSET_FIELD_HINTS = (
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "webp",
    "poster",
    "cover",
    "avatar",
    "head",
    "image",
    "img",
    "file",
    "url",
    "syllabus",
)

PUBLIC_ASSET_HOST_MARKERS = (
    "aliyuncs.com",
    "oss-",
)


@dataclass(frozen=True)
class CrawlSettings:
    output_dir: Path = Path("output")
    user_agent: str = DEFAULT_USER_AGENT
    rate_limit: float = 1.5
    timeout: float = 20.0
    retries: int = 2
    concurrency: int = 2
    max_pages: int = 20
    max_assets: int | None = None
    allowed_domains: set[str] = field(default_factory=lambda: set(AUTHORIZED_DOMAINS))
    skipped_asset_hosts: set[str] = field(default_factory=set)

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


def ensure_output_dirs(settings: CrawlSettings) -> None:
    for path in (
        settings.discovery_dir,
        settings.raw_dir / "lists",
        settings.raw_dir / "details",
        settings.processed_dir,
        settings.assets_dir,
        settings.reports_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
