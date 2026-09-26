import tempfile
import unittest
from pathlib import Path

from sou_crawler.audit import audit_archive
from sou_crawler.cleanup import cleanup_out_of_scope
from sou_crawler.config import CrawlSettings
from sou_crawler.refresh import HARBOUR_TOPIC_LIST_URL
from sou_crawler.storage import write_json, write_jsonl


class CleanupTests(unittest.TestCase):
    def test_cleanup_removes_only_manifested_out_of_scope_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            in_scope = {"id": "topic-1", "title": "课题一", "source_url": HARBOUR_TOPIC_LIST_URL, "category": "计算机", "direction": "人工智能", "raw": {"id": "topic-1"}}
            out_of_scope = {"id": "other-1", "title": "范围外课题", "source_url": "https://example.com/topics", "category": "计算机", "direction": "人工智能", "raw": {"id": "other-1"}}
            write_jsonl(settings.processed_dir / "projects.jsonl", [in_scope, out_of_scope])
            write_json(settings.site_dir / "计算机" / "人工智能" / "课题一" / "details.json", in_scope)
            write_json(settings.site_dir / "计算机" / "人工智能" / "范围外课题" / "details.json", out_of_scope)
            write_json(settings.raw_dir / "lists" / "refresh_20260730" / "harbour_topics" / "page_0001.json", {"data": {"result": {"records": [{"id": "topic-1"}]}}})
            out_raw = settings.raw_dir / "lists" / "legacy.json"
            write_json(out_raw, {"request": {"url": "https://example.com/topics"}})
            legacy_asset = settings.assets_dir / "计算机" / "范围外课题"
            legacy_asset.mkdir(parents=True)
            (legacy_asset / "poster.jpg").write_bytes(b"image")
            audit_archive(settings, snapshot_id="20260730")

            stats = cleanup_out_of_scope(settings, snapshot_id="20260730")

            self.assertEqual(stats["records_removed"], 1)
            self.assertEqual(stats["site_directories_removed"], 1)
            self.assertEqual(stats["raw_files_removed"], 1)
            self.assertEqual(stats["legacy_asset_directories_removed"], 1)
            self.assertTrue((settings.site_dir / "计算机" / "人工智能" / "课题一" / "details.json").exists())
            self.assertFalse((settings.site_dir / "计算机" / "人工智能" / "范围外课题").exists())
            self.assertFalse(out_raw.exists())
            self.assertFalse(legacy_asset.exists())
            self.assertEqual((settings.processed_dir / "projects.jsonl").read_text(encoding="utf-8").count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
