import unittest

from sou_crawler.config import AUTHORIZED_DOMAINS, DEFAULT_ENTRY_URLS


class ConfigTests(unittest.TestCase):
    def test_default_entry_urls_include_requested_spa_targets(self) -> None:
        self.assertIn("https://jf.cas-harbour.cn/avocado/#/", DEFAULT_ENTRY_URLS)
        self.assertIn("https://jf.cas-harbour.cn/mini/#/", DEFAULT_ENTRY_URLS)

    def test_default_domains_are_limited_to_the_requested_target(self) -> None:
        self.assertEqual(AUTHORIZED_DOMAINS, {"jf.cas-harbour.cn"})


if __name__ == "__main__":
    unittest.main()
