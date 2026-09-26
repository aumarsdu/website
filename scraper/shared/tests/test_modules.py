from __future__ import annotations

import json
from pathlib import Path

import httpx

from crawler_common import (
    classify_http_error,
    iter_jsonl,
    read_json,
    redact_headers,
    redact_mapping,
    sha256_text,
    write_json,
    write_jsonl,
)
from crawler_common.fsutil import link_or_copy
from crawler_common.url_rules import is_allowed_hostname, is_subdomain_allowed


def test_classify_http_error_taxonomy():
    assert classify_http_error(401) == "http_401_unauthorized"
    assert classify_http_error(403) == "http_403_forbidden"
    assert classify_http_error(404) == "http_404_not_found"
    assert classify_http_error(429) == "http_429_rate_limited"
    assert classify_http_error(502) == "http_5xx_server_error"
    assert classify_http_error(302) == "unknown_error"


def test_redact_headers_and_mapping():
    safe = redact_headers({"User-Agent": "Bot/1.0", "Authorization": "Bearer xyz", "Set-Cookie": "a=1"})
    assert safe["User-Agent"] == "Bot/1.0"
    assert safe["Authorization"] == "[REDACTED]"
    assert safe["Set-Cookie"] == "[REDACTED]"

    payload = redact_mapping({"title": "t", "api_key": "k", "nested": {"password": "p"}})
    assert payload == {"title": "t", "api_key": "[REDACTED]", "nested": {"password": "[REDACTED]"}}


def test_storage_json_jsonl_roundtrip(tmp_path: Path):
    write_json(tmp_path / "a" / "b.json", {"x": 1})
    assert read_json(tmp_path / "a" / "b.json") == {"x": 1}
    assert read_json(tmp_path / "missing.json", default=[]) == []

    write_jsonl(tmp_path / "rec.jsonl", [{"i": 1}, {"i": 2}])
    assert [r["i"] for r in iter_jsonl(tmp_path / "rec.jsonl")] == [1, 2]
    assert list(iter_jsonl(tmp_path / "nope.jsonl")) == []


def test_digest_and_link_or_copy(tmp_path: Path):
    source = tmp_path / "src.txt"
    source.write_text("hello", encoding="utf-8")
    assert sha256_text("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    target = tmp_path / "dst" / "dst.txt"
    action = link_or_copy(source, target)
    assert action in {"link", "copy"}
    assert target.read_text(encoding="utf-8") == "hello"


def test_url_rules():
    assert is_allowed_hostname("https://www.example.com/a", {"www.example.com"})
    assert not is_allowed_hostname("https://sub.example.com/", {"example.com"})
    assert is_subdomain_allowed("https://sub.example.com/", {"example.com"})
    assert not is_subdomain_allowed("https://evilexample.com/", {"example.com"})


def test_jsonl_roundtrip_uses_ascii_false(tmp_path: Path):
    write_jsonl(tmp_path / "c.jsonl", [{"标题": "课题"}])
    assert "课题" in (tmp_path / "c.jsonl").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "c.jsonl").read_text(encoding="utf-8").splitlines()[0]) == {"标题": "课题"}
