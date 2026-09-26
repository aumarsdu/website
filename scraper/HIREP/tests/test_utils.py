from sou_crawler.scheduler import UrlDeduper
from sou_crawler.utils import canonicalize_url, extract_records, find_asset_urls, safe_filename
from sou_crawler.config import Settings
import unittest


class UtilsTest(unittest.TestCase):
    def test_canonicalize_url_sorts_query_params(self):
        self.assertEqual(canonicalize_url("HTTPS://Example.COM/path?b=2&a=1"), "https://example.com/path?a=1&b=2")

    def test_deduper_uses_canonical_url(self):
        deduper = UrlDeduper()
        self.assertTrue(deduper.add("https://example.com/path?b=2&a=1"))
        self.assertFalse(deduper.add("https://example.com/path?a=1&b=2"))

    def test_extract_records_from_common_shapes(self):
        payload = {"data": {"records": [{"id": 1, "title": "A"}], "total": 1}}
        self.assertEqual(extract_records(payload), [{"id": 1, "title": "A"}])

    def test_find_asset_urls(self):
        payload = {"poster": "https://cdn.example.com/a/b/poster.jpg?x=1", "doc": "https://cdn.example.com/file.pdf"}
        self.assertEqual(
            find_asset_urls(payload),
            [
                "https://cdn.example.com/a/b/poster.jpg?x=1",
                "https://cdn.example.com/file.pdf",
            ],
        )

    def test_safe_filename_removes_invalid_chars(self):
        self.assertEqual(safe_filename("A/B:C*D?"), "A_B_C_D_")

    def test_asset_host_allowlist_rejects_unknown_https(self):
        settings = Settings()
        self.assertTrue(settings.is_allowed_url("https://cdn.aliyuncs.com/a.pdf", allow_assets=True))
        self.assertFalse(settings.is_allowed_url("https://tracker.example.net/a.pdf", allow_assets=True))


if __name__ == "__main__":
    unittest.main()
