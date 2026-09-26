import asyncio
import json
from pathlib import Path

from sou_crawler.asset_downloader import asset_filename
from sou_crawler.full_refresh import (
    RefreshOptions,
    SiteSpec,
    build_domestic_seeds_from_network_logs,
    classify_protocol_error,
    download_assets_for_site,
    extract_course_records,
    triage_asset_failures,
)


def test_extract_course_records_supports_sou_course_list() -> None:
    payload = {"data": {"courseList": [{"id": "1"}, {"id": "2"}]}}

    assert extract_course_records(payload) == [{"id": "1"}, {"id": "2"}]


def test_extract_course_records_supports_domestic_levels() -> None:
    payload = {"data": {"levels": [{"id": "a"}, {"id": "b"}]}}

    assert extract_course_records(payload) == [{"id": "a"}, {"id": "b"}]


def test_build_domestic_seeds_from_network_logs(tmp_path: Path) -> None:
    log_path = tmp_path / "network_logs.jsonl"
    row = {
        "event": "response",
        "is_json": True,
        "method": "POST",
        "url": "https://gec-api.gecacademy.cn/souapi/soutools/course/query/course",
        "post_data_json": {
            "page": 3,
            "limit": 10,
            "pageType": 2,
            "isCnPage": True,
            "typeIdList": [1, 2],
        },
        "json": {"data": {"levels": [{"id": "1"}], "allPage": 1}},
    }
    log_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    seeds = build_domestic_seeds_from_network_logs(log_path)

    assert len(seeds) == 1
    assert seeds[0].body["page"] == 1
    assert seeds[0].limit == 10
    assert seeds[0].origin == "https://domestic.gecacademy.cn"


def test_download_assets_copies_cached_course_poster(tmp_path: Path) -> None:
    poster_url = "https://example.com/posters/course.jpg"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached = cache_dir / asset_filename(poster_url)
    cached.write_bytes(b"poster")

    site_dir = tmp_path / "run" / "sou_tools"
    raw_dir = site_dir / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "list_records.jsonl").write_text(
        json.dumps({"record": {"id": "1", "courseImgUrl": poster_url}}) + "\n",
        encoding="utf-8",
    )

    report = asyncio.run(
        download_assets_for_site(
            SiteSpec(
                name="sou_tools",
                base_url="https://sou-tools.gecacademy.cn/",
                seeds=[],
                asset_cache_dirs=[cache_dir],
            ),
            site_dir,
            RefreshOptions(
                run_id="test",
                output_root=tmp_path / "run",
                user_agent="test-agent",
                timeout=5,
                retries=0,
                rate_limit=0,
                concurrency=1,
                max_pages=1,
                max_details=1,
                download_assets=True,
            ),
        )
    )

    target = site_dir / "assets" / asset_filename(poster_url)
    assert target.read_bytes() == b"poster"
    assert report["available_in_cache"] == 1
    assert report["copied_from_cache"] == 1


def test_classify_protocol_error_maps_incomplete_read() -> None:
    exc = RuntimeError("peer closed connection without sending complete message body")

    assert classify_protocol_error(exc) == "incomplete_read"


def test_triage_asset_failures_groups_requested_buckets() -> None:
    triage = triage_asset_failures(
        {
            "http_404_not_found": ["https://example.com/missing.pdf"],
            "url_encoding_error": ["https://example.com/bad url.pdf"],
            "timeout": ["https://example.com/slow.pdf"],
            "http_403_forbidden": ["https://example.com/forbidden.pdf"],
        }
    )

    assert len(triage["http_404_not_found"]) == 1
    assert len(triage["url_encoding_error"]) == 1
    assert len(triage["remote_incomplete_read_or_timeout"]) == 1
    assert len(triage["other"]["http_403_forbidden"]) == 1
