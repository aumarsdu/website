from __future__ import annotations

import httpx
import pytest

from crawler_common.fetcher import Fetcher


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture()
def _no_sleep(monkeypatch):
    monkeypatch.setattr("crawler_common.fetcher.time.sleep", lambda _s: None)


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="<html>ok</html>")


def test_requires_transparent_user_agent():
    with pytest.raises(ValueError):
        Fetcher("", {"example.com"})


def test_blocks_hosts_outside_whitelist(_no_sleep):
    with Fetcher("Bot/1.0", {"example.com"}, transport=_transport(_ok_handler)) as fetcher:
        result = fetcher.fetch("https://elsewhere.org/page")
    assert result.error == "host_not_allowed"


def test_blocks_redirects_outside_whitelist(_no_sleep):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "https://evil.net/next"})
        return httpx.Response(200, text="hi")

    with Fetcher("Bot/1.0", {"example.com"}, transport=_transport(handler)) as fetcher:
        result = fetcher.fetch("https://example.com/start")
    assert result.error == "host_not_allowed_after_redirect"


def test_retries_only_transient_statuses(_no_sleep):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, text="busy")

    with Fetcher("Bot/1.0", {"example.com"}, retries=2, obey_robots=False, transport=_transport(handler)) as fetcher:
        result = fetcher.fetch("https://example.com/x")
    assert result.error == "http_5xx_server_error"
    assert len(calls) == 3


def test_does_not_retry_forbidden(_no_sleep):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(403, text="no")

    with Fetcher("Bot/1.0", {"example.com"}, retries=2, obey_robots=False, transport=_transport(handler)) as fetcher:
        result = fetcher.fetch("https://example.com/x")
    assert result.error == "http_403_forbidden"
    assert len(calls) == 1


def test_robots_disallow_short_circuits(_no_sleep):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        raise AssertionError("fetch should have been gated by robots")

    with Fetcher("Bot/1.0", {"example.com"}, transport=_transport(handler)) as fetcher:
        result = fetcher.fetch("https://example.com/page")
    assert result.error == "robots_disallow"
