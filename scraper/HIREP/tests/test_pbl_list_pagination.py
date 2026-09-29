import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from sou_crawler.config import Settings
from sou_crawler import pbl_crawler


class _FakeListFetcher:
    def __init__(self, pages):
        self._pages = pages
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def request_json(self, method, url, json=None, headers=None):
        self.calls.append(dict(json or {}))
        return self._pages[min(len(self.calls) - 1, len(self._pages) - 1)]


class FetchListPaginationTest(unittest.TestCase):
    def _response(self, records, pages):
        return {
            "data": {
                "courseList": {
                    "current": "1",
                    "pages": str(pages),
                    "size": "200",
                    "total": "999",
                    "records": records,
                }
            },
            "status": 200,
            "success": True,
        }

    def _run_fetch_list(self, fake):
        with TemporaryDirectory() as tmp:
            settings = Settings(output_dir=Path(tmp) / "out")
            with mock.patch("sou_crawler.pbl_crawler.HttpFetcher", lambda _settings: fake):
                data = asyncio.run(pbl_crawler._fetch_list(settings, force_refresh=True))
            saved = json.loads((settings.raw_dir / "pbl_ais_cis_page.json").read_text())
        return data, saved

    def test_fetch_list_merges_all_pages(self):
        page1 = self._response([{"courseExtendId": "a"}, {"courseExtendId": "b"}], 2)
        page2 = self._response([{"courseExtendId": "c"}], 2)
        fake = _FakeListFetcher([page1, page2])

        data, saved = self._run_fetch_list(fake)

        records = pbl_crawler._records_from_response(data)
        self.assertEqual([r["courseExtendId"] for r in records], ["a", "b", "c"])
        self.assertEqual(
            fake.calls,
            [{"pageSize": 200, "current": 1}, {"pageSize": 200, "current": 2}],
        )
        self.assertEqual(len(saved["data"]["courseList"]["records"]), 3)
        self.assertEqual(saved["data"]["courseList"]["size"], "3")

    def test_fetch_list_stops_when_server_ignores_current_then_falls_back(self):
        page = self._response([{"courseExtendId": "a"}, {"courseExtendId": "b"}], 3)
        fake = _FakeListFetcher([page])

        data, _saved = self._run_fetch_list(fake)

        records = pbl_crawler._records_from_response(data)
        self.assertEqual([r["courseExtendId"] for r in records], ["a", "b"])
        # 第 1、2 页 + 回退单请求，共 3 次调用；回退无增益时保留原结果
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(fake.calls[-1]["pageSize"], 999)  # total=999 回退上限内

    def test_fetch_list_fallback_recovers_full_list_when_server_ignores_current(self):
        # 页 1/2 与页 2 相同（服务端忽略 current），但单请求大 pageSize 能拿全量
        page = self._response([{"courseExtendId": "a"}, {"courseExtendId": "b"}], 3)
        full = self._response(
            [{"courseExtendId": c} for c in ("a", "b", "c", "d", "e")], 1
        )
        fake = _FakeListFetcher([page, page, full])

        data, saved = self._run_fetch_list(fake)

        records = pbl_crawler._records_from_response(data)
        self.assertEqual([r["courseExtendId"] for r in records], ["a", "b", "c", "d", "e"])
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(len(saved["data"]["courseList"]["records"]), 5)


if __name__ == "__main__":
    unittest.main()
