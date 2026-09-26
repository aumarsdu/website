import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sou_crawler.config import CrawlSettings
from sou_crawler.fetcher import FetchResult
from sou_crawler.refresh import (
    HARBOUR_TOPIC_CATEGORY_URL,
    HARBOUR_TOPIC_DETAIL_URL,
    HARBOUR_TOPIC_LIST_URL,
    PublicListSource,
    backfill_harbour_details,
    collect_list_source,
    refresh_public_topics,
)
from sou_crawler.storage import write_json, write_jsonl


class FakeFetcher:
    requests: list[dict[str, object]] = []

    def __init__(self, _settings: CrawlSettings):
        pass

    async def __aenter__(self) -> "FakeFetcher":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def request(self, method: str, url: str, *, params=None, json_body=None, **_kwargs) -> FetchResult:
        type(self).requests.append({"method": method, "url": url, "params": params, "json_body": json_body})
        if url == HARBOUR_TOPIC_CATEGORY_URL:
            data = {"result": [{"name": "计算机", "child": [{"name": "人工智能"}]}]}
        elif url == HARBOUR_TOPIC_LIST_URL:
            data = {"result": {"records": [{"id": "known", "name": "既有课题"}, {"id": "new-topic", "name": "新增课题"}], "pages": 1}}
        elif url == f"{HARBOUR_TOPIC_DETAIL_URL}/new-topic":
            data = {"data": {"id": "new-topic", "name": "新增课题", "courseIntroduction": "完整详情"}}
        else:  # pragma: no cover - keeps unexpected endpoint calls visible
            raise AssertionError(f"unexpected request: {method} {url}")
        return FetchResult(url, method, 200, {}, data, None)


class RefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeFetcher.requests = []

    def test_refresh_snapshots_public_sources_and_uses_json_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output", max_pages=3, max_details=10)
            write_jsonl(
                settings.processed_dir / "projects.jsonl",
                [{"id": "known", "source_url": HARBOUR_TOPIC_LIST_URL, "title": "既有课题"}],
            )
            with patch("sou_crawler.refresh.AsyncFetcher", FakeFetcher):
                stats = asyncio.run(refresh_public_topics(settings, snapshot_id="20260730"))

            snapshot = settings.raw_dir / "lists" / "refresh_20260730"
            detail = settings.raw_dir / "details" / "refresh_20260730" / "harbour_topics" / "new-topic.json"
            report = settings.reports_dir / "refresh_20260730.json"

            self.assertTrue((snapshot / "harbour_topics" / "page_0001.json").exists())
            self.assertTrue((settings.raw_dir / "taxonomy" / "refresh_20260730" / "harbour_topic_category.json").exists())
            self.assertTrue(detail.exists())
            self.assertTrue(report.exists())
            self.assertEqual(stats["new_records"], {"harbour_topics": 1})
            self.assertEqual(stats["details"]["succeeded"], 1)

    def test_dry_run_does_not_request_or_create_a_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            result = asyncio.run(refresh_public_topics(settings, snapshot_id="20260730", dry_run=True))

            self.assertTrue(result["dry_run"])
            self.assertEqual(FakeFetcher.requests, [])
            self.assertFalse((settings.raw_dir / "lists" / "refresh_20260730").exists())

    def test_refresh_rejects_an_existing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            (settings.raw_dir / "lists" / "refresh_20260730").mkdir(parents=True)

            with self.assertRaises(FileExistsError):
                asyncio.run(refresh_public_topics(settings, snapshot_id="20260730"))

    def test_backfill_resumes_only_missing_public_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output", max_details=10)
            list_path = settings.raw_dir / "lists" / "refresh_20260730" / "harbour_topics" / "page_0001.json"
            write_json(
                list_path,
                {
                    "request": {"url": HARBOUR_TOPIC_LIST_URL},
                    "data": {"result": {"records": [{"id": "known"}, {"id": "new-topic"}]}},
                },
            )
            write_json(
                settings.raw_dir / "details" / "refresh_previous" / "harbour_topics" / "known.json",
                {
                    "request": {"url": f"{HARBOUR_TOPIC_DETAIL_URL}/known"},
                    "data": {"data": {"id": "known", "name": "既有详情"}},
                },
            )

            with patch("sou_crawler.refresh.AsyncFetcher", FakeFetcher):
                stats = asyncio.run(backfill_harbour_details(settings, snapshot_id="20260730"))

            backfill_path = settings.raw_dir / "details" / "backfill_20260730" / "harbour_topics" / "new-topic.json"
            self.assertTrue(backfill_path.exists())
            self.assertEqual(stats["missing_before"], 1)
            self.assertEqual(stats["succeeded"], 1)
            self.assertEqual(stats["remaining_after"], 0)
            self.assertEqual([request["url"] for request in FakeFetcher.requests], [f"{HARBOUR_TOPIC_DETAIL_URL}/new-topic"])

    def test_duplicate_page_payload_is_reported_as_incomplete(self) -> None:
        class DuplicatePageFetcher:
            async def request(self, method: str, url: str, **_kwargs) -> FetchResult:
                return FetchResult(url, method, 200, {}, {"data": {"records": [{"id": "same"}], "pages": 2}}, None)

        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output", max_pages=2)
            source = PublicListSource("test", "https://jf.cas-harbour.cn/test", "GET", "page", "limit", 100)
            _items, stats = asyncio.run(
                collect_list_source(DuplicatePageFetcher(), source, settings, settings.raw_dir / "lists" / "test", "20260730")
            )

        self.assertEqual(stats["failed"], 1)
        self.assertTrue(stats["truncated"])
        self.assertEqual(stats["errors"], {"duplicate_page_payload": 1})


if __name__ == "__main__":
    unittest.main()
