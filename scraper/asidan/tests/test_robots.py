from __future__ import annotations

import httpx
import pytest

from seed_intel.crawler.fetcher import Fetcher
from seed_intel.crawler.robots import RobotsCache


def _transport(robots_status: int, robots_body: str = "", counter: list[int] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if counter is not None:
            counter.append(1)
        if request.url.path == "/robots.txt":
            return httpx.Response(robots_status, text=robots_body)
        return httpx.Response(200, text="<html>ok</html>")

    return httpx.MockTransport(handler)


def test_robots_allows_allowed_path_and_blocks_disallowed():
    cache = RobotsCache("TestBot/1.0", 5.0, _transport(200, "User-agent: *\nDisallow: /private/\n"))
    assert cache.allowed("https://example.com/public/page") is True
    assert cache.allowed("https://example.com/private/secret") is False


def test_robots_missing_file_allows_all():
    cache = RobotsCache("TestBot/1.0", 5.0, _transport(404))
    assert cache.allowed("https://example.com/anything") is True


def test_robots_forbidden_disallows_all():
    cache = RobotsCache("TestBot/1.0", 5.0, _transport(403))
    assert cache.allowed("https://example.com/") is False


def test_robots_server_error_disallows_all():
    cache = RobotsCache("TestBot/1.0", 5.0, _transport(500))
    assert cache.allowed("https://example.com/") is False


def test_robots_network_error_disallows_all():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    cache = RobotsCache("TestBot/1.0", 5.0, httpx.MockTransport(handler))
    assert cache.allowed("https://example.com/") is False


def test_robots_verdict_is_cached_per_origin():
    counter: list[int] = []
    cache = RobotsCache("TestBot/1.0", 5.0, _transport(404, counter=counter))
    cache.allowed("https://example.com/a")
    cache.allowed("https://example.com/b")
    assert len(counter) == 1


@pytest.fixture()
def _no_rate_limit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("seed_intel.crawler.fetcher.time.sleep", lambda _s: None)


def test_fetcher_respects_robots_disallow(_no_rate_limit):
    fetcher = Fetcher("TestBot/1.0", 5.0, 0, 0.0, obey_robots=True, transport=_transport(403))
    result = fetcher.fetch("https://example.com/page")
    fetcher.close()
    assert result.error == "robots_disallow"
    assert result.status_code == 0


def test_fetcher_robots_disabled_fetches_normally(_no_rate_limit):
    fetcher = Fetcher("TestBot/1.0", 5.0, 0, 0.0, obey_robots=False, transport=_transport(403))
    result = fetcher.fetch("https://example.com/page")
    fetcher.close()
    assert result.error is None
    assert result.status_code == 200
