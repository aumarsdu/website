import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.reorganize_pbl_outputs import desired_asset_path, migrate_output, project_folder, with_project_directories


class ReorganizePblOutputsTest(unittest.TestCase):
    def test_project_folder_uses_category_direction_title(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output_pbl"
            project = {
                "category": "计算机与人工智能",
                "direction": "深度学习",
                "title": "课题 A",
            }

            self.assertEqual(
                project_folder(output_dir, project),
                output_dir / "assets" / "计算机与人工智能" / "深度学习" / "课题 A",
            )

    def test_desired_asset_path_uses_semantic_names(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output_pbl"
            source = output_dir / "assets" / "旧目录" / "old.pdf"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"pdf")
            project = {
                "category": "计算机与人工智能",
                "direction": "深度学习",
                "title": "课题 A",
                "direct_assets": [
                    {
                        "field": "majorAttachment",
                        "file_name": "论文材料.pdf",
                        "url": "https://example.com/file.pdf",
                    }
                ],
            }
            item = {"field": "majorAttachment", "source_url": "https://example.com/file.pdf"}

            path = desired_asset_path(output_dir, project, item, source)

            self.assertEqual(path.name, "论文材料.pdf")
            self.assertIn("计算机与人工智能/深度学习/课题 A", str(path))

    def test_migrate_output_writes_detail_and_relocated_manifest(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output_pbl"
            processed = output_dir / "processed"
            processed.mkdir(parents=True)
            source = output_dir / "assets" / "商科" / "课题 A" / "课题 A.jpg"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"poster")
            project = {
                "business_id": "ce-1",
                "category": "计算机与人工智能",
                "direction": "深度学习",
                "title": "课题 A",
                "raw": {"detail": {"courseNameCn": "课题 A"}},
            }
            (processed / "projects.jsonl").write_text(json.dumps(project, ensure_ascii=False) + "\n", encoding="utf-8")
            manifest = {
                "manifest_key": "ce-1::att-1::attachmentId",
                "record_title": "课题 A",
                "field": "attachmentId",
                "source_url": "https://example.com/poster.jpg",
                "file": str(source),
            }
            (processed / "asset_manifest.jsonl").write_text(json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8")

            stats = migrate_output(output_dir)

            new_file = output_dir / "assets" / "计算机与人工智能" / "深度学习" / "课题 A" / "海报.jpg"
            detail_file = new_file.parent / "详情页信息.json"
            self.assertEqual(stats["assets_linked_or_copied"], 1)
            self.assertTrue(new_file.exists())
            self.assertTrue(detail_file.exists())
            self.assertIn('"project_dir"', (processed / "projects.jsonl").read_text(encoding="utf-8"))

    def test_with_project_directories_disambiguates_duplicate_topic_paths(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output_pbl"
            projects = [
                {"business_id": "ce-1", "category": "商科", "direction": "金融学", "title": "课题 A"},
                {"business_id": "ce-2", "category": "商科", "direction": "金融学", "title": "课题 A"},
            ]

            migrated = with_project_directories(output_dir, projects)

            self.assertTrue(migrated[0]["project_dir"].endswith("课题 A__ce-1"))
            self.assertTrue(migrated[1]["project_dir"].endswith("课题 A__ce-2"))


if __name__ == "__main__":
    unittest.main()
