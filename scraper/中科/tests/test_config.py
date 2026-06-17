import unittest

from sou_crawler.config import AUTHORIZED_DOMAINS, DEFAULT_ENTRY_URLS


class ConfigTests(unittest.TestCase):
    def test_default_entry_urls_include_requested_spa_targets(self) -> None:
        self.assertIn("https://jf.cas-harbour.cn/avocado/#/", DEFAULT_ENTRY_URLS)
        self.assertIn("https://jf.cas-harbour.cn/mini/#/pages/topic/topic", DEFAULT_ENTRY_URLS)

    def test_default_domains_include_public_sou_api_host(self) -> None:
        self.assertIn("gec-api.gecacademy.cn", AUTHORIZED_DOMAINS)


if __name__ == "__main__":
    unittest.main()
