import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sou_crawler.config import Settings
from sou_crawler.pbl_crawler import _fetch_list


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def request_json(self, _method, _url, json=None, **_kwargs):
        self.calls.append(json)
        return self.pages[min(len(self.calls) - 1, len(self.pages) - 1)]


def response(ids, pages=2):
    return {"data": {"courseList": {"pages": pages, "total": 400,
            "records": [{"courseExtendId": value} for value in ids]}}}


class PaginationRepairTests(unittest.TestCase):
    def run_fetch(self, fake, max_pages=100):
        with TemporaryDirectory() as tmp:
            settings = Settings(output_dir=Path(tmp), max_pages=max_pages)
            with patch("sou_crawler.pbl_crawler.HttpFetcher", return_value=fake):
                return asyncio.run(_fetch_list(settings, force_refresh=True))

    def test_official_page_index_merges_distinct_pages(self):
        fake = FakeFetcher([response(["a"]), response(["b"])])
        result = self.run_fetch(fake)
        self.assertEqual(fake.calls, [{"pageSize": 200, "pageIndex": 1},
                                      {"pageSize": 200, "pageIndex": 2}])
        self.assertEqual(len(result["data"]["courseList"]["records"]), 2)

    def test_duplicate_page_stops_without_fallback(self):
        fake = FakeFetcher([response(["a"])])
        with self.assertRaisesRegex(RuntimeError, "duplicate page"):
            self.run_fetch(fake)
        self.assertEqual(len(fake.calls), 2)
        self.assertTrue(all(call["pageSize"] == 200 for call in fake.calls))

    def test_hard_page_cap_rejects_partial_list(self):
        fake = FakeFetcher([response(["a"])])
        with self.assertRaisesRegex(RuntimeError, "max-pages"):
            self.run_fetch(fake, max_pages=1)
        self.assertEqual(len(fake.calls), 1)
