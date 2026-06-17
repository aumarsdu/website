from pathlib import Path
import tempfile
import unittest

from sou_crawler.api_analyzer import analyze_network_logs, classify_response
from sou_crawler.config import CrawlSettings


class ApiAnalyzerTests(unittest.TestCase):
    def test_analyze_network_logs_classifies_list_and_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            settings.discovery_dir.mkdir(parents=True)
            fixture = Path(__file__).parent / "fixtures" / "sample_network_logs.jsonl"
            (settings.discovery_dir / "network_logs.jsonl").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

            result = analyze_network_logs(settings)

            types = {item["suspected_type"] for item in result["classified_apis"]}
            self.assertIn("project_list", types)
            self.assertIn("project_detail", types)
            self.assertTrue((settings.discovery_dir / "api_classification.json").exists())
            self.assertTrue((settings.discovery_dir / "api_classification.md").exists())


if __name__ == "__main__":
    unittest.main()


class AuthClassificationTests(unittest.TestCase):
    def test_cookie_alone_does_not_mark_api_as_requires_auth(self) -> None:
        row = {
            "url": "https://sou-tools.gecacademy.cn/api/project/list?page=1",
            "method": "GET",
            "status": 200,
            "resource_type": "xhr",
            "query_params": {"page": "1"},
            "had_sensitive_headers": True,
            "uses_auth_header": False,
            "had_sensitive_post_data": False,
            "response_json": {"data": {"records": [{"id": 1, "title": "A"}], "total": 1}},
        }

        classified = classify_response(row)

        self.assertFalse(classified["requires_auth"])

    def test_auth_header_marks_api_as_requires_auth(self) -> None:
        row = {
            "url": "https://sou-tools.gecacademy.cn/api/project/list?page=1",
            "method": "GET",
            "status": 200,
            "resource_type": "xhr",
            "query_params": {"page": "1"},
            "uses_auth_header": True,
            "response_json": {"data": {"records": [{"id": 1, "title": "A"}], "total": 1}},
        }

        classified = classify_response(row)

        self.assertTrue(classified["requires_auth"])

    def test_course_list_with_assets_is_classified_as_project_list(self) -> None:
        row = {
            "url": "https://gec-api.gecacademy.cn/souapi/soutools/v2/course/query/common",
            "method": "POST",
            "status": 200,
            "resource_type": "xhr",
            "query_params": {},
            "post_data": {"page": 1, "limit": 20},
            "response_json": {
                "data": {
                    "courseList": [
                        {
                            "id": "c1",
                            "name": "Course",
                            "teacherName": "Teacher",
                            "courseImgUrl": "https://example.com/a.jpg",
                        }
                    ],
                    "allPage": 2,
                    "currentPage": 1,
                }
            },
        }

        classified = classify_response(row)

        self.assertEqual(classified["suspected_type"], "project_list")
