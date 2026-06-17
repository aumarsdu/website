import tempfile
import unittest
from pathlib import Path

from caoliao_archiver.storage import ArchiveStorage


class StorageTests(unittest.TestCase):
    def test_write_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = ArchiveStorage(Path(tmp))
            path = storage.write_jsonl("records/items.jsonl", [{"a": 1}, {"b": 2}])
            self.assertEqual(
                path.read_text(encoding="utf-8").splitlines(),
                ['{"a": 1}', '{"b": 2}'],
            )

    def test_asset_path_for_uses_hash_and_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = ArchiveStorage(Path(tmp))
            path = storage.asset_path_for("https://example.com/file", b"abc", "application/pdf")
            self.assertTrue(path.startswith("assets/files/"))
            self.assertTrue(path.endswith(".pdf"))

    def test_external_page_path_for_uses_separate_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = ArchiveStorage(Path(tmp))
            path = storage.external_page_path_for("https://example.com/path/page")
            self.assertTrue(path.startswith("external_pages/"))
            self.assertIn("example.com", path)
            self.assertTrue(path.endswith(".html"))


if __name__ == "__main__":
    unittest.main()
