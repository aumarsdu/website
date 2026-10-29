"""Bounded streaming archive of explicitly referenced public resources."""
from __future__ import annotations

import argparse
import asyncio
from collections import deque
import hashlib
from email.utils import parsedate_to_datetime
import ipaddress
import json
import logging
import mimetypes
from pathlib import Path
import posixpath
import socket
import time
from urllib.parse import unquote, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from .assets import collect_asset_candidates, write_assets_db
from .complete_assets import dependencies
from .config import DEFAULT_USER_AGENT, Settings
from .public_transport import public_transport
from .robots_policy import RobotsPolicy
from .storage import append_jsonl, iter_jsonl, read_json, write_json
from .utils import find_asset_urls, utc_now

FILE_KEYS = {"FileId", "PrimaryPictureId", "PrimaryOrFirstPictureId", "PictureId", "LogoId", "VideoId"}
RETRYABLE = {"http_429", "http_500", "http_502", "http_503", "http_504", "ConnectError", "ConnectTimeout", "ReadTimeout", "ReadError", "RemoteProtocolError", "robots_unavailable", "private_or_unresolvable_dns"}
DENIED_PATHS = ("/api/_account", "/api/account", "/api/student", "/api/order", "/api/coupon", "/api/follow", "/selfcenter", "/login", "/connect/", "/mp/wappoc_appmsgcaptcha")


def reference_key(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    if ":" in host:
        host = f"[{host}]"
    if parsed.port and parsed.port != (443 if parsed.scheme == "https" else 80):
        host += f":{parsed.port}"
    return urlunparse((parsed.scheme.lower(), host, parsed.path or "/", parsed.params, parsed.query, ""))


def cached_file_valid(root: Path, record: dict) -> bool:
    if not record.get("local_path"):
        return False
    path = (root / record["local_path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size != record.get("size_bytes"):
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == record.get("sha256")


def safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        return False
    if host == "admin.dianedu.com" or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        if not ipaddress.ip_address(host).is_global:
            return False
    except ValueError:
        pass
    path = parsed.path
    for _ in range(3):
        path = unquote(path)
    return not posixpath.normpath(path.replace("\\", "/")).lower().startswith(DENIED_PATHS)


def referenced_files(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FILE_KEYS and isinstance(child, str) and child:
                yield {"url": f"https://www.dianedu.com/api/_file/GetFile/{child}", "kind": "asset", "is_video": key == "VideoId"}
            yield from referenced_files(child)
    elif isinstance(value, list):
        for child in value:
            yield from referenced_files(child)


def referenced_html_assets(value: object):
    """Resolve literal media references in public rich text without rewriting endpoints."""
    if isinstance(value, dict):
        for child in value.values():
            yield from referenced_html_assets(child)
    elif isinstance(value, list):
        for child in value:
            yield from referenced_html_assets(child)
    elif isinstance(value, str) and "<" in value:
        soup = BeautifulSoup(value, "lxml")
        for tag in soup.select("img, video, audio, source, object"):
            for attr in ("src", "data-src", "poster", "data"):
                ref = tag.get(attr)
                if isinstance(ref, str) and ref.strip() and not ref.strip().startswith(("data:", "blob:", "javascript:")):
                    yield {"url": urljoin("https://www.dianedu.com/", ref.strip()), "kind": "asset", "is_video": tag.name in {"video", "source"} and attr != "poster"}


class ReferencedArchive:
    def __init__(self, root: Path, max_gb: float, max_hours: float, include_video: bool, max_items: int = 15000):
        self.settings = Settings(root_dir=root)
        self.settings.ensure_dirs()
        limits_path = self.settings.reports_dir / "resource_limits.json"
        limits = read_json(limits_path, {})
        if not limits:
            limits = {"started_at": utc_now(), "deadline_epoch": time.time() + max_hours * 3600, "max_bytes": int(max_gb * 1000 ** 3), "transferred_bytes": 0}
            write_json(limits_path, limits)
        self.limits = limits
        self.max_bytes = min(int(max_gb * 1000 ** 3), limits["max_bytes"])
        self.deadline = time.monotonic() + max(0, min(max_hours * 3600, limits["deadline_epoch"] - time.time()))
        self.transferred_bytes = limits["transferred_bytes"]
        self.include_video = include_video
        self.max_items = min(15000, max_items)
        self.last_request = 0.0
        self.robots: dict[str, RobotsPolicy | None | bool] = {}
        self.robot_failures: dict[str, str] = {}
        self.manifest = {reference_key(x["url"]): x for x in read_json(self.settings.processed_dir / "referenced_manifest.json", [])}
        for record in iter_jsonl(self.settings.raw_dir / "referenced_attempts.jsonl"):
            self.manifest[reference_key(record["url"])] = record
        self.settings.ensure_dirs()
        self.total_bytes = sum(x.stat().st_size for x in self.settings.assets_dir.iterdir() if x.is_file())
        self.public_hosts: dict[str, bool] = {}
        self.denied_streak: dict[str, int] = {}
        progress = read_json(self.settings.reports_dir / "referenced_progress.json", {})
        self.blocked_hosts: set[str] = set(progress.get("blocked_hosts", [])) | {x["denied_host"] for x in self.manifest.values() if x.get("denied_host")}
        self.queue: deque[dict] = deque()
        self.seen: set[str] = set()
        self.client = httpx.AsyncClient(headers={"User-Agent": DEFAULT_USER_AGENT, "Accept-Encoding": "identity"}, timeout=httpx.Timeout(30, connect=15), follow_redirects=False, transport=public_transport(), trust_env=False)

    def account_transfer(self, size: int):
        self.transferred_bytes += size
        self.limits["transferred_bytes"] = self.transferred_bytes
        path = self.settings.reports_dir / "resource_limits.json"
        temporary = path.with_suffix(".json.tmp")
        write_json(temporary, self.limits)
        temporary.replace(path)
        if self.transferred_bytes > self.max_bytes:
            raise RuntimeError("byte_budget_reached")
        if time.monotonic() >= self.deadline:
            raise RuntimeError("time_budget_reached")

    async def wait_seconds(self, delay: float):
        if delay > self.deadline - time.monotonic():
            raise RuntimeError("required_wait_exceeds_time_budget")
        await asyncio.sleep(delay)

    async def throttle(self):
        if self.transferred_bytes >= self.max_bytes or self.total_bytes >= self.max_bytes:
            raise RuntimeError("byte_budget_reached")
        if time.monotonic() >= self.deadline:
            raise RuntimeError("time_budget_reached")
        await self.wait_seconds(max(0, 2 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        self.client.cookies.clear()

    async def allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.robots:
            await self.throttle()
            try:
                async with self.client.stream("GET", origin + "/robots.txt") as result:
                    if result.status_code in {401, 403, 429}:
                        self.blocked_hosts.add((parsed.hostname or "").rstrip(".").lower())
                        self.robots[origin] = False
                        self.robot_failures[origin] = f"robots_http_{result.status_code}"
                    elif result.status_code == 404:
                        self.robots[origin] = None
                    elif result.status_code == 200:
                        if result.headers.get("content-encoding", "identity") != "identity":
                            self.robots[origin] = False
                            self.robot_failures[origin] = "robots_encoding_unverifiable"
                            return False
                        content = bytearray()
                        async for chunk in result.aiter_raw(chunk_size=16384):
                            self.account_transfer(len(chunk))
                            if len(content) + len(chunk) > 65536:
                                self.robots[origin] = False
                                self.robot_failures[origin] = "robots_size_limit"
                                break
                            content.extend(chunk)
                            self.total_bytes += len(chunk)
                        else:
                            robot = RobotsPolicy(content.decode("utf-8", errors="replace"), DEFAULT_USER_AGENT)
                            self.robots[origin] = robot
                    else:
                        self.robots[origin] = False
            except httpx.HTTPError:
                self.robots[origin] = False
        robot = self.robots[origin]
        if robot is False:
            return False
        if robot is None:
            return True
        crawl_delay = robot.delay
        if crawl_delay > 2:
            await self.wait_seconds(max(0, crawl_delay - (time.monotonic() - self.last_request)))
        return robot.can_fetch(url)

    async def public_dns(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").rstrip(".").lower()
        if host not in self.public_hosts:
            try:
                entries = await asyncio.get_running_loop().getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
                self.public_hosts[host] = bool(entries) and all(ipaddress.ip_address(x[4][0]).is_global for x in entries)
            except (OSError, ValueError):
                self.public_hosts[host] = False
        return self.public_hosts[host]

    def seed(self):
        self.queue.extend({**x, "kind": "asset"} for x in collect_asset_candidates(self.settings))
        self.queue.append({"url": "https://www.dianedu.com/api/HomeBanner/Swiper", "kind": "public_json"})
        self.queue.append({"url": "https://www.dianedu.com/api/HomeBanner/Search", "kind": "public_json", "method": "POST", "payload": {}})
        for name in ("projects", "articles", "schools"):
            for record in read_json(self.settings.processed_dir / f"{name}.json", []):
                self.queue.extend({**x, "source_url": record["source_url"]} for x in referenced_files(record.get("raw", {})))
                self.queue.extend({**x, "source_url": record["source_url"]} for x in referenced_html_assets(record.get("raw", {})))
                if name == "projects" and record.get("fields", {}).get("FAQGroup"):
                    self.queue.append({"url": f"https://www.dianedu.com/api/Project/GetFaqs?projectId={record['id']}", "kind": "faq", "project_id": record["id"], "source_url": record["source_url"]})
                if name == "schools":
                    self.queue.extend({"url": x, "source_url": record["source_url"], "kind": "asset"} for x in find_asset_urls(json.dumps(record, ensure_ascii=False)))
                if name == "articles":
                    for key in ("Link", "WechatUrl"):
                        url = record.get("raw", {}).get(key)
                        if isinstance(url, str) and url.startswith(("https://", "http://")):
                            self.queue.appendleft({"url": url, "source_url": record["source_url"], "kind": "article", "article_id": record["id"]})

    async def download(self, item: dict) -> dict:
        original = item["url"]
        url = original
        record = {**item, "downloaded_at": utc_now()}
        if item.get("is_video") and not self.include_video:
            return {**record, "error_type": "video_excluded_by_budget"}
        for hop in range(5):
            if not safe_public_url(url):
                return {**record, "error_type": "excluded_access_or_host"}
            host = (urlparse(url).hostname or "").rstrip(".").lower()
            if host in self.blocked_hosts:
                return {**record, "error_type": "host_access_denied_stop", "denied_host": host}
            if not await self.public_dns(url):
                return {**record, "error_type": "private_or_unresolvable_dns"}
            if not await self.allowed_by_robots(url):
                origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                error_type = "robots_disallowed" if isinstance(self.robots.get(origin), RobotsPolicy) else self.robot_failures.get(origin, "robots_unavailable")
                return {**record, "error_type": error_type, **({"denied_host": host} if host in self.blocked_hosts else {})}
            await self.throttle()
            method = item.get("method", "GET")
            payload = item.get("payload")
            project_search = url == original == "https://www.dianedu.com/api/Project/Search" and isinstance(payload, dict) and set(payload) == {"Page", "Limit"} and type(payload["Page"]) is int and 1 <= payload["Page"] <= 200 and type(payload["Limit"]) is int and payload["Limit"] == 100
            if method != "GET" and not (method == "POST" and item["kind"] == "public_json" and ((url == original == "https://www.dianedu.com/api/HomeBanner/Search" and payload == {}) or project_search)):
                return {**record, "error_type": "method_outside_public_query_scope"}
            async with self.client.stream(method, url, json=item.get("payload") if method == "POST" else None) as response:
                record.update(status_code=response.status_code, final_url=str(response.url), content_type=response.headers.get("content-type"))
                if response.status_code in {301, 302, 303, 307, 308}:
                    if method == "POST":
                        return {**record, "error_type": "public_query_redirect_not_followed"}
                    location = response.headers.get("location")
                    if not location:
                        return {**record, "error_type": "redirect_without_location"}
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    if response.status_code in {401, 403}:
                        self.blocked_hosts.add(host)
                        record["denied_host"] = host
                    record["retry_after"] = response.headers.get("retry-after")
                    return {**record, "error_type": f"http_{response.status_code}"}
                self.denied_streak[host] = 0
                if response.headers.get("content-encoding", "identity") != "identity":
                    return {**record, "error_type": "unexpected_content_encoding"}
                content_type = response.headers.get("content-type", "")
                if any(endpoint in original for endpoint in ("/api/_file/GetFile/", "/_Framework/GetFile?")) and ("html" in content_type.lower() or "json" in content_type.lower()):
                    return {**record, "error_type": "file_endpoint_returned_nonfile"}
                if content_type.startswith("video/") and not self.include_video:
                    return {**record, "error_type": "video_excluded_by_budget"}
                length = response.headers.get("content-length")
                if item["kind"] in {"article", "faq", "public_json"} and length and int(length) > 20 * 1000 ** 2:
                    return {**record, "error_type": "article_size_limit"}
                if length and (self.total_bytes + int(length) > self.max_bytes or self.transferred_bytes + int(length) > self.max_bytes):
                    raise RuntimeError("byte_budget_reached")
                suffix = Path(urlparse(url).path).suffix
                if len(suffix) > 8:
                    suffix = ""
                if item["kind"] == "article":
                    suffix = ".html"
                elif not suffix:
                    suffix = mimetypes.guess_extension(content_type.split(";", 1)[0]) or ".bin"
                name = hashlib.sha256(original.encode()).hexdigest() + (suffix or ".bin")
                path = self.settings.assets_dir / name
                if path.exists():
                    index = 1
                    while path.with_name(f"{path.stem}.retry-{index}{path.suffix}").exists():
                        index += 1
                    path = path.with_name(f"{path.stem}.retry-{index}{path.suffix}")
                partial = path.with_suffix(path.suffix + ".part")
                if partial.exists():
                    self.total_bytes -= partial.stat().st_size
                digest = hashlib.sha256()
                size = 0
                try:
                    with partial.open("wb") as handle:
                        async for chunk in response.aiter_raw(chunk_size=65536):
                            self.account_transfer(len(chunk))
                            if item["kind"] in {"article", "faq", "public_json"} and size + len(chunk) > 20 * 1000 ** 2:
                                self.total_bytes += size
                                return {**record, "error_type": "article_size_limit"}
                            if self.total_bytes + size + len(chunk) > self.max_bytes or self.transferred_bytes > self.max_bytes or time.monotonic() >= self.deadline:
                                raise RuntimeError("stream_budget_reached")
                            handle.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                except Exception:
                    self.total_bytes += size
                    raise
                partial.replace(path)
                self.total_bytes += size
                record.update(local_path=str(path.relative_to(self.settings.root_dir)), size_bytes=size, sha256=digest.hexdigest())
                return record
        return {**record, "error_type": "too_many_redirects"}

    def expand(self, record: dict):
        if not record.get("local_path"):
            return
        path = self.settings.root_dir / record["local_path"]
        content_type = record.get("content_type") or ""
        if record["kind"] == "article":
            soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")
            body = soup.select_one("#js_content") or soup.select_one("article")
            if body is None:
                record["error_type"] = "article_body_missing_or_access_challenge"
                return
            text = body.get_text("\n", strip=True)
            if not text:
                record["error_type"] = "article_body_empty"
                return
            body_path = path.with_suffix(".txt")
            body_size = len(text.encode("utf-8"))
            previous_size = body_path.stat().st_size if body_path.exists() else 0
            if self.total_bytes + body_size - previous_size > self.max_bytes:
                raise RuntimeError("body_byte_budget_reached")
            body_path.write_text(text, encoding="utf-8")
            self.total_bytes += body_size - previous_size
            record["body_path"] = str(body_path.relative_to(self.settings.root_dir))
            for image in body.select("img[src], img[data-src]"):
                value = image.get("data-src") or image.get("src")
                if value:
                    self.queue.append({"url": urljoin(record["final_url"], value), "source_url": record["url"], "kind": "asset"})
        elif "javascript" in content_type or "text/css" in content_type:
            self.queue.extend({"url": x, "source_url": record["url"], "kind": "asset"} for x in dependencies(path.read_text(encoding="utf-8", errors="replace"), record["final_url"]))
        elif record["kind"] in {"faq", "public_json"}:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, (dict, list)):
                    raise ValueError("JSON envelope is not an object/list")
                self.queue.extend({**x, "source_url": record["url"]} for x in referenced_files(data))
                self.queue.extend({"url": x, "source_url": record["url"], "kind": "asset"} for x in find_asset_urls(json.dumps(data, ensure_ascii=False)))
            except (ValueError, UnicodeError):
                record["error_type"] = "public_json_schema_error"

    def save(self, status: str, reason: str | None = None):
        temp = self.settings.processed_dir / "referenced_manifest.json.tmp"
        write_json(temp, list(self.manifest.values()))
        temp.replace(self.settings.processed_dir / "referenced_manifest.json")
        write_json(self.settings.reports_dir / "referenced_progress.json", {"status": status, "stop_reason": reason, "seen": len(self.seen), "queued": len(self.queue), "downloaded": sum(bool(x.get("local_path")) for x in self.manifest.values()), "article_bodies": sum(bool(x.get("body_path")) for x in self.manifest.values()), "errors": sum(bool(x.get("error_type")) for x in self.manifest.values()), "bytes": self.total_bytes, "transferred_bytes": self.transferred_bytes, "blocked_hosts": sorted(self.blocked_hosts), "updated_at": utc_now()})

    async def download_with_retries(self, item: dict) -> dict:
        url = item["url"]
        for attempt in range(3):
            try:
                record = await self.download(item)
            except httpx.HTTPError as exc:
                record = {**item, "error_type": type(exc).__name__, "downloaded_at": utc_now()}
            if record.get("error_type") not in RETRYABLE or attempt == 2:
                return record
            retry_after = record.get("retry_after")
            delay = (attempt + 1) * 4
            if retry_after:
                try:
                    delay = max(delay, float(retry_after)) if retry_after.isdigit() else max(delay, parsedate_to_datetime(retry_after).timestamp() - time.time())
                except (ValueError, TypeError, OverflowError):
                    raise RuntimeError("unparseable_retry_after_stop")
            if record.get("error_type") == "private_or_unresolvable_dns":
                self.public_hosts.pop((urlparse(url).hostname or "").rstrip(".").lower(), None)
            if record.get("error_type") == "robots_unavailable":
                self.robots.pop(f"{urlparse(url).scheme}://{urlparse(url).netloc}", None)
            await self.wait_seconds(delay)
        return record

    async def run(self):
        self.seed()
        try:
            while self.queue:
                item = self.queue.popleft()
                if not safe_public_url(item["url"]):
                    url = item["url"]
                else:
                    url = reference_key(item["url"])
                    item["url"] = url
                if url in self.seen:
                    continue
                self.seen.add(url)
                if len(self.seen) > self.max_items:
                    self.seen.discard(url)
                    self.queue.appendleft(item)
                    raise RuntimeError("reference_cap_reached")
                record = self.manifest.get(url)
                if record is None or record.get("error_type") in RETRYABLE or record.get("local_path") and not cached_file_valid(self.settings.root_dir, record):
                    record = await self.download_with_retries(item)
                    self.manifest[url] = record
                    append_jsonl(self.settings.raw_dir / "referenced_attempts.jsonl", record)
                    if record.get("error_type") == "http_429":
                        raise RuntimeError("persistent_rate_limit_stop")
                self.expand(record)
                if len(self.seen) % 10 == 0:
                    self.save("running")
            self.save("finished")
        except Exception as exc:
            self.save("stopped", str(exc))
            raise
        finally:
            await self.client.aclose()
            assets = [{**x, "error": {"error_type": x["error_type"]} if x.get("error_type") else None} for x in self.manifest.values()]
            write_assets_db(self.settings, assets)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-gb", type=float, required=True)
    parser.add_argument("--max-hours", type=float, required=True)
    parser.add_argument("--include-video", action="store_true")
    parser.add_argument("--max-items", type=int, default=15000)
    args = parser.parse_args()
    logging.getLogger("httpx").setLevel(logging.WARNING)
    root = Path(__file__).resolve().parents[1] / "task_runs/20261014"
    if args.max_gb <= 0 or args.max_hours <= 0 or args.max_items <= 0:
        parser.error("Resource limits must be positive")
    archive = ReferencedArchive(root, args.max_gb, args.max_hours, args.include_video, args.max_items)
    async def bounded_run():
        try:
            await asyncio.wait_for(archive.run(), timeout=max(0, archive.deadline - time.monotonic()))
        except TimeoutError:
            archive.save("stopped", "time_budget_reached")
            raise
    asyncio.run(bounded_run())


if __name__ == "__main__":
    main()
