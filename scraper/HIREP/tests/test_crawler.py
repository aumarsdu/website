import unittest
from argparse import Namespace

from sou_crawler.config import load_settings
from sou_crawler.crawler import _build_followup_request, _iter_paginated_requests, _safe_request_headers, _should_continue
from sou_crawler.schema import CrawlStats


class CrawlerTest(unittest.TestCase):
    def test_iter_paginated_requests_updates_nested_json_page_fields(self):
        target = {
            "method": "POST",
            "url": "https://edu4-crm-api.neoschool.com/sdm/mtc/pubController/pageV2",
            "json": {"args": {"page": 1, "limit": 20}},
            "pagination": {
                "page_param": "page",
                "page_size_param": "limit",
                "page_size": 50,
                "start_page": 2,
            },
        }
        requests = _iter_paginated_requests(target, 2)
        self.assertEqual(requests[0]["json"]["args"]["page"], 2)
        self.assertEqual(requests[0]["json"]["args"]["limit"], 50)
        self.assertEqual(requests[1]["json"]["args"]["page"], 3)

    def test_should_continue_stops_on_short_page(self):
        spec = {"_page_size": 20}
        records = [{"id": 1}]
        self.assertFalse(_should_continue({"data": {"courseList": records}}, records, spec))

    def test_safe_request_headers_drops_sensitive_headers(self):
        headers = _safe_request_headers({"Content-Type": "application/json", "Authorization": "secret", "Cookie": "secret"})
        self.assertEqual(headers, {"Content-Type": "application/json"})

    def test_build_followup_request_can_use_parent_data_scalar(self):
        spec = _build_followup_request(
            {
                "method": "POST",
                "url": "https://edu4-crm-api.neoschool.com/bus/ath/resAttachment/noToken/getResAttachment",
                "params": {"id": "{data}"},
            },
            {},
            {"data": "2038901939158851585", "success": True},
        )
        self.assertEqual(spec["params"]["id"], "2038901939158851585")

    def test_load_settings_disables_environment_proxy_by_default(self):
        settings = load_settings(Namespace())

        self.assertFalse(settings.trust_env)

    def test_crawl_stats_include_finished_at(self):
        payload = CrawlStats(started_at="2026-07-30T00:00:00+00:00").as_dict()

        self.assertEqual(payload["started_at"], "2026-07-30T00:00:00+00:00")
        self.assertIn("T", payload["finished_at"])


if __name__ == "__main__":
    unittest.main()
