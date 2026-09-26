from sou_crawler.utils import canonical_url, content_hash, deep_find_asset_urls


def test_canonical_url_sorts_query_params_and_drops_fragment() -> None:
    assert canonical_url("HTTPS://EXAMPLE.COM/path?b=2&a=1#frag") == "https://example.com/path?a=1&b=2"


def test_content_hash_is_deterministic_for_key_order() -> None:
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})


def test_deep_find_asset_urls_preserves_apostrophes_in_pdf_urls() -> None:
    url = "https://assets.example.com/reader/What's%20new.pdf"

    assert deep_find_asset_urls({"attachment": url}) == [url]
