import unittest

from pathlib import Path
import tempfile

from sou_crawler.config import CrawlSettings
from sou_crawler.fetcher import FetchResult
from sou_crawler.storage import write_json
from sou_crawler.pipeline import asset_url_candidates, build_asset_jobs, collect_identifiers, extract_items, extract_total_pages, load_api_candidates, load_detail_items, load_override_candidates, normalize_item, request_candidate


class PipelineTests(unittest.TestCase):
    def test_extract_items_prefers_records_array(self) -> None:
        payload = {"code": 0, "data": {"records": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}], "total": 2}}

        self.assertEqual([item["id"] for item in extract_items(payload)], ["a", "b"])

    def test_extract_items_prefers_semantic_records_over_longer_nested_arrays(self) -> None:
        payload = {
            "data": {
                "records": [{"id": "record"}],
                "filters": [{"id": idx} for idx in range(10)],
            }
        }

        self.assertEqual(extract_items(payload), [{"id": "record"}])

    def test_extract_items_supports_course_list(self) -> None:
        payload = {"data": {"courseList": [{"id": "c1", "name": "Course"}], "allPage": 1}}

        self.assertEqual(extract_items(payload), [{"id": "c1", "name": "Course"}])

    def test_extract_total_pages_supports_all_page(self) -> None:
        self.assertEqual(extract_total_pages({"data": {"allPage": "262"}}), 262)

    def test_collect_identifiers_deduplicates(self) -> None:
        self.assertEqual(collect_identifiers([{"id": 1}, {"id": 1}, {"uuid": "u2"}]), [1, "u2"])

    def test_normalize_item_maps_common_fields(self) -> None:
        record = normalize_item(
            {
                "_source_url": "https://sou-tools.gecacademy.cn/api/project/list",
                "projectId": "p1",
                "projectName": "计算机与人工智能",
                "teacherName": "张教授",
                "school": "某大学",
                "posterUrl": "https://oss-cn.example.com/poster.jpg",
            }
        ).to_dict()

        self.assertEqual(record["id"], "p1")
        self.assertEqual(record["title"], "计算机与人工智能")
        self.assertEqual(record["teacher"], "张教授")
        self.assertEqual(record["asset_urls"], ["https://oss-cn.example.com/poster.jpg"])

    def test_relative_asset_urls_are_resolved_from_source_url(self) -> None:
        record = normalize_item(
            {
                "_source_url": "https://jf.cas-harbour.cn/api/project/list",
                "id": "p1",
                "title": "课题 A",
                "posterUrl": "/upload/poster.jpg",
            }
        ).to_dict()

        self.assertEqual(record["asset_urls"], ["https://jf.cas-harbour.cn/upload/poster.jpg"])

    def test_duplicate_asset_filenames_get_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            jobs = build_asset_jobs(
                [
                    {
                        "title": "课题 A",
                        "category": "计算机与人工智能",
                        "source_url": "https://jf.cas-harbour.cn/api/project/list",
                        "raw": {
                            "posterUrl": "https://jf.cas-harbour.cn/a/poster.jpg",
                            "coverUrl": "https://jf.cas-harbour.cn/b/cover.jpg",
                        },
                    }
                ],
                settings,
            )

        targets = [Path(job["target_path"]).name for job in jobs]
        self.assertEqual(targets, ["课题 A.jpg", "课题 A-2.jpg"])

    def test_asset_targets_avoid_case_insensitive_filesystem_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            jobs = build_asset_jobs(
                [
                    {
                        "title": "计算机专题：算法和Python语言基础",
                        "category": "未分类",
                        "source_url": "https://jf.cas-harbour.cn/api/project/list",
                        "raw": {"haibaoPic": "https://jf.cas-harbour.cn/a/one.jpg"},
                    },
                    {
                        "title": "计算机专题：算法和python语言基础",
                        "category": "未分类",
                        "source_url": "https://jf.cas-harbour.cn/api/project/list",
                        "raw": {"haibaoPic": "https://jf.cas-harbour.cn/a/two.jpg"},
                    },
                ],
                settings,
            )

        targets = [Path(job["target_path"]).name for job in jobs]
        self.assertEqual(targets, ["haibaoPic.jpg", "haibaoPic-2.jpg"])

    def test_asset_url_candidates_adds_public_oss_fallbacks(self) -> None:
        candidates = asset_url_candidates("https://bucket.oss-cn-beijing.aliyuncs.com/path/file.png")

        self.assertEqual(
            candidates,
            [
                "https://bucket.cn-beijing.oss.aliyuncs.com/path/file.png",
                "https://bucket.oss-accelerate.aliyuncs.com/path/file.png",
                "https://bucket.oss-cn-beijing.aliyuncs.com/path/file.png",
            ],
        )

    def test_redacted_post_body_is_not_replayed(self) -> None:
        class DummyFetcher:
            async def request(self, *_args, **_kwargs):  # pragma: no cover - should not be called
                raise AssertionError("redacted body must not be replayed")

        result = __import__("asyncio").run(
            request_candidate(
                DummyFetcher(),
                {"method": "POST"},
                "https://sou-tools.gecacademy.cn/api/list",
                {},
                {"token": "<redacted:str>"},
            )
        )

        self.assertIsInstance(result, FetchResult)
        self.assertEqual(result.error_category, "requires_sensitive_payload")

    def test_load_override_candidates_reads_manual_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            import os

            os.chdir(tmp)
            try:
                Path("config").mkdir()
                write_json(
                    Path("config/api_overrides.json"),
                    {
                        "list_apis": [
                            {
                                "name": "manual-list",
                                "url": "https://gec-api.gecacademy.cn/souapi/soutools/v2/course/query/common",
                                "method": "POST",
                                "page_param": "page",
                            }
                        ]
                    },
                )

                candidates = load_override_candidates("project_list")
            finally:
                os.chdir(cwd)

        self.assertEqual(candidates[0]["name"], "manual-list")
        self.assertEqual(candidates[0]["pagination_params"], ["page"])

    def test_load_api_candidates_dedupes_identical_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            settings.discovery_dir.mkdir(parents=True)
            write_json(
                settings.discovery_dir / "api_classification.json",
                {
                    "classified_apis": [
                        {
                            "suspected_type": "project_list",
                            "method": "POST",
                            "endpoint": "https://example.com/api",
                            "endpoint_without_query": "https://example.com/api",
                            "post_data": {"page": 1},
                        },
                        {
                            "suspected_type": "project_list",
                            "method": "POST",
                            "endpoint": "https://example.com/api",
                            "endpoint_without_query": "https://example.com/api",
                            "post_data": {"page": 1},
                        },
                    ]
                },
            )

            self.assertEqual(len(load_api_candidates(settings, "project_list")), 1)

    def test_load_detail_items_skips_list_payloads_saved_under_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            detail_dir = settings.raw_dir / "details" / "bad-detail"
            detail_dir.mkdir(parents=True)
            write_json(
                detail_dir / "page_0001.json",
                {
                    "request": {"url": "https://jf.cas-harbour.cn/zhongkehaobo/v2/topic/list?pageNum=1"},
                    "data": {
                        "result": {
                            "records": [{"id": "p1", "name": "课题"}],
                            "total": 1,
                            "pages": 1,
                        }
                    },
                },
            )

            self.assertEqual(load_detail_items(settings), [])


if __name__ == "__main__":
    unittest.main()
