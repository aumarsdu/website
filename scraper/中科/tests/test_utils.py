import unittest

from sou_crawler.utils import headers_have_auth_indicator, is_public_asset_url, query_params, redact_headers, redact_obj, slugify, with_query_params


class UtilsTests(unittest.TestCase):
    def test_redact_headers_hides_sensitive_values(self) -> None:
        headers, had_sensitive = redact_headers({"cookie": "abc", "accept": "json"})

        self.assertTrue(had_sensitive)
        self.assertTrue(headers["cookie"].startswith("<redacted"))
        self.assertEqual(headers["accept"], "json")

    def test_redact_obj_recurses(self) -> None:
        self.assertTrue(redact_obj({"nested": {"accessToken": "secret"}})["nested"]["accessToken"].startswith("<redacted"))

    def test_query_param_helpers(self) -> None:
        url = with_query_params("https://example.com/api?a=1", {"page": 2})

        self.assertEqual(query_params(url), {"a": "1", "page": "2"})

    def test_slugify_preserves_chinese_and_removes_path_chars(self) -> None:
        self.assertEqual(slugify("计算机/人工智能:*"), "计算机 人工智能")

    def test_cookie_is_not_auth_indicator_but_authorization_is(self) -> None:
        self.assertFalse(headers_have_auth_indicator({"cookie": "abc"}))
        self.assertTrue(headers_have_auth_indicator({"authorization": "Bearer x"}))

    def test_public_asset_url_detection(self) -> None:
        self.assertTrue(is_public_asset_url("https://bucket.oss-cn-shanghai.aliyuncs.com/a.pdf"))
        self.assertTrue(is_public_asset_url("https://cdn.example.com/a.webp"))


if __name__ == "__main__":
    unittest.main()
