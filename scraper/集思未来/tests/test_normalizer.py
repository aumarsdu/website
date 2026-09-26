from sou_crawler.normalizer import normalize_record


def test_normalize_record_extracts_preferred_fields_and_assets() -> None:
    row = normalize_record(
        {
            "id": 1,
            "title": "Research Course",
            "teacher": "Prof. X",
            "nested": {"syllabus": "https://example.com/course.pdf"},
        },
        "https://sou-tools.gecacademy.cn/api/project/detail?id=1",
    )

    assert row["record_key"] == "1"
    assert row["title"] == "Research Course"
    assert row["teacher"] == "Prof. X"
    assert row["asset_urls"] == ["https://example.com/course.pdf"]

