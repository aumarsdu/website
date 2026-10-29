import unittest
from types import SimpleNamespace

from sou_crawler.fetcher import AsyncFetcher
from sou_crawler.config import CrawlSettings


class FakeResponse:
    def __init__(self, body: bytes, content_type: str, status_code: int = 200):
        self.content = body
        self.headers = {"content-type": content_type}
        self.status_code = status_code
        self.request = SimpleNamespace(method="GET")
        self.url = "https://gec-api.gecacademy.cn/souapi/test"
        self.is_error = status_code >= 400
        self.text = body.decode("utf-8", errors="replace")

    def json(self):
        import json

        return json.loads(self.text)


class FetcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_plain_json_body_is_parsed(self) -> None:
        fetcher = AsyncFetcher(CrawlSettings())

        result = await fetcher._build_result(FakeResponse(b'{"code":200,"result":[]}', "text/plain; charset=utf-8"), None, None)

        self.assertEqual(result.json_data, {"code": 200, "result": []})
        self.assertIsNone(result.bytes_data)


if __name__ == "__main__":
    unittest.main()
