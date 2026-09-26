from pathlib import Path

from scripts.audit_scope_and_completeness import (
    LocalInventory,
    collect_non_scope_from_row,
    placement_issue,
)


def test_scope_audit_treats_external_pdfs_as_asset_hosts_not_non_scope() -> None:
    inventory = LocalInventory()
    row = {
        "source_url": "https://gec-api.gecacademy.cn/souapi/course/query/share",
        "payload": {
            "data": {
                "id": "course-1",
                "allAttachmentsArray": [
                    {"url": "https://arxiv.org/pdf/2401.00001.pdf"},
                ],
            }
        },
    }

    collect_non_scope_from_row(inventory, Path("raw/detail_responses.jsonl"), row)

    assert inventory.non_scope_items == []
    assert inventory.external_asset_hosts == {"arxiv.org": 1}


def test_scope_audit_reports_source_urls_outside_scope() -> None:
    inventory = LocalInventory()
    row = {"source_url": "https://example.com/course/list"}

    collect_non_scope_from_row(inventory, Path("raw/list_records.jsonl"), row)

    assert inventory.non_scope_items[0]["host"] == "example.com"


def test_placement_issue_accepts_category_direction_topic_structure() -> None:
    path = Path("organized_by_site/计算机与人工智能/深度学习/深度学习课题/详情页信息.json")
    info = {
        "id": "course-1",
        "category": "计算机与人工智能",
        "direction": "深度学习",
        "title": "深度学习课题",
    }

    assert placement_issue(path, info) is None
