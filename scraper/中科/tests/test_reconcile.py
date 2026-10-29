import tempfile
import unittest
from pathlib import Path

from sou_crawler.config import CrawlSettings
from sou_crawler.reconcile import reconcile_site_layout
from sou_crawler.refresh import HARBOUR_TOPIC_LIST_URL
from sou_crawler.storage import write_json, write_jsonl


class ReconcileTests(unittest.TestCase):
    def test_reconcile_preserves_missing_assets_before_removing_old_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            stale = {"id": "stale", "title": "同名课题", "source_url": HARBOUR_TOPIC_LIST_URL, "category": "计算机", "direction": "人工智能", "raw": {"id": "stale"}}
            current = {"id": "current", "title": "同名课题", "source_url": HARBOUR_TOPIC_LIST_URL, "category": "计算机", "direction": "人工智能", "raw": {"id": "current"}}
            write_jsonl(settings.processed_dir / "projects.jsonl", [stale, current])
            old_dir = settings.site_dir / "计算机" / "人工智能" / "同名课题"
            expected_dir = settings.site_dir / "计算机" / "人工智能" / "同名课题__stale"
            write_json(old_dir / "details.json", stale)
            (old_dir / "poster.jpg").write_bytes(b"poster")
            write_json(expected_dir / "details.json", stale)

            stats = reconcile_site_layout(settings)

            self.assertEqual(stats["moved"], 1)
            self.assertEqual(stats["assets_copied"], 1)
            self.assertFalse(old_dir.exists())
            self.assertEqual((expected_dir / "poster.jpg").read_bytes(), b"poster")


if __name__ == "__main__":
    unittest.main()
