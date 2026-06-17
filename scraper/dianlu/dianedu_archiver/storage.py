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
        return []
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
    seen: set[str] = set()
    for record in records:
        for key in record:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pages (
              canonical_url TEXT PRIMARY KEY,
              source_url TEXT NOT NULL,
              title TEXT,
              content_type TEXT,
              status_code INTEGER,
              html_path TEXT,
              text_hash TEXT,
              crawled_at TEXT NOT NULL,
              data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projects (
              canonical_url TEXT PRIMARY KEY,
              source_url TEXT NOT NULL,
              title TEXT,
              category TEXT,
              location TEXT,
              grade TEXT,
              project_type TEXT,
              crawled_at TEXT NOT NULL,
              data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS articles (
              canonical_url TEXT PRIMARY KEY,
              source_url TEXT NOT NULL,
              title TEXT,
              category TEXT,
              published_at TEXT,
              crawled_at TEXT NOT NULL,
              data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS filters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_url TEXT NOT NULL,
              filter_name TEXT NOT NULL,
              option_text TEXT NOT NULL,
              option_value TEXT,
              data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hot_search_terms (
              term TEXT PRIMARY KEY,
              source_url TEXT NOT NULL,
              weight TEXT,
              crawled_at TEXT NOT NULL,
              data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assets (
              url TEXT PRIMARY KEY,
              source_url TEXT,
              local_path TEXT,
              content_type TEXT,
              size_bytes INTEGER,
              sha256 TEXT,
              status_code INTEGER,
              downloaded_at TEXT,
              data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_observations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              method TEXT,
              url TEXT NOT NULL,
              status_code INTEGER,
              resource_type TEXT,
              content_type TEXT,
              observed_at TEXT NOT NULL,
              data_json TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def upsert_records(path: Path, table: str, records: list[dict[str, Any]], key_field: str) -> None:
    init_db(path)
    conn = sqlite3.connect(path)
    try:
        for record in records:
            if table == "pages":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO pages
                    (canonical_url, source_url, title, content_type, status_code, html_path, text_hash, crawled_at, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.get("canonical_url"),
                        record.get("source_url"),
                        record.get("title"),
                        record.get("content_type"),
                        record.get("status_code"),
                        record.get("html_path"),
                        record.get("text_hash"),
                        record.get("crawled_at"),
                        json.dumps(record, ensure_ascii=False, sort_keys=True),
                    ),
                )
            elif table == "projects":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO projects
                    (canonical_url, source_url, title, category, location, grade, project_type, crawled_at, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.get(key_field),
                        record.get("source_url"),
                        record.get("title"),
                        record.get("category"),
                        record.get("location"),
                        record.get("grade"),
                        record.get("project_type"),
                        record.get("crawled_at"),
                        json.dumps(record, ensure_ascii=False, sort_keys=True),
                    ),
                )
            elif table == "articles":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO articles
                    (canonical_url, source_url, title, category, published_at, crawled_at, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.get(key_field),
                        record.get("source_url"),
                        record.get("title"),
                        record.get("category"),
                        record.get("published_at"),
                        record.get("crawled_at"),
                        json.dumps(record, ensure_ascii=False, sort_keys=True),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def replace_simple_table(path: Path, table: str, records: list[dict[str, Any]]) -> None:
    init_db(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(f"DELETE FROM {table}")
        for record in records:
            if table == "filters":
                conn.execute(
                    """
                    INSERT INTO filters (source_url, filter_name, option_text, option_value, data_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.get("source_url"),
                        record.get("filter_name"),
                        record.get("option_text"),
                        record.get("option_value"),
                        json.dumps(record, ensure_ascii=False, sort_keys=True),
                    ),
                )
            elif table == "hot_search_terms":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO hot_search_terms (term, source_url, weight, crawled_at, data_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.get("term"),
                        record.get("source_url"),
                        record.get("weight"),
                        record.get("crawled_at"),
                        json.dumps(record, ensure_ascii=False, sort_keys=True),
                    ),
                )
        conn.commit()
    finally:
        conn.close()
