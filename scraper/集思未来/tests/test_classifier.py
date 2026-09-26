from pathlib import Path

from sou_crawler.classifier import analyze_network_logs
from sou_crawler.config import CrawlConfig


def test_analyze_network_logs_classifies_list_and_detail(tmp_path: Path) -> None:
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "sample_network_logs.jsonl"
    (discovery_dir / "network_logs.jsonl").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    signatures = analyze_network_logs(CrawlConfig(output_dir=tmp_path))

    categories = {category for signature in signatures for category in signature.categories}
    assert "项目列表接口" in categories
    assert "项目详情接口" in categories
    assert any(signature.is_paginated for signature in signatures)
    assert any("data.records.poster" in signature.asset_url_fields for signature in signatures)
