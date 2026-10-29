from pathlib import Path
import tempfile
import unittest

from sou_crawler.storage import read_jsonl, write_csv, write_jsonl


class StorageTests(unittest.TestCase):
    def test_jsonl_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            rows = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]

            self.assertEqual(write_jsonl(path, rows), 2)
            self.assertEqual(read_jsonl(path), rows)

    def test_write_csv_handles_nested_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.csv"
            rows = [{"id": "1", "raw": {"a": 1}}]

            self.assertEqual(write_csv(path, rows), 1)
            self.assertIn("raw", path.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
