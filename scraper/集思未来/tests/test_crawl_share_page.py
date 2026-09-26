from scripts.crawl_share_page import infer_category, infer_direction, parse_share_id


def test_parse_share_id_extracts_query_value() -> None:
    assert (
        parse_share_id("https://sou-m.gecacademy.cn/share?id=23e0ae90-f4e9-11f0-80f8-89a6fba17d1b")
        == "23e0ae90-f4e9-11f0-80f8-89a6fba17d1b"
    )


def test_parse_share_id_rejects_missing_id() -> None:
    try:
        parse_share_id("https://sou-m.gecacademy.cn/share")
    except ValueError as exc:
        assert "Missing id" in str(exc)
    else:
        raise AssertionError("expected missing id to fail")


def test_infer_category_prefers_computer_keywords() -> None:
    text = "MIS信息系统管理专题 搜索引擎核心技术 数据库系统 SQL 后端开发 计算机科学"

    assert infer_category(text) == "计算机与人工智能"


def test_infer_direction_extracts_topic_subject() -> None:
    title = "致理计划：MIS信息系统管理专题：搜索引擎核心技术：数据库系统的高性能设计"

    assert infer_direction(title, title) == "MIS信息系统管理"
