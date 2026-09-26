from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Any

from .config import CrawlConfig, ensure_output_dirs
from .utils import canonical_url, deep_find_asset_urls, flatten_json, iter_jsonl, utc_now_iso, write_json


PREFERRED_FIELDS = (
    "id",
    "uuid",
    "projectId",
    "courseId",
    "title",
    "name",
    "teacher",
    "instructor",
    "professor",
    "university",
    "major",
    "prerequisite",
    "intro",
    "description",
)


def normalize_outputs(config: CrawlConfig) -> None:
    ensure_output_dirs(config)
    normalized = collect_normalized_records(config)
    jsonl_path = config.processed_dir / "records.jsonl"
    csv_path = config.processed_dir / "records.csv"
    sqlite_path = config.processed_dir / "records.sqlite"
    jsonl_path.write_text("", encoding="utf-8")
    for record in normalized:
        with jsonl_path.open("a", encoding="utf-8") as fh:
            import json

            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_csv(csv_path, normalized)
    write_sqlite(sqlite_path, normalized)
    write_json(
        config.reports_dir / "normalize_stats.json",
        {
            "records": len(normalized),
            "jsonl": str(jsonl_path),
            "csv": str(csv_path),
            "sqlite": str(sqlite_path),
        },
    )


def collect_normalized_records(config: CrawlConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in iter_jsonl(config.raw_dir / "detail_responses.jsonl"):
        payload = row.get("payload")
        record = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(record, dict):
            normalized = normalize_record(record, row.get("meta", {}).get("url"))
            key = normalized.get("record_key")
            if key not in seen:
                seen.add(str(key))
                rows.append(normalized)

    for row in iter_jsonl(config.raw_dir / "list_records.jsonl"):
        record = row.get("record")
        if isinstance(record, dict):
            normalized = normalize_record(record, row.get("source_url"))
            key = normalized.get("record_key")
            if key not in seen:
                seen.add(str(key))
                rows.append(normalized)

    return rows


def normalize_record(record: dict[str, Any], source_url: str | None) -> dict[str, Any]:
    flat = flatten_json(record)
    preferred = {}
    for field in PREFERRED_FIELDS:
        for key, value in flat.items():
            if key.split(".")[-1] == field and value not in (None, ""):
                preferred[field] = value
                break
    record_key = preferred.get("uuid") or preferred.get("id") or preferred.get("projectId") or preferred.get("courseId")
    if not record_key:
        from .utils import content_hash

        record_key = content_hash(record)
    return {
        "record_key": str(record_key),
        "source_url": source_url,
        "canonical_url": canonical_url(source_url) if source_url else None,
        "crawled_at": utc_now_iso(),
        "asset_urls": deep_find_asset_urls(record),
        "raw": record,
        **preferred,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "record_key",
        "source_url",
        "canonical_url",
        "crawled_at",
        *PREFERRED_FIELDS,
        "asset_urls",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["asset_urls"] = ";".join(row.get("asset_urls", []))
            writer.writerow(out)


def write_sqlite(path: Path, rows: list[dict[str, Any]]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
              record_key TEXT PRIMARY KEY,
              source_url TEXT,
              canonical_url TEXT,
              crawled_at TEXT,
              title TEXT,
              name TEXT,
              teacher TEXT,
              instructor TEXT,
              professor TEXT,
              university TEXT,
              major TEXT,
              prerequisite TEXT,
              intro TEXT,
              description TEXT,
              asset_urls TEXT,
              raw_json TEXT
            )
            """
        )
        conn.execute("DELETE FROM records")
        import json

        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO records VALUES (
                  :record_key, :source_url, :canonical_url, :crawled_at, :title, :name,
                  :teacher, :instructor, :professor, :university, :major, :prerequisite,
                  :intro, :description, :asset_urls, :raw_json
                )
                """,
                {
                    **{key: row.get(key) for key in ("record_key", "source_url", "canonical_url", "crawled_at")},
                    **{key: row.get(key) for key in PREFERRED_FIELDS if key not in {"id", "uuid", "projectId", "courseId"}},
                    "asset_urls": json.dumps(row.get("asset_urls", []), ensure_ascii=False),
                    "raw_json": json.dumps(row.get("raw", {}), ensure_ascii=False),
                },
            )
        conn.commit()
    finally:
        conn.close()
