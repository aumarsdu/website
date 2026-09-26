from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlsplit

import httpx


_DISALLOW_ALL = ("User-agent: *", "Disallow: /")


class RobotsCache:
    """Per-origin robots.txt cache used to gate every fetch.

    Semantics (RFC 9309 subset):
    - 2xx: rules parsed and applied per user-agent.
    - 4xx (e.g. 404): no robots.txt, crawling allowed.
    - 401/403, 5xx or network error: conservative disallow-all for the origin.
    """

    def __init__(self, user_agent: str, timeout: float, transport: httpx.BaseTransport | None = None) -> None:
        self._user_agent = user_agent
        self._timeout = timeout
        self._transport = transport
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._parsers:
            self._parsers[origin] = self._load(origin)
        return self._parsers[origin].can_fetch(self._user_agent, url)

    def _load(self, origin: str) -> urllib.robotparser.RobotFileParser:
        parser = urllib.robotparser.RobotFileParser()
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=self._timeout,
                transport=self._transport,
                headers={"User-Agent": self._user_agent},
            ) as client:
                response = client.get(f"{origin}/robots.txt")
        except httpx.HTTPError:
            parser.parse(_DISALLOW_ALL)
            return parser
        if response.status_code in (401, 403) or response.status_code >= 500:
            parser.parse(_DISALLOW_ALL)
        elif response.status_code >= 400:
            parser.parse([""])  # robots.txt absent: allow all
        else:
            parser.parse(response.text.splitlines())
        return parser
