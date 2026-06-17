import unittest

from caoliao_archiver.publicapi import PublicH5Client


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeFetcher:
    def __init__(self):
        self.calls = []

    def post_json(self, url, payload):
        self.calls.append((url, payload))
        return FakeResponse(
            {
                "code": 1,
                "data": {
                    "markdown": "# Title",
                    "headers": "<meta property=\"og:title\" content=\"Title\" />",
                },
            }
        )


class PublicApiTests(unittest.TestCase):
    def test_get_content_by_route_parses_markdown_and_headers(self):
        fetcher = FakeFetcher()
        content = PublicH5Client(fetcher).get_content_by_route("h.qr61.cn/odBU6p/qYtCDec")
        self.assertEqual(content.markdown, "# Title")
        self.assertIn("og:title", content.headers)
        self.assertEqual(fetcher.calls[0][1], {"route": "h.qr61.cn/odBU6p/qYtCDec"})


if __name__ == "__main__":
    unittest.main()
