from seed_intel.crawler.storage import CrawlStorage
from seed_intel.extraction.schema import ParsedPage


def test_storage_reuses_cached_page_and_asset(tmp_path):
    storage = CrawlStorage(tmp_path, "batch")
    page = ParsedPage(source_url="https://www.seedasdan.com/project/", body_text="body", clean_html="<p>body</p>", markdown="body")
    storage.save_html(page.source_url, b"<p>body</p>", {"content-type": "text/html"})
    storage.save_page(page)
    asset_url = "https://www.seedasdan.com/files/guide.pdf"
    storage.save_asset(asset_url, b"pdf")

    assert storage.has_html(page.source_url)
    assert storage.has_asset(asset_url)
    assert storage.load_pages() == [page]
