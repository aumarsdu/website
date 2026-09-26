import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from organize_processed_posters import (
    infer_subject,
    page_subject,
    project_type,
    safe_component,
)


def test_project_type_uses_site_type_metadata() -> None:
    assert project_type({"typeId": 39}, "2026暑期iHUB项目") == "2026暑期线下营地项目"
    assert project_type({"types": "研助起航系列"}, "普通课题") == "研助起航计划"
    assert project_type({"typeId": 56}, "全球在研：经济学方向") == "全球在研"


def test_subject_uses_website_page_type_before_inference() -> None:
    entries = [{"label": "pageType=2 typeIdList=6,32,44", "record": {}}]
    assert page_subject(entries) == "理工科"
    assert infer_subject("人工智能与数据科学专题", {}) == "计算机与人工智能"


def test_safe_component_keeps_topic_as_one_folder() -> None:
    result = safe_component("教育/与\\TESOL\n专题")
    assert "/" not in result
    assert "\\" not in result
    assert " " in result
