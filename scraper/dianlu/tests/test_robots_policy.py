from dianedu_archiver.robots_policy import RobotsPolicy


def test_wildcard_end_anchor_longest_allow_and_merged_groups():
    policy = RobotsPolicy("User-agent: *\nDisallow: /private/*\nAllow: /private/public/\nDisallow: /*.pdf$\nUser-agent: *\nDisallow: /other/", "ArchiveCrawler/1.0")
    assert not policy.can_fetch("https://example.com/private/a")
    assert policy.can_fetch("https://example.com/private/public/a")
    assert not policy.can_fetch("https://example.com/a.pdf")
    assert policy.can_fetch("https://example.com/a.pdf?download=1")
    assert not policy.can_fetch("https://example.com/other/a")


def test_specific_agent_and_percent_encoding_and_utf8():
    policy = RobotsPolicy("User-agent: *\nDisallow: /\nUser-agent: ArchiveCrawler\nDisallow: /secret/\nDisallow: /中文/", "ArchiveCrawler/1.0")
    assert policy.can_fetch("https://example.com/public/")
    assert not policy.can_fetch("https://example.com/%73ecret/a")
    assert not policy.can_fetch("https://example.com/%E4%B8%AD%E6%96%87/a")


def test_allow_wins_equal_rule_and_crawl_delay_is_retained():
    policy = RobotsPolicy("User-agent: *\nDisallow: /a\nAllow: /a\nCrawl-delay: 3600", "ArchiveCrawler")
    assert policy.can_fetch("https://example.com/a")
    assert policy.delay == 3600


def test_semicolon_path_parameters_are_not_dropped():
    policy = RobotsPolicy("User-agent: *\nDisallow: /a;b", "ArchiveCrawler")
    assert not policy.can_fetch("https://example.com/a;b")
