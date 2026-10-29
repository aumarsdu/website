from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from openision_crawler.config import load_settings
from openision_crawler.endpoint_summary import read_jsonl, summarize_network
from openision_crawler.html_probe import extract_initial_schools
from openision_crawler.api_crawler import default_case_params, default_major_params, extract_items
from openision_crawler.sanitize import redact_headers, sanitize_json, sanitize_text, sanitize_url, strip_sensitive_query
from openision_crawler.storage import Storage


class CoreTests(unittest.TestCase):
    def test_redact_headers(self) -> None:
        self.assertEqual(
            redact_headers({"Authorization": "secret", "Accept": "json"}),
            {"Authorization": "[REDACTED]", "Accept": "json"},
        )

    def test_sanitize_url_redacts_signed_query(self) -> None:
        url = "https://example.com/a.png?security-token=abc&OSSAccessKeyId=id&Signature=sig&x=1"
        safe = sanitize_url(url)
        self.assertNotIn("abc", safe)
        self.assertNotIn("sig", safe)
        self.assertIn("x=1", safe)
        stripped = strip_sensitive_query(url)
        self.assertNotIn("security-token", stripped.lower())
        self.assertNotIn("Signature", stripped)

    def test_sanitize_text_redacts_nextjs_escaped_signed_query(self) -> None:
        text = "https://example.com/a.png?security-token=abc\\u0026OSSAccessKeyId=id\\u0026Signature=sig"
        safe = sanitize_text(text)
        self.assertNotIn("abc", safe)
        self.assertNotIn("id", safe)
        self.assertNotIn("sig", safe)

    def test_sanitize_text_redacts_json_token_field(self) -> None:
        safe = sanitize_text('{"token":"secret-token-value","msg":"ok"}')
        self.assertNotIn("secret-token-value", safe)
        self.assertIn("[REDACTED]", safe)

    def test_sanitize_json_redacts_sensitive_keys(self) -> None:
        safe = sanitize_json({"token": "secret", "nested": {"AccessKeySecret": "secret2"}, "ok": "yes"})
        self.assertEqual(safe["token"], "[REDACTED]")
        self.assertEqual(safe["nested"]["AccessKeySecret"], "[REDACTED]")
        self.assertEqual(safe["ok"], "yes")

    def test_default_api_params_are_minimal_public_queries(self) -> None:
        self.assertEqual(default_major_params(2, 100)["page"], 2)
        self.assertNotIn("qs_max", default_major_params(1, 100))
        self.assertEqual(default_case_params(1, 100)["search_type"], "keyword")

    def test_extract_items_reads_pagination_shape(self) -> None:
        items, total, page, pages = extract_items({"data": {"items": [{"id": "1"}], "total": 3, "page": 1, "pages": 3}})
        self.assertEqual(items, [{"id": "1"}])
        self.assertEqual(total, 3)
        self.assertEqual(page, 1)
        self.assertEqual(pages, 3)

    def test_simple_config_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = tmp_path / "config"
            config.mkdir()
            (config / "settings.example.yaml").write_text(
                "base_url: https://example.com\nallowed_domains:\n  - example.com\n",
                encoding="utf-8",
            )
            settings = load_settings(tmp_path)
            self.assertEqual(settings.base_url, "https://example.com")
            self.assertEqual(settings.allowed_domains, ("example.com",))

    def test_sqlite_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "data" / "openision.sqlite"
            Storage(db).init_db()
            self.assertTrue(db.exists())

    def test_jsonl_reader_skips_bad_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "network.jsonl"
            path.write_text(
                '{"url":"https://www.openision.com/api","method":"GET","status":200}\nnot-json\n',
                encoding="utf-8",
            )
            rows = read_jsonl(path)
            self.assertEqual(len(rows), 1)

    def test_endpoint_summary_groups_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "network.jsonl"
            path.write_text(
                '{"request_url":"https://www.openision.com/api/items?page=1","method":"GET","status":200,"response_body_sample":"{\\"items\\":[],\\"total\\":0}"}\n',
                encoding="utf-8",
            )
            rows = summarize_network(path)
            self.assertEqual(rows[0]["endpoint"], "GET https://www.openision.com/api/items")
            self.assertEqual(rows[0]["guessed_type"], "list")

    def test_extract_initial_schools(self) -> None:
        raw_html = '<script>self.__next_f.push([1,"\\"initialSchools\\":[{\\"id\\":\\"1\\",\\"name\\":\\"A\\"}]"])</script>'
        rows = extract_initial_schools(raw_html)
        self.assertEqual(rows, [{"id": "1", "name": "A"}])


if __name__ == "__main__":
    unittest.main()
