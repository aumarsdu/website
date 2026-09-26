import json
from pathlib import Path

from scripts.incremental_refresh import (
    collect_baseline_ids,
    filter_list_records,
    filter_list_responses,
    resolve_baseline_roots,
    select_topic_ids,
    topic_rows,
)
from scripts.sync_lark_base_topics import EXPECTED_FIELD_TYPES, validate_field_schema
from sou_crawler.utils import iter_jsonl


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_collect_baseline_ids_supports_direct_and_site_roots(tmp_path: Path) -> None:
    direct = tmp_path / "direct"
    grouped = tmp_path / "grouped"
    write_jsonl(direct / "raw" / "list_records.jsonl", [{"record": {"id": "one"}}])
    write_jsonl(grouped / "sou_tools" / "raw" / "list_records.jsonl", [{"record": {"id": "two"}}])

    assert collect_baseline_ids("sou_tools", [direct, grouped]) == {"one", "two"}


def test_filters_keep_only_new_ids_and_preserve_response_shape(tmp_path: Path) -> None:
    source_records = tmp_path / "current_records.jsonl"
    destination_records = tmp_path / "list_records.jsonl"
    source_responses = tmp_path / "current_responses.jsonl"
    destination_responses = tmp_path / "list_responses.jsonl"
    write_jsonl(
        source_records,
        [
            {"label": "计算机与人工智能+深度学习", "record": {"id": "old", "name": "旧课题"}},
            {"label": "计算机与人工智能+深度学习", "record": {"id": "new", "name": "新课题"}},
        ],
    )
    write_jsonl(
        source_responses,
        [
            {
                "label": "计算机与人工智能+深度学习",
                "payload": {"data": {"allPage": 1, "courseList": [{"id": "old"}, {"id": "new"}]}},
            }
        ],
    )

    filter_list_records(source_records, destination_records, {"new"})
    filter_list_responses(source_responses, destination_responses, {"new"})

    assert topic_rows(destination_records) == [{"id": "new", "title": "新课题", "teacher": None}]
    response = iter_jsonl(destination_responses)[0]
    assert response["payload"]["data"]["allPage"] == 1
    assert response["payload"]["data"]["courseList"] == [{"id": "new"}]


def test_resolve_baseline_roots_adds_prior_incremental_runs(tmp_path: Path) -> None:
    (tmp_path / "old-run").mkdir()
    (tmp_path / "current-run").mkdir()

    roots = resolve_baseline_roots(None, tmp_path, "current-run")

    assert tmp_path / "old-run" in roots
    assert tmp_path / "current-run" not in roots


def test_explicit_include_only_selects_existing_baseline_records() -> None:
    current_ids = {"already-crawled", "new"}
    baseline_ids = {"already-crawled"}
    include_ids = frozenset({"already-crawled"})
    included_ids, selected_ids = select_topic_ids(
        current_ids,
        baseline_ids,
        include_ids,
        include_only=True,
    )

    assert included_ids == {"already-crawled"}
    assert selected_ids == {"already-crawled"}


def test_explicit_include_can_be_combined_with_normal_new_topics() -> None:
    included_ids, selected_ids = select_topic_ids(
        {"already-crawled", "new"},
        {"already-crawled"},
        frozenset({"already-crawled"}),
        include_only=False,
    )

    assert included_ids == {"already-crawled"}
    assert selected_ids == {"already-crawled", "new"}


def test_validate_field_schema_rejects_attachment_write_target() -> None:
    fields = [{"name": name, "type": field_type} for name, field_type in EXPECTED_FIELD_TYPES.items()]
    assert validate_field_schema(fields)["适合年级"] == "select"

    fields = [{"name": name, "type": field_type} for name, field_type in EXPECTED_FIELD_TYPES.items()]
    next(field for field in fields if field["name"] == "教授头像")["type"] = "attachment"

    try:
        validate_field_schema(fields)
    except RuntimeError as exc:
        assert "教授头像" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("attachment field must not be accepted as a normal CellValue")
