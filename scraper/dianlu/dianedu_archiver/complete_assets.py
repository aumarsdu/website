"""Archive same-host public resources, including JS/CSS dependencies."""
from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path
import json
import re
from urllib.parse import urljoin, urlparse

from .assets import collect_asset_candidates, write_assets_db
from .config import Settings
from .fetcher import Fetcher
from .storage import read_json, write_json
from .utils import find_asset_urls, safe_filename_from_url, sha256_bytes, utc_now


DEPENDENCY_RE = re.compile(r'''["']([^"'\s<>]+\.(?:js|css|png|jpe?g|svg|gif|webp|woff2?|ttf|ico)(?:\?[^"'\s<>]*)?)["']''', re.I)


def dependencies(text: str, source_url: str) -> list[str]:
    candidates = DEPENDENCY_RE.findall(text) + re.findall(r"url\(\s*([^\s\"'()]+)\s*\)", text)
    return sorted({urljoin(source_url, "/" + x if x.startswith("assets/") else x) for x in candidates if not x.startswith(("data:", "#"))})


async def main() -> None:
    base = Path(__file__).resolve().parents[1]
    settings = Settings(root_dir=base / "task_runs/20261014", rate_limit=2, timeout=20, retries=2)
    settings.ensure_dirs()
    queue = deque(collect_asset_candidates(settings))
    for school in read_json(settings.processed_dir / "schools.json", []):
        queue.extend({"url": x, "source_url": school["canonical_url"]} for x in find_asset_urls(json.dumps(school, ensure_ascii=False)))
    previous = read_json(settings.processed_dir / "asset_manifest.json", [])
    records = {x["url"]: x for x in previous if x.get("local_path") and (settings.root_dir / x["local_path"]).exists()}
    seen: set[str] = set()
    exclusions: dict[str, int] = {}
    fetcher = Fetcher(settings)
    # A public resource redirect must not silently expand the host boundary.
    fetcher._client.follow_redirects = False
    try:
        while queue:
            item = queue.popleft()
            url = item["url"]
            if url in seen:
                continue
            seen.add(url)
            if len(seen) > 2000:
                raise RuntimeError("Resource cap of 2000 exceeded")
            if not settings.is_allowed_url(url):
                host = urlparse(url).hostname or "invalid"
                exclusions[host] = exclusions.get(host, 0) + 1
                continue
            record = records.get(url)
            if record is None:
                result = await fetcher.get(url, binary=True)
                record = {"url": url, "source_url": item.get("source_url"), "status_code": result.status_code, "content_type": result.content_type, "downloaded_at": utc_now()}
                if result.status_code and 300 <= result.status_code < 400:
                    record["error"] = {"error_type": "redirect_not_followed", "message": "Resource redirect excluded from fixed-host archive"}
                elif result.error:
                    record["error"] = result.error.model_dump()
                    if result.status_code in {401, 403, 429}:
                        raise RuntimeError(f"Resource access boundary: {result.status_code}")
                elif result.content is not None:
                    path = settings.assets_dir / safe_filename_from_url(url, "")
                    path.write_bytes(result.content)
                    record.update(local_path=str(path.relative_to(settings.root_dir)), size_bytes=len(result.content), sha256=sha256_bytes(result.content))
                records[url] = record
                write_json(settings.processed_dir / "asset_manifest.json", list(records.values()))
            if record.get("local_path") and urlparse(url).path.endswith((".js", ".css")):
                text = (settings.root_dir / record["local_path"]).read_text(encoding="utf-8", errors="replace")
                queue.extend({"url": x, "source_url": url} for x in dependencies(text, url))
    finally:
        await fetcher.close()
        write_assets_db(settings, list(records.values()))
        write_json(settings.reports_dir / "asset_coverage.json", {"discovered": len(seen), "downloaded": sum(bool(x.get("local_path")) for x in records.values()), "failed": sum(bool(x.get("error")) for x in records.values()), "excluded_hosts": exclusions, "remaining_queue": len(queue), "updated_at": utc_now()})


if __name__ == "__main__":
    asyncio.run(main())
