import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sou_crawler.archive import archive_snapshot_topics, download_snapshot_assets
from sou_crawler.config import CrawlSettings
from sou_crawler.fetcher import FetchResult
from sou_crawler.storage import write_json, write_jsonl


class ArchiveSnapshotTests(unittest.TestCase):
    def test_copies_snapshot_topics_and_preserves_existing_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            source_dir = settings.site_dir / "理科" / "数学" / "新增课题"
            source_dir.mkdir(parents=True)
            (source_dir / "details.json").write_text('{"id":"new"}', encoding="utf-8")
            write_jsonl(
                settings.processed_dir / "projects.jsonl",
                [{"id": "new", "title": "新增课题", "category": "理科", "direction": "数学"}],
            )
            write_json(
                settings.raw_dir / "details" / "refresh_20260902" / "harbour_topics" / "new.json",
                {"request": {"identifier": "new"}},
            )
            target = Path(tmp) / "archive"

            first = archive_snapshot_topics(settings, snapshot_id="20260902", target_dir=target)
            copied = target / "理科" / "数学" / "新增课题" / "details.json"
            second = archive_snapshot_topics(settings, snapshot_id="20260902", target_dir=target)
            copied_exists = copied.exists()

        self.assertEqual(first["topics"], 1)
        self.assertEqual(first["copied"], 1)
        self.assertTrue(copied_exists)
        self.assertEqual(second["copied"], 0)
        self.assertEqual(second["skipped_existing"], 1)

    def test_rejects_a_destination_inside_site_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            (settings.raw_dir / "details" / "refresh_20260902" / "harbour_topics").mkdir(parents=True)

            with self.assertRaises(ValueError):
                archive_snapshot_topics(settings, snapshot_id="20260902", target_dir=settings.site_dir / "nested")

    def test_downloads_assets_only_for_snapshot_topics(self) -> None:
        class FakeFetcher:
            downloads: list[str] = []

            def __init__(self, _settings: CrawlSettings):
                pass

            async def __aenter__(self) -> "FakeFetcher":
                return self

            async def __aexit__(self, *_args: object) -> None:
                return None

            async def download(self, url: str) -> FetchResult:
                type(self).downloads.append(url)
                return FetchResult(url, "GET", 200, {}, None, None, b"public asset")

        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            write_jsonl(
                settings.processed_dir / "projects.jsonl",
                [
                    {"id": "new", "title": "新增", "category": "理科", "direction": "数学", "source_url": "https://jf.cas-harbour.cn/list", "raw": {"pdf": "https://jf.cas-harbour.cn/new.pdf"}},
                    {"id": "old", "title": "历史", "category": "理科", "direction": "数学", "source_url": "https://jf.cas-harbour.cn/list", "raw": {"pdf": "https://jf.cas-harbour.cn/old.pdf"}},
                ],
            )
            write_json(
                settings.raw_dir / "details" / "refresh_20260902" / "harbour_topics" / "new.json",
                {"request": {"identifier": "new"}},
            )

            with patch("sou_crawler.pipeline.AsyncFetcher", FakeFetcher):
                stats = asyncio.run(download_snapshot_assets(settings, snapshot_id="20260902"))

        self.assertEqual(FakeFetcher.downloads, ["https://jf.cas-harbour.cn/new.pdf"])
        self.assertEqual(stats["snapshot_topics"], 1)
        self.assertEqual(stats["downloaded"], 1)

    def test_download_uses_full_archive_directory_mapping_for_duplicate_titles(self) -> None:
        class FakeFetcher:
            def __init__(self, _settings: CrawlSettings):
                pass

            async def __aenter__(self) -> "FakeFetcher":
                return self

            async def __aexit__(self, *_args: object) -> None:
                return None

            async def download(self, url: str) -> FetchResult:
                return FetchResult(url, "GET", 200, {}, None, None, b"public asset")

        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            write_jsonl(
                settings.processed_dir / "projects.jsonl",
                [
                    {"id": "new", "title": "同名课题", "category": "理科", "direction": "数学", "source_url": "https://jf.cas-harbour.cn/list", "raw": {"pdf": "https://jf.cas-harbour.cn/new.pdf"}},
                    {"id": "old", "title": "同名课题", "category": "理科", "direction": "数学", "source_url": "https://jf.cas-harbour.cn/list", "raw": {}},
                ],
            )
            write_json(
                settings.raw_dir / "details" / "refresh_20260902" / "harbour_topics" / "new.json",
                {"request": {"identifier": "new"}},
            )

            with patch("sou_crawler.pipeline.AsyncFetcher", FakeFetcher):
                asyncio.run(download_snapshot_assets(settings, snapshot_id="20260902"))

            expected = settings.site_dir / "理科" / "数学" / "同名课题__new" / "pdf.pdf"
            unexpected = settings.site_dir / "理科" / "数学" / "同名课题" / "pdf.pdf"
            expected_exists = expected.exists()
            unexpected_exists = unexpected.exists()

        self.assertTrue(expected_exists)
        self.assertFalse(unexpected_exists)
