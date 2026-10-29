from seed_intel.common.url_utils import (
    is_allowed_domain,
    is_asset_url,
    normalize_url,
    should_block_url,
)


def test_url_normalization():
    assert normalize_url("http://WWW.SeedASDAN.com/a//b/?utm_source=x&b=2&a=1#top") == "https://www.seedasdan.com/a/b/?a=1&b=2"


def test_allowed_domain_filter():
    assert is_allowed_domain("https://www.seedasdan.com/path", ["www.seedasdan.com"])
    assert not is_allowed_domain("https://evil.example/path", ["www.seedasdan.com"])


def test_blocked_url_filter():
    assert should_block_url("https://www.seedasdan.com/wp-admin/index.php", ["/wp-admin/"])
    assert not should_block_url("https://www.seedasdan.com/programs/", ["/wp-admin/"])


def test_asset_url():
    assert is_asset_url("https://www.seedasdan.com/a/b.pdf", [".pdf"])
