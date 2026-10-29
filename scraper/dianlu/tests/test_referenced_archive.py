import asyncio
import hashlib
import socket
import time

import httpx
import pytest

from dianedu_archiver.referenced_archive import ReferencedArchive, cached_file_valid, reference_key, referenced_files, safe_public_url


def test_external_reference_scope_excludes_private_access_surfaces():
    assert safe_public_url("https://mp.weixin.qq.com/s?__biz=public-article")
    assert safe_public_url("https://www.dianedu.com/api/_file/GetFile/observed-id")
    for url in ("https://admin.dianedu.com/a.png", "https://admin.dianedu.com./a.png", "http://localhost./x", "http://127.0.0.1/a.png", "http://[::1]/x", "http://169.254.169.254/x", "file:///tmp/x", "https://user:password@example.com/x", "https://www.dianedu.com/api/Student/Search", "https://www.dianedu.com/%61pi/%5fAccount/Login", "https://www.dianedu.com/api/OrderApi/Search", "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha"):
        assert not safe_public_url(url)


def test_referenced_ids_are_observed_and_do_not_include_user_avatars():
    payload = {"ProjectPictures": [{"FileId": "picture-id"}], "VideoId": "video-id", "User_PhotoId": "private-avatar", "PhotoId": "unneeded-photo", "LogoId": None}
    records = list(referenced_files(payload))
    assert {x["url"].rsplit("/", 1)[-1] for x in records} == {"picture-id", "video-id"}
    assert next(x for x in records if x["is_video"])["url"].endswith("video-id")


def test_fragment_variants_deduplicate():
    assert reference_key("https://WWW.DIANEDU.COM:443/a.png#one") == reference_key("https://www.dianedu.com/a.png#two")


def test_cache_checks_actual_bytes_and_path_boundary(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"abc")
    record = {"local_path": "a.png", "size_bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}
    assert cached_file_valid(tmp_path, record)
    path.write_bytes(b"abd")
    assert not cached_file_valid(tmp_path, record)
    assert not cached_file_valid(tmp_path, {**record, "local_path": "../outside.png"})


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks, fail=False):
        self.chunks = chunks
        self.fail = fail

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        if self.fail:
            raise httpx.ReadError("fixture interruption")


async def mock_archive(tmp_path, handler, max_bytes=1024 * 1024):
    archive = ReferencedArchive(tmp_path, max_bytes / 1000 ** 3, 1, True)
    await archive.client.aclose()
    archive.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async def throttle():
        if time.monotonic() >= archive.deadline:
            raise RuntimeError("time_budget_reached")
    async def public_dns(url):
        return True
    archive.throttle = throttle
    archive.public_dns = public_dns
    return archive


@pytest.mark.parametrize("content_type", ["text/html", "Text/HTML", "Application/JSON"])
def test_legacy_file_html_response_is_not_saved_as_image(tmp_path, content_type):
    async def run():
        def handler(request):
            return httpx.Response(404 if request.url.path == "/robots.txt" else 200, headers={"content-type": content_type}, stream=Stream([b"<html>SPA</html>"]))
        archive = await mock_archive(tmp_path, handler)
        try:
            result = await archive.download({"url": "https://www.dianedu.com/_Framework/GetFile?Id=observed", "kind": "asset"})
            assert result["error_type"] == "file_endpoint_returned_nonfile"
            assert "local_path" not in result
        finally:
            await archive.client.aclose()
    asyncio.run(run())


def test_stream_interruption_counts_partial_bytes(tmp_path):
    async def run():
        def handler(request):
            if request.url.path == "/robots.txt":
                return httpx.Response(404, stream=Stream([]))
            return httpx.Response(200, headers={"content-type": "image/png"}, stream=Stream([b"a" * 65536], fail=True))
        archive = await mock_archive(tmp_path, handler)
        try:
            with pytest.raises(httpx.ReadError):
                await archive.download({"url": "https://example.com/a.png", "kind": "asset"})
            assert archive.total_bytes == 65536
            assert sum(x.stat().st_size for x in archive.settings.assets_dir.iterdir()) == 65536
        finally:
            await archive.client.aclose()
    asyncio.run(run())


@pytest.mark.parametrize("payload,allowed", [({"Page": 1, "Limit": 100}, True), ({"Page": 0, "Limit": 100}, False), ({"Page": True, "Limit": 100}, False), ({"Page": 1, "Limit": 100, "Token": "public-test"}, False), ({"Page": 1, "Limit": 100.0}, False)])
def test_project_search_only_allows_fixed_public_pagination(tmp_path, payload, allowed):
    async def run():
        calls = []
        def handler(request):
            calls.append((request.method, request.url.path))
            return httpx.Response(404 if request.url.path == "/robots.txt" else 200, headers={"content-type": "application/json"}, stream=Stream([b"{}"]))
        archive = await mock_archive(tmp_path, handler)
        try:
            result = await archive.download({"url": "https://www.dianedu.com/api/Project/Search", "kind": "public_json", "method": "POST", "payload": payload})
            if allowed:
                assert result["size_bytes"] == 2
                assert ("POST", "/api/Project/Search") in calls
            else:
                assert result["error_type"] == "method_outside_public_query_scope"
                assert not any(method == "POST" for method, path in calls)
        finally:
            await archive.client.aclose()
    asyncio.run(run())


def test_first_access_denial_stops_host_without_more_requests(tmp_path):
    async def run():
        requests = []
        def handler(request):
            requests.append(request.url.path)
            return httpx.Response(404 if request.url.path == "/robots.txt" else 403, stream=Stream([]))
        archive = await mock_archive(tmp_path, handler)
        try:
            first = await archive.download({"url": "https://example.com/a.png", "kind": "asset"})
            second = await archive.download({"url": "https://example.com/b.png", "kind": "asset"})
            assert first["error_type"] == "http_403"
            assert second["error_type"] == "host_access_denied_stop"
            assert requests == ["/robots.txt", "/a.png"]
        finally:
            await archive.client.aclose()
    asyncio.run(run())


def test_robots_response_is_bounded_and_accounted(tmp_path):
    async def run():
        archive = await mock_archive(tmp_path, lambda request: httpx.Response(200, stream=Stream([b"a" * 16384] * 5)))
        try:
            assert not await archive.allowed_by_robots("https://example.com/a.png")
            assert archive.total_bytes == 65536
        finally:
            await archive.client.aclose()
    asyncio.run(run())


def test_dns_resolving_to_private_address_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))])
    async def run():
        archive = ReferencedArchive(tmp_path, 1, 1, True)
        try:
            assert not await archive.public_dns("https://public-looking.example/a.png")
        finally:
            await archive.client.aclose()
    asyncio.run(run())


@pytest.mark.parametrize("status", [401, 403, 429])
def test_robots_access_denial_blocks_host_immediately(tmp_path, status):
    async def run():
        requests = []
        def handler(request):
            requests.append(request.url.path)
            return httpx.Response(status, headers={"retry-after": "3600"}, stream=Stream([]))
        archive = await mock_archive(tmp_path, handler)
        try:
            first = await archive.download({"url": "https://example.com/a.png", "kind": "asset"})
            second = await archive.download({"url": "https://example.com/b.png", "kind": "asset"})
            assert first["error_type"] == f"robots_http_{status}"
            assert second["error_type"] == "host_access_denied_stop"
            assert requests == ["/robots.txt"]
        finally:
            await archive.client.aclose()
    asyncio.run(run())


def test_robots_transfer_budget_is_a_global_exception(tmp_path):
    async def run():
        archive = await mock_archive(tmp_path, lambda request: httpx.Response(200, stream=Stream([b"a" * 16384] * 2)), max_bytes=20000)
        try:
            with pytest.raises(RuntimeError, match="byte_budget_reached"):
                await archive.allowed_by_robots("https://example.com/a.png")
        finally:
            await archive.client.aclose()
    asyncio.run(run())


def test_wait_cannot_exceed_persistent_deadline(tmp_path):
    async def run():
        archive = ReferencedArchive(tmp_path, 1, 1, True)
        archive.deadline = time.monotonic() + 0.01
        try:
            with pytest.raises(RuntimeError, match="required_wait_exceeds_time_budget"):
                await archive.wait_seconds(3600)
        finally:
            await archive.client.aclose()
    asyncio.run(run())


def test_closed_host_stays_closed_after_instance_resume(tmp_path):
    async def run():
        archive = await mock_archive(tmp_path, lambda request: httpx.Response(403, stream=Stream([])))
        first = await archive.download({"url": "https://example.com/a.png", "kind": "asset"})
        archive.manifest[first["url"]] = first
        archive.save("stopped", "pilot_limit")
        await archive.client.aclose()
        resumed = ReferencedArchive(tmp_path, 1, 1, True)
        try:
            second = await resumed.download({"url": "https://example.com/b.png", "kind": "asset"})
            assert second["error_type"] == "host_access_denied_stop"
            assert resumed.limits["deadline_epoch"] == archive.limits["deadline_epoch"]
        finally:
            await resumed.client.aclose()
    asyncio.run(run())


def test_public_post_query_cannot_redirect_to_another_endpoint(tmp_path):
    async def run():
        calls = []
        def handler(request):
            calls.append((request.method, request.url.path))
            if request.url.path == "/robots.txt":
                return httpx.Response(404, stream=Stream([]))
            return httpx.Response(307, headers={"location": "https://example.com/write"}, stream=Stream([]))
        archive = await mock_archive(tmp_path, handler)
        try:
            result = await archive.download({"url": "https://www.dianedu.com/api/HomeBanner/Search", "kind": "public_json", "method": "POST", "payload": {}})
            assert result["error_type"] == "public_query_redirect_not_followed"
            assert calls == [("GET", "/robots.txt"), ("POST", "/api/HomeBanner/Search")]
        finally:
            await archive.client.aclose()
    asyncio.run(run())
