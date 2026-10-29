from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any
import csv
import json
import sqlite3


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    seen = set()
    for record in records:
        for key in record:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def write_sqlite(path: Path, records: list[dict[str, Any]], table: str = "projects") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              business_id TEXT,
              title TEXT,
              category TEXT,
              source_url TEXT,
              canonical_url TEXT,
              crawled_at TEXT,
              data_json TEXT NOT NULL
            )
            """
        )
        conn.execute(f"DELETE FROM {table}")
        for record in records:
            conn.execute(
                f"""
                INSERT INTO {table}
                (business_id, title, category, source_url, canonical_url, crawled_at, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.get("business_id") or ""),
                    str(record.get("title") or ""),
                    str(record.get("category") or ""),
                    str(record.get("source_url") or ""),
                    str(record.get("canonical_url") or ""),
                    str(record.get("crawled_at") or ""),
                    json.dumps(record, ensure_ascii=False, sort_keys=True),
                ),
            )
        conn.commit()
    finally:
        conn.close()
