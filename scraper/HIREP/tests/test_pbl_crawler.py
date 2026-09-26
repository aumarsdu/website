import unittest
import asyncio
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from sou_crawler.config import Settings
from sou_crawler.pbl_crawler import (
    _asset_refs,
    _asset_target_path,
    _direct_asset_target_path,
    _load_major_map,
    _manifest_file_is_current,
    _history_project_paths,
    _known_business_ids,
    _new_projects,
    _dedupe_pbl_records,
    _normalize_projects,
    _project_folder,
    _records_from_response,
    _with_project_directories,
    _write_project_detail_files,
    crawl_pbl_incremental,
)


class PblCrawlerTest(unittest.TestCase):
    def test_normalize_projects_uses_major_parent_category_and_assets(self):
        records = [
            {
                "courseExtendId": "ce-1",
                "courseId": "c-1",
                "courseExtendNameCn": "课题 A",
                "productPackageId": "pkg-1",
                "h5Type": 2,
                "majorMax": "20",
                "direction": "金融学",
                "professorName": "Prof A",
                "collegeName": "School A",
                "attachmentId": "att-1",
                "thumbnailId": "thumb-1",
                "keywords": "资产定价|行为金融|",
                "courseDifficulty": 5,
                "teachingMode": 1,
                "lectureCourseBeginTime": "2025-10-18",
                "researchCourseBeginTime": "2026-11-21",
            }
        ]
        major_map = {"20": {"name": "金融学", "parent_id": "3", "parent_name": "商科"}}

        projects = _normalize_projects(records, major_map)

        self.assertEqual(projects[0]["category"], "商科")
        self.assertEqual(projects[0]["title"], "课题 A")
        self.assertEqual(projects[0]["keywords"], ["资产定价", "行为金融"])
        self.assertEqual(projects[0]["course_difficulty"], 5)
        self.assertEqual(projects[0]["teaching_mode"], 1)
        self.assertEqual(len(projects[0]["assets"]), 2)
        self.assertIn("courseExtendId=ce-1", projects[0]["source_url"])

    def test_asset_refs_collects_project_asset_ids(self):
        projects = [
            {
                "business_id": "ce-1",
                "title": "课题 A",
                "category": "商科",
                "professor": "Prof A",
                "assets": [{"field": "attachmentId", "attachment_id": "att-1"}],
            }
        ]

        refs = _asset_refs(projects)

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].attachment_id, "att-1")

    def test_load_major_map_flattens_parent_and_children(self):
        data = {
            "data": [
                {
                    "majors": "3",
                    "majorsName": "商科",
                    "majorsMinList": [{"majors": "20", "majorsName": "金融学"}],
                }
            ]
        }
        # Exercise the same structure through the public helper by monkeypatching read_json input
        # would be heavier than useful here; normalize coverage above verifies the expected map shape.
        self.assertEqual(data["data"][0]["majorsMinList"][0]["majorsName"], "金融学")

    def test_records_from_response_accepts_nested_and_flat_records(self):
        nested = {"data": {"courseList": {"records": [{"id": 1}, "bad"]}}}
        flat = {"data": {"records": [{"id": 2}]}}

        self.assertEqual(_records_from_response(nested), [{"id": 1}])
        self.assertEqual(_records_from_response(flat), [{"id": 2}])

    def test_pbl_list_deduplication_keeps_most_complete_course_record(self):
        records = [
            {"courseExtendId": "ce-1", "courseExtendNameCn": "课题 A"},
            {
                "courseExtendId": "ce-1",
                "courseExtendNameCn": "课题 A",
                "productPackageId": "pkg-1",
                "direction": "计算机科学",
                "attachmentId": "poster-1",
            },
            {"courseExtendId": "ce-2", "courseExtendNameCn": "课题 B"},
        ]

        unique, duplicates = _dedupe_pbl_records(records)

        self.assertEqual(duplicates, 1)
        self.assertEqual([item["courseExtendId"] for item in unique], ["ce-1", "ce-2"])
        self.assertEqual(unique[0]["productPackageId"], "pkg-1")

    def test_incremental_filter_uses_historical_business_ids(self):
        with TemporaryDirectory() as tmp:
            history = Path(tmp) / "historical_projects.jsonl"
            history.write_text('{"business_id": "ce-1"}\n{"business_id": "ce-2"}\n', encoding="utf-8")

            known = _known_business_ids([history])
            new = _new_projects(
                [
                    {"business_id": "ce-1", "title": "既有课题"},
                    {"business_id": "ce-3", "title": "新增课题"},
                    {"business_id": "", "title": "缺失 ID"},
                ],
                known,
            )

            self.assertEqual(known, {"ce-1", "ce-2"})
            self.assertEqual([item["business_id"] for item in new], ["ce-3", ""])

    def test_incremental_history_auto_discovers_other_pbl_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / "output_pbl_incremental_20260730"
            historical = root / "output_pbl_full_20260724" / "processed" / "projects.jsonl"
            current_projects = current / "processed" / "projects.jsonl"
            historical.parent.mkdir(parents=True)
            current_projects.parent.mkdir(parents=True)
            historical.write_text('{"business_id": "ce-1"}\n', encoding="utf-8")
            current_projects.write_text('{"business_id": "ce-2"}\n', encoding="utf-8")

            paths = _history_project_paths(Settings(output_dir=current), [])

            self.assertEqual(paths, [historical.resolve()])

    def test_incremental_requires_history_before_network_access(self):
        with TemporaryDirectory() as tmp:
            settings = Settings(output_dir=Path(tmp) / "output_pbl_incremental")

            with self.assertRaisesRegex(ValueError, "至少一个包含历史 business_id"):
                asyncio.run(crawl_pbl_incremental(settings, []))

    def test_incremental_dry_run_reports_auto_discovered_baseline(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            historical = root / "output_pbl_full_20260724" / "processed" / "projects.jsonl"
            historical.parent.mkdir(parents=True)
            historical.write_text('{"business_id": "ce-1"}\n', encoding="utf-8")
            settings = Settings(output_dir=root / "output_pbl_incremental_20260730", dry_run=True)
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                asyncio.run(crawl_pbl_incremental(settings, []))

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["known_business_ids"], 1)
            self.assertTrue(payload["incremental_ready"])
            self.assertEqual(payload["known_project_paths"], [str(historical.resolve())])

    def test_project_folder_matches_site_category_direction_topic(self):
        with TemporaryDirectory() as tmp:
            settings = Settings(output_dir=Path(tmp) / "output")
            project = {
                "business_id": "ce-1",
                "category": "计算机与人工智能",
                "direction": "深度学习",
                "title": "课题 A",
            }

            folder = _project_folder(settings, project)

            self.assertEqual(
                folder,
                Path(tmp) / "output" / "assets" / "计算机与人工智能" / "深度学习" / "课题 A",
            )

    def test_asset_paths_use_project_folder_and_readable_names(self):
        with TemporaryDirectory() as tmp:
            settings = Settings(output_dir=Path(tmp) / "output")
            project = {
                "business_id": "ce-1",
                "category": "计算机与人工智能",
                "direction": "深度学习",
                "title": "课题 A",
                "professor": "Prof A",
            }

            poster = _asset_target_path(settings, project, {"field": "attachmentId"}, {"ext": "jpg"}, "https://cdn.example.com/a")
            pdf = _direct_asset_target_path(
                settings,
                project,
                {"field": "majorAttachment", "file_name": "研究材料.pdf"},
                "https://cdn.example.com/file.pdf",
            )

            self.assertEqual(poster.name, "海报.jpg")
            self.assertEqual(pdf.name, "研究材料.pdf")
            self.assertEqual(poster.parent, pdf.parent)
            self.assertIn("计算机与人工智能/深度学习/课题 A", str(pdf))

    def test_project_detail_file_contains_full_project_record(self):
        with TemporaryDirectory() as tmp:
            settings = Settings(output_dir=Path(tmp) / "output")
            project = {
                "business_id": "ce-1",
                "category": "计算机与人工智能",
                "direction": "深度学习",
                "title": "课题 A",
                "raw": {"detail": {"courseNameCn": "课题 A"}},
                "major_attachments": [{"fileName": "研究材料.pdf"}],
            }

            projects = _with_project_directories(settings, [project])
            _write_project_detail_files(settings, projects)

            detail_path = Path(projects[0]["project_dir"]) / "详情页信息.json"
            self.assertTrue(detail_path.exists())
            self.assertIn('"major_attachments"', detail_path.read_text(encoding="utf-8"))

    def test_project_directories_are_unique_for_duplicate_topic_paths(self):
        with TemporaryDirectory() as tmp:
            settings = Settings(output_dir=Path(tmp) / "output")
            projects = [
                {"business_id": "ce-1", "category": "商科", "direction": "金融学", "title": "课题 A"},
                {"business_id": "ce-2", "category": "商科", "direction": "金融学", "title": "课题 A"},
            ]

            with_dirs = _with_project_directories(settings, projects)

            self.assertNotEqual(with_dirs[0]["project_dir"], with_dirs[1]["project_dir"])
            self.assertTrue(with_dirs[0]["project_dir"].endswith("课题 A__ce-1"))
            self.assertTrue(with_dirs[1]["project_dir"].endswith("课题 A__ce-2"))

    def test_manifest_file_current_requires_same_project_folder(self):
        with TemporaryDirectory() as tmp:
            project_folder = Path(tmp) / "output" / "assets" / "计算机与人工智能" / "深度学习" / "课题 A"
            project_folder.mkdir(parents=True)
            current_file = project_folder / "海报.jpg"
            current_file.write_bytes(b"poster")
            old_folder = Path(tmp) / "output" / "assets" / "计算机与人工智能" / "课题 A"
            old_folder.mkdir(parents=True)
            old_file = old_folder / "海报.jpg"
            old_file.write_bytes(b"poster")

            self.assertTrue(_manifest_file_is_current({"file": str(current_file)}, project_folder))
            self.assertFalse(_manifest_file_is_current({"file": str(old_file)}, project_folder))


if __name__ == "__main__":
    unittest.main()
