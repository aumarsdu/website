from __future__ import annotations

from typing import Any
import sqlite3

from .config import Settings
from .fetcher import Fetcher
from .storage import append_jsonl, init_db, iter_jsonl, read_json, write_json
from .utils import safe_filename_from_url, sha256_bytes, utc_now


async def download_assets(settings: Settings) -> None:
    candidates = collect_asset_candidates(settings)
    if settings.dry_run:
        print({"command": "download-assets", "asset_candidates": len(candidates), "will_download": False})
        return
    fetcher = Fetcher(settings)
    records: list[dict[str, Any]] = []
    try:
        for item in candidates[: settings.max_pages * 20]:
            url = item["url"]
            if not settings.is_allowed_url(url):
                continue
            result = await fetcher.get(url, binary=True)
            record: dict[str, Any] = {
                "url": url,
                "source_url": item.get("source_url"),
                "status_code": result.status_code,
                "content_type": result.content_type,
                "downloaded_at": utc_now(),
            }
            if result.error:
                record["error"] = result.error.model_dump()
            elif result.content is not None:
                local_path = settings.assets_dir / safe_filename_from_url(url, default_suffix="")
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(result.content)
                record.update(
                    {
                        "local_path": str(local_path.relative_to(settings.root_dir)),
                        "size_bytes": len(result.content),
                        "sha256": sha256_bytes(result.content),
                    }
                )
            records.append(record)
            append_jsonl(settings.processed_dir / "asset_manifest.jsonl", record)
    finally:
        await fetcher.close()
    write_json(settings.processed_dir / "asset_manifest.json", records)
    write_assets_db(settings, records)
    write_json(settings.reports_dir / "download_assets_summary.json", {"assets": len(records)})


def collect_asset_candidates(settings: Settings) -> list[dict[str, Any]]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for page in iter_jsonl(settings.raw_dir / "pages_raw.jsonl"):
        for url in page.get("assets", []):
            if url in seen or not settings.is_asset_url(url):
                continue
            seen.add(url)
            items.append({"url": url, "source_url": page.get("canonical_url")})
    for dataset_name in ("projects", "articles", "project_list_items"):
        for record in read_json(settings.processed_dir / f"{dataset_name}.json", []):
            for url in record.get("assets", []) if isinstance(record, dict) else []:
                if url in seen or not settings.is_asset_url(url):
                    continue
                seen.add(url)
                items.append({"url": url, "source_url": record.get("canonical_url")})
    return items


def write_assets_db(settings: Settings, records: list[dict[str, Any]]) -> None:
    init_db(settings.db_path)
    conn = sqlite3.connect(settings.db_path)
    try:
        for record in records:
            conn.execute(
                """
                INSERT OR REPLACE INTO assets
                (url, source_url, local_path, content_type, size_bytes, sha256, status_code, downloaded_at, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("url"),
                    record.get("source_url"),
                    record.get("local_path"),
                    record.get("content_type"),
                    record.get("size_bytes"),
                    record.get("sha256"),
                    record.get("status_code"),
                    record.get("downloaded_at"),
                    __import__("json").dumps(record, ensure_ascii=False, sort_keys=True),
                ),
            )
        conn.commit()
    finally:
        conn.close()
