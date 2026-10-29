import asyncio
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from sou_crawler.config import CrawlSettings
from sou_crawler.pipeline import download_assets
from sou_crawler.storage import write_jsonl


class SlowFetcher:
    def __init__(self, _settings):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def download(self, _url):
        await asyncio.sleep(1)


class AssetDownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_download_assets_hard_timeout_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = CrawlSettings(output_dir=Path(tmp) / "output", timeout=-4.99, retries=0)
            settings.processed_dir.mkdir(parents=True)
            write_jsonl(
                settings.processed_dir / "projects.jsonl",
                [
                    {
                        "title": "T",
                        "category": "C",
                        "source_url": "https://jf.cas-harbour.cn/api",
                        "raw": {"posterUrl": "https://jf.cas-harbour.cn/a.jpg"},
                    }
                ],
            )

            with patch("sou_crawler.pipeline.AsyncFetcher", SlowFetcher):
                result = await download_assets(settings)

            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["errors"], {"timeout": 1})


if __name__ == "__main__":
    unittest.main()
