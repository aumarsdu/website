import asyncio
import unittest
from dataclasses import dataclass, field

from sou_crawler.fetcher import request_json_core


@dataclass
class _FakeResponse:
    status_code: int
    json_body: object = None
    url: str = "https://example.test/api"
    headers: dict = field(default_factory=dict)
    text: str = ""

    def json(self):
        if self.json_body is None:
            raise ValueError("no body")
        return self.json_body


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def request(self, method, url, params=None, json=None, headers=None):
        self.calls.append({"method": method, "url": url, "headers": headers})
        return self._responses.pop(0)


class _Stats:
    def __init__(self):
        self.requested = 0
        self.succeeded = 0
        self.errors: list[str] = []

    def on_request(self):
        self.requested += 1

    def on_success(self):
        self.succeeded += 1

    def on_error(self, category):
        self.errors.append(category)


def _run_core(client, retries=2):
    async def case():
        async def _no_sleep(_s):
            return None

        original_sleep = asyncio.sleep
        asyncio.sleep = _no_sleep
        try:
            stats = _Stats()
            payload, meta = await request_json_core(
                client,
                method="POST",
                url="https://example.test/api",
                json_body={"id": 1},
                retries=retries,
                rate_limit=0.0,
                on_request=stats.on_request,
                on_success=stats.on_success,
                on_error=stats.on_error,
            )
            return stats, payload, meta
        finally:
            asyncio.sleep = original_sleep

    return asyncio.run(case())


class RequestJsonCoreTest(unittest.TestCase):
    def test_401_stops_immediately_without_retry(self):
        client = _FakeClient([_FakeResponse(401)])
        stats, payload, meta = _run_core(client)
        self.assertIsNone(payload)
        self.assertEqual(meta["error_category"], "http_401_unauthorized")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(stats.errors, ["http_401_unauthorized"])

    def test_403_carries_stop_reason(self):
        client = _FakeClient([_FakeResponse(403)])
        _stats, payload, meta = _run_core(client)
        self.assertIsNone(payload)
        self.assertEqual(meta["error_category"], "http_403_forbidden")
        self.assertEqual(meta["stop_reason"], "forbidden")

    def test_429_is_retried_then_succeeds(self):
        client = _FakeClient([_FakeResponse(429), _FakeResponse(200, json_body={"ok": 1})])
        stats, payload, meta = _run_core(client)
        self.assertEqual(payload, {"ok": 1})
        self.assertEqual(stats.requested, 2)
        self.assertEqual(stats.succeeded, 1)
        self.assertEqual(meta["status"], 200)

    def test_parse_error_stops_immediately(self):
        client = _FakeClient([_FakeResponse(200, text="not json"), _FakeResponse(200, text="still not")])
        stats, payload, meta = _run_core(client)
        self.assertIsNone(payload)
        self.assertEqual(meta["error_category"], "parse_error")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(stats.errors, ["parse_error"])


if __name__ == "__main__":
    unittest.main()
