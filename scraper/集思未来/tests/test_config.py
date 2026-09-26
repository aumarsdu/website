from sou_crawler.config import CrawlConfig, SITE_TARGETS


def test_default_discovery_entries_include_overseas_and_domestic_sites() -> None:
    config = CrawlConfig()
    entries = set(config.discovery_entries)

    assert "https://sou-tools.gecacademy.cn/" in entries
    assert "https://domestic.gecacademy.cn/" in entries
    assert {target.name for target in SITE_TARGETS} == {"sou_tools", "domestic"}
