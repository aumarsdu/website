import tempfile
import unittest
from pathlib import Path

from sou_crawler.audit import audit_archive, audit_summary
from sou_crawler.config import CrawlSettings
from sou_crawler.refresh import HARBOUR_TOPIC_LIST_URL
from sou_crawler.storage import read_json, write_json, write_jsonl


class AuditTests(unittest.TestCase):
    def test_audit_reports_scope_coverage_and_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            in_scope = {
                "id": "topic-1",
                "title": "课题一",
                "source_url": HARBOUR_TOPIC_LIST_URL,
                "category": "计算机",
                "direction": "人工智能",
                "raw": {"id": "topic-1", "name": "课题一"},
            }
            out_of_scope = {
                "id": "gec-1",
                "title": "范围外课题",
                "source_url": "https://gec-api.gecacademy.cn/course/list",
                "category": "计算机",
                "direction": "人工智能",
                "raw": {"id": "gec-1", "name": "范围外课题"},
            }
            write_jsonl(settings.processed_dir / "projects.jsonl", [in_scope, out_of_scope])
            write_json(
                settings.site_dir / "计算机" / "人工智能" / "课题一" / "details.json",
                in_scope,
            )
            write_json(
                settings.site_dir / "计算机" / "人工智能" / "范围外课题" / "details.json",
                out_of_scope,
            )
            write_json(
                settings.raw_dir / "lists" / "refresh_20260730" / "harbour_topics" / "page_0001.json",
                {"data": {"result": {"records": [{"id": "topic-1", "name": "课题一"}]}}},
            )
            write_json(settings.raw_dir / "lists" / "legacy.json", {"request": {"url": "https://gec-api.gecacademy.cn/course/list"}})
            (settings.assets_dir / "计算机" / "范围外课题").mkdir(parents=True)

            report = audit_archive(settings, snapshot_id="20260730")
            manifest = read_json(settings.reports_dir / "scope_audit_20260730_out_of_scope.json")

        self.assertEqual(report["records"], {"total": 2, "in_scope": 1, "out_of_scope": 1})
        self.assertEqual(report["current_public_list"]["missing_from_archive"], [])
        self.assertEqual(report["site"]["correctly_placed"], 1)
        self.assertEqual(report["out_of_scope"]["site_topic_directories"], 1)
        self.assertEqual(report["out_of_scope"]["raw_files"], 1)
        self.assertEqual(report["out_of_scope"]["legacy_asset_directories"], 1)
        self.assertEqual(manifest["out_of_scope_records"][0]["id"], "gec-1")
        self.assertEqual(audit_summary(report)["current_public_list"]["missing_from_archive"], 0)

    def test_audit_survives_corrupt_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            in_scope = {
                "id": "topic-1",
                "title": "课题一",
                "source_url": HARBOUR_TOPIC_LIST_URL,
                "category": "计算机",
                "direction": "人工智能",
                "raw": {"id": "topic-1", "name": "课题一"},
            }
            write_jsonl(settings.processed_dir / "projects.jsonl", [in_scope])
            write_json(
                settings.site_dir / "计算机" / "人工智能" / "课题一" / "details.json",
                in_scope,
            )
            corrupt_detail = settings.site_dir / "计算机" / "人工智能" / "坏文件" / "details.json"
            corrupt_detail.parent.mkdir(parents=True)
            corrupt_detail.write_text("{not valid json", encoding="utf-8")
            write_json(
                settings.raw_dir / "lists" / "refresh_20260730" / "harbour_topics" / "page_0001.json",
                {"data": {"result": {"records": [{"id": "topic-1", "name": "课题一"}]}}},
            )
            (settings.raw_dir / "lists").mkdir(parents=True, exist_ok=True)
            (settings.raw_dir / "lists" / "broken.json").write_text("]\xff[", encoding="utf-8")

            report = audit_archive(settings, snapshot_id="20260730")

        self.assertEqual(report["site"]["unreadable_detail_paths"], ["计算机/人工智能/坏文件/details.json"])
        self.assertEqual(report["out_of_scope"]["unreadable_raw_files"], 1)
        self.assertEqual(report["out_of_scope"]["raw_files"], 0)
        self.assertEqual(report["site"]["correctly_placed"], 1)
        self.assertEqual(audit_summary(report)["site"]["unreadable_detail_paths"], 1)


if __name__ == "__main__":
    unittest.main()
