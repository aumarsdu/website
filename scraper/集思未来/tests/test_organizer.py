import json
from pathlib import Path

from sou_crawler.asset_downloader import asset_filename
from sou_crawler.config import CrawlConfig
from sou_crawler.organizer import organize_assets


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_organize_assets_preserves_category_direction_topic_structure(tmp_path: Path) -> None:
    config = CrawlConfig(output_dir=tmp_path / "output")
    poster_url = "https://assets.example.com/posters/deep-learning.jpg"
    pdf_url = "https://assets.example.com/syllabus/deep-learning.pdf"
    record = {
        "id": "course-1",
        "name": "深度学习课题",
        "teacherName": "王教授",
        "level2Name": "深度学习",
        "courseImgUrl": poster_url,
    }
    detail = {
        "id": "course-1",
        "name": "深度学习课题",
        "teacherName": "王教授",
        "description": "完整详情页介绍",
        "allAttachmentsArray": [{"str": "项目介绍PDF", "url": pdf_url}],
    }

    for seed in range(1, 5):
        append_jsonl(
            config.raw_dir / "list_responses.jsonl",
            {"page": 1, "payload": {"data": {"allNumber": seed, "courseList": []}}},
        )
    append_jsonl(
        config.raw_dir / "list_responses.jsonl",
        {
            "page": 1,
            "label": "计算机与人工智能+深度学习",
            "payload": {"data": {"allNumber": 5, "courseList": [record]}},
        },
    )
    append_jsonl(
        config.raw_dir / "list_records.jsonl",
        {"label": "计算机与人工智能+深度学习", "record": record},
    )
    append_jsonl(
        config.raw_dir / "detail_responses.jsonl",
        {"id": "course-1", "payload": {"data": detail}},
    )
    config.assets_dir.mkdir(parents=True)
    (config.assets_dir / asset_filename(poster_url)).write_bytes(b"poster")
    (config.assets_dir / asset_filename(pdf_url)).write_bytes(b"pdf")

    organize_assets(config)

    topic_dir = (
        config.output_dir
        / "organized_by_site"
        / "计算机与人工智能"
        / "深度学习"
        / "深度学习课题"
    )
    assert topic_dir.is_dir()
    assert (topic_dir / "深度学习课题.jpg").read_bytes() == b"poster"
    assert (topic_dir / "项目介绍PDF.pdf").read_bytes() == b"pdf"

    detail_json = json.loads((topic_dir / "详情页信息.json").read_text(encoding="utf-8"))
    assert detail_json["category"] == "计算机与人工智能"
    assert detail_json["direction"] == "深度学习"
    assert detail_json["detail_record"]["description"] == "完整详情页介绍"
    assert detail_json["pdf_urls"] == [pdf_url]
    assert pdf_url in (topic_dir / "详情页信息.md").read_text(encoding="utf-8")


def test_organize_assets_supports_flat_list_records(tmp_path: Path) -> None:
    config = CrawlConfig(output_dir=tmp_path / "output")
    poster_url = "https://assets.example.com/posters/domestic.jpg"
    record = {
        "id": "domestic-1",
        "_category": "计算机与人工智能",
        "name": "国内导师课题",
        "teacherName": "李教授",
        "courseImgUrl": poster_url,
    }

    append_jsonl(config.raw_dir / "list_records.jsonl", record)
    append_jsonl(
        config.raw_dir / "detail_responses.jsonl",
        {"id": "domestic-1", "payload": {"data": {"id": "domestic-1", "name": "国内导师课题"}}},
    )
    config.assets_dir.mkdir(parents=True)
    (config.assets_dir / asset_filename(poster_url)).write_bytes(b"poster")

    organize_assets(config)

    topic_dir = (
        config.output_dir
        / "organized_by_site"
        / "计算机与人工智能"
        / "未分方向"
        / "国内导师课题"
    )
    assert topic_dir.is_dir()
    assert (topic_dir / "国内导师课题.jpg").read_bytes() == b"poster"
