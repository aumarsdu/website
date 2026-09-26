import asyncio
import hashlib
import unittest

from pathlib import Path
import tempfile
from unittest.mock import patch

from sou_crawler.config import CrawlSettings
from sou_crawler.fetcher import FetchResult
from sou_crawler.storage import write_json, write_jsonl
from sou_crawler.pipeline import (
    asset_url_candidates,
    build_asset_jobs,
    build_gec_profession_map,
    collect_identifiers,
    enrich_record_taxonomy,
    extract_items,
    extract_total_pages,
    find_asset_urls,
    flatten_topic_categories,
    load_api_candidates,
    load_detail_items,
    load_normalized_records,
    load_taxonomy_context,
    load_override_candidates,
    merge_list_and_detail_items,
    download_assets,
    normalize,
    normalize_item,
    request_candidate,
)


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
                "level2Name": "深度学习",
                "teacherName": "张教授",
                "school": "某大学",
                "posterUrl": "https://oss-cn.example.com/poster.jpg",
            }
        ).to_dict()

        self.assertEqual(record["id"], "p1")
        self.assertEqual(record["title"], "计算机与人工智能")
        self.assertEqual(record["direction"], "深度学习")
        self.assertEqual(record["teacher"], "张教授")
        self.assertEqual(record["asset_urls"], ["https://oss-cn.example.com/poster.jpg"])

    def test_merge_list_and_detail_items_keeps_list_fields_and_prefers_detail(self) -> None:
        list_items = [
            {
                "_source_url": "https://jf.cas-harbour.cn/zhongkehaobo/v2/topic/list?pageNum=1",
                "id": "p1",
                "name": "列表课题名称",
                "teacherName": "列表教授",
                "schoolName": "列表学校",
            }
        ]
        detail_items = [
            {
                "_source_url": "https://jf.cas-harbour.cn/zhongkehaobo/v2/topic/detail/p1?sourceType=2",
                "id": "p1",
                "name": "详情课题名称",
                "courseIntroduction": "详情简介",
                "_detail_response": {"result": {"id": "p1", "courseIntroduction": "详情简介"}},
            }
        ]

        merged = merge_list_and_detail_items(list_items, detail_items)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["name"], "详情课题名称")
        self.assertEqual(merged[0]["teacherName"], "列表教授")
        self.assertEqual(merged[0]["courseIntroduction"], "详情简介")
        self.assertEqual(merged[0]["_detail_response"]["result"]["id"], "p1")

    def test_normalize_merges_detail_with_its_list_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            list_dir = settings.raw_dir / "lists" / "topic-list"
            detail_dir = settings.raw_dir / "details" / "topic-detail"
            list_dir.mkdir(parents=True)
            detail_dir.mkdir(parents=True)
            write_json(
                list_dir / "page_0001.json",
                {
                    "request": {"url": "https://jf.cas-harbour.cn/zhongkehaobo/v2/topic/list?pageNum=1"},
                    "data": {"result": {"records": [{"id": "p1", "name": "列表名称", "teacherName": "列表教授"}]}},
                },
            )
            write_json(
                detail_dir / "p1.json",
                {
                    "request": {"url": "https://jf.cas-harbour.cn/zhongkehaobo/v2/topic/detail/p1?sourceType=2"},
                    "data": {"result": {"id": "p1", "name": "详情名称", "courseIntroduction": "详情简介"}},
                },
            )

            stats = normalize(settings)
            records = __import__("json").loads((settings.processed_dir / "projects.jsonl").read_text(encoding="utf-8"))

        self.assertEqual(stats["records"], 1)
        self.assertEqual(records["title"], "详情名称")
        self.assertEqual(records["teacher"], "列表教授")
        self.assertEqual(records["description"], "详情简介")
        self.assertEqual(records["raw"]["_detail_response"]["result"]["id"], "p1")

    def test_enrich_record_taxonomy_maps_gec_profession_and_direction_ids(self) -> None:
        mapping = build_gec_profession_map(
            [
                {
                    "id": 33,
                    "name": "计算机与人工智能",
                    "profession": [
                        {
                            "id": 12,
                            "name": "人工智能",
                            "allFp": [{"id": 34, "name": "深度学习"}],
                        }
                    ],
                }
            ]
        )
        record = {
            "title": "AI 课题",
            "category": None,
            "direction": None,
            "raw": {"professionId": 12, "directionId": 34},
        }

        enriched = enrich_record_taxonomy(record, {"gec_professions": mapping, "topic_categories": []})

        self.assertEqual(enriched["category"], "计算机与人工智能")
        self.assertEqual(enriched["direction"], "深度学习")
        self.assertEqual(enriched["profession"], "人工智能")
        self.assertEqual(enriched["taxonomy_source"], "gec_profession_direction")

    def test_load_taxonomy_context_prefers_the_latest_refresh_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            taxonomy_dir = settings.raw_dir / "taxonomy" / "refresh_20260730"
            write_json(
                taxonomy_dir / "gec_profession_direction.json",
                {
                    "data": {
                        "data": {
                            "direction": [
                                {
                                    "name": "计算机与人工智能",
                                    "profession": [{"id": 12, "name": "人工智能", "allFp": [{"id": 34, "name": "深度学习"}]}],
                                }
                            ]
                        }
                    }
                },
            )
            write_json(
                taxonomy_dir / "harbour_topic_category.json",
                {"data": {"result": [{"name": "工科", "child": [{"name": "信息与通信工程"}]}]}},
            )

            taxonomy = load_taxonomy_context(settings)

        self.assertEqual(taxonomy["gec_professions"]["profession:12:direction:34"]["direction"], "深度学习")
        self.assertEqual(taxonomy["topic_categories"], [{"category": "工科", "direction": "信息与通信工程", "source": "topic_category"}])

    def test_enrich_record_taxonomy_matches_topic_lingyu_to_category_tree(self) -> None:
        categories = flatten_topic_categories(
            [
                {
                    "name": "计算机",
                    "child": [{"id": "3", "name": "人工智能", "pid": "topic_computer"}],
                }
            ]
        )
        record = {
            "title": "自然语言处理课题",
            "category": None,
            "direction": None,
            "raw": {"topicLingyu": "人工智能，机器学习，自然语言处理"},
        }

        enriched = enrich_record_taxonomy(record, {"gec_professions": {}, "topic_categories": categories})

        self.assertEqual(enriched["category"], "计算机")
        self.assertEqual(enriched["direction"], "人工智能")
        self.assertEqual(enriched["taxonomy_source"], "topic_category")

    def test_enrich_record_taxonomy_uses_supplemental_keyword_fallback(self) -> None:
        record = {
            "title": "环境科学与生态学专题",
            "category": None,
            "direction": None,
            "raw": {"name": "环境科学与生态学专题"},
        }

        enriched = enrich_record_taxonomy(record, {"gec_professions": {}, "topic_categories": []})

        self.assertEqual(enriched["category"], "工科")
        self.assertEqual(enriched["direction"], "环境科学与工程")
        self.assertEqual(enriched["taxonomy_source"], "supplemental_keyword")

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

    def test_asset_targets_follow_site_category_direction_topic_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            jobs = build_asset_jobs(
                [
                    {
                        "title": "视觉识别课题",
                        "category": "计算机与人工智能",
                        "direction": "深度学习",
                        "source_url": "https://jf.cas-harbour.cn/api/project/list",
                        "raw": {
                            "posterUrl": "https://jf.cas-harbour.cn/a/poster.jpg",
                            "syllabusPdf": "https://jf.cas-harbour.cn/a/syllabus.pdf",
                        },
                    }
                ],
                settings,
            )

        targets = [Path(job["target_path"]).relative_to(settings.site_dir) for job in jobs]
        self.assertEqual(
            targets,
            [
                Path("计算机与人工智能") / "深度学习" / "视觉识别课题" / "视觉识别课题.jpg",
                Path("计算机与人工智能") / "深度学习" / "视觉识别课题" / "syllabusPdf.pdf",
            ],
        )

    def test_find_asset_urls_ignores_internal_detail_response(self) -> None:
        assets = find_asset_urls(
            {
                "syllabusPdf": "https://jf.cas-harbour.cn/a/course.pdf",
                "_detail_response": {"syllabusPdf": "https://jf.cas-harbour.cn/a/course.pdf"},
            }
        )

        self.assertEqual([asset["url"] for asset in assets], ["https://jf.cas-harbour.cn/a/course.pdf"])

    def test_shared_asset_url_has_a_target_in_each_topic_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            jobs = build_asset_jobs(
                [
                    {"id": "one", "title": "课题一", "category": "理科", "direction": "数学", "raw": {"pdf": "https://jf.cas-harbour.cn/a/shared.pdf"}},
                    {"id": "two", "title": "课题二", "category": "理科", "direction": "数学", "raw": {"pdf": "https://jf.cas-harbour.cn/a/shared.pdf"}},
                ],
                settings,
            )

        self.assertEqual(len(jobs), 2)
        self.assertEqual({job["url"] for job in jobs}, {"https://jf.cas-harbour.cn/a/shared.pdf"})
        self.assertNotEqual(jobs[0]["target_path"], jobs[1]["target_path"])

    def test_download_assets_caches_content_and_materializes_shared_references(self) -> None:
        class FakeAssetFetcher:
            downloads: list[str] = []

            def __init__(self, _settings: CrawlSettings):
                pass

            async def __aenter__(self) -> "FakeAssetFetcher":
                return self

            async def __aexit__(self, *_args: object) -> None:
                return None

            async def download(self, url: str) -> FetchResult:
                type(self).downloads.append(url)
                return FetchResult(url, "GET", 200, {}, None, None, b"identical public file")

        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            write_jsonl(
                settings.processed_dir / "projects.jsonl",
                [
                    {"id": "one", "title": "课题一", "category": "理科", "direction": "数学", "source_url": "https://jf.cas-harbour.cn/list", "raw": {"pdf": "https://jf.cas-harbour.cn/a/shared.pdf"}},
                    {"id": "two", "title": "课题二", "category": "理科", "direction": "数学", "source_url": "https://jf.cas-harbour.cn/list", "raw": {"pdf": "https://jf.cas-harbour.cn/a/shared.pdf"}},
                    {"id": "three", "title": "课题三", "category": "理科", "direction": "数学", "source_url": "https://jf.cas-harbour.cn/list", "raw": {"pdf": "https://jf.cas-harbour.cn/a/different-url.pdf"}},
                ],
            )
            with patch("sou_crawler.pipeline.AsyncFetcher", FakeAssetFetcher):
                stats = asyncio.run(download_assets(settings))
                repeat_stats = asyncio.run(download_assets(settings))

            jobs = build_asset_jobs(load_normalized_records(settings), settings)
            targets = [Path(job["target_path"]) for job in jobs]
            digest = hashlib.sha256(b"identical public file").hexdigest()
            cache_path = settings.asset_cache_dir / "sha256" / digest

            self.assertEqual(FakeAssetFetcher.downloads, ["https://jf.cas-harbour.cn/a/shared.pdf", "https://jf.cas-harbour.cn/a/different-url.pdf"])
            self.assertEqual(stats["downloaded"], 2)
            self.assertEqual(stats["content_duplicates"], 1)
            self.assertEqual(stats["hardlinked"], 3)
            self.assertTrue(cache_path.exists())
            self.assertTrue(all(path.read_bytes() == b"identical public file" for path in targets))
            self.assertTrue(all(path.stat().st_ino == cache_path.stat().st_ino for path in targets))

            self.assertEqual(repeat_stats["asset_urls"], 0)
            self.assertEqual(FakeAssetFetcher.downloads, ["https://jf.cas-harbour.cn/a/shared.pdf", "https://jf.cas-harbour.cn/a/different-url.pdf"])

    def test_normalize_writes_full_detail_json_into_topic_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            detail_dir = settings.raw_dir / "details" / "detail-api"
            detail_dir.mkdir(parents=True)
            write_json(
                detail_dir / "p1.json",
                {
                    "request": {"url": "https://jf.cas-harbour.cn/zhongkehaobo/v2/topic/detail/p1?sourceType=2"},
                    "data": {
                        "data": {
                            "projectId": "p1",
                            "projectName": "视觉识别课题",
                            "level1Name": "计算机与人工智能",
                            "level2Name": "深度学习",
                            "body": {"全部详情": "保留"},
                            "syllabusPdf": "https://jf.cas-harbour.cn/a/syllabus.pdf",
                        }
                    },
                },
            )

            stats = normalize(settings)

            detail_path = settings.site_dir / "计算机与人工智能" / "深度学习" / "视觉识别课题" / "details.json"
            self.assertEqual(stats["site_detail_files"], 1)
            self.assertTrue(detail_path.exists())
            payload = __import__("json").loads(detail_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["raw"]["body"], {"全部详情": "保留"})
            self.assertEqual(payload["asset_urls"], ["https://jf.cas-harbour.cn/a/syllabus.pdf"])

    def test_normalize_keeps_duplicate_topic_titles_in_separate_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output")
            detail_dir = settings.raw_dir / "details" / "detail-api"
            detail_dir.mkdir(parents=True)
            for project_id in ("p1", "p2"):
                write_json(
                    detail_dir / f"{project_id}.json",
                    {
                        "request": {"url": f"https://jf.cas-harbour.cn/zhongkehaobo/v2/topic/detail/{project_id}?sourceType=2"},
                        "data": {
                            "data": {
                                "projectId": project_id,
                                "projectName": "同名课题",
                                "level1Name": "计算机与人工智能",
                                "level2Name": "深度学习",
                            }
                        },
                    },
                )

            stats = normalize(settings)

            detail_files = sorted(settings.site_dir.glob("计算机与人工智能/深度学习/同名课题*/details.json"))
            self.assertEqual(stats["site_detail_files"], 2)
            self.assertEqual(len(detail_files), 2)
            self.assertTrue(any(path.parent.name == "同名课题__p1" for path in detail_files))
            self.assertTrue(any(path.parent.name == "同名课题__p2" for path in detail_files))

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
