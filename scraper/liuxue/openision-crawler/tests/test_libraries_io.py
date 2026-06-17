from pathlib import Path
import tempfile
import unittest

from openision_crawler.libraries.io import read_jsonl, write_jsonl, contains_sensitive_key


class LibraryIoTests(unittest.TestCase):
    def test_write_jsonl_creates_parent_and_sorts_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "out.jsonl"
            write_jsonl(path, [{"b": 2, "a": 1}])
            self.assertEqual(path.read_text(encoding="utf-8"), '{"a":1,"b":2}\n')

    def test_read_jsonl_skips_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "in.jsonl"
            path.write_text('{"id":"1"}\n\n{"id":"2"}\n', encoding="utf-8")
            self.assertEqual(read_jsonl(path), [{"id": "1"}, {"id": "2"}])

    def test_contains_sensitive_key_detects_nested_keys(self) -> None:
        row = {"headers": {"FCAuthorization": "secret"}}
        self.assertTrue(contains_sensitive_key(row))
        self.assertFalse(contains_sensitive_key({"id": "1", "name": "ok"}))


if __name__ == "__main__":
    unittest.main()
