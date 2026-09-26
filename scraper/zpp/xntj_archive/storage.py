from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_name(url: str, suffix: str) -> str:
    parsed = urlparse(url)
    base = (parsed.path.strip("/") or "index").replace("/", "--")
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-") or "resource"
    return f"{base}--{sha256(url.encode())[:12]}{suffix}"


class ArchiveStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("pages", "markdown", "metadata", "assets"):
            (root / name).mkdir(exist_ok=True)
        self.db = sqlite3.connect(root / "archive.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS urls (
                url TEXT PRIMARY KEY, source TEXT NOT NULL, status INTEGER,
                content_type TEXT, content_hash TEXT, path TEXT, error TEXT,
                discovered_at TEXT NOT NULL, fetched_at TEXT
            );
            CREATE TABLE IF NOT EXISTS assets (
                url TEXT PRIMARY KEY, source_url TEXT NOT NULL, status INTEGER,
                content_type TEXT, bytes INTEGER, content_hash TEXT, path TEXT,
                error TEXT, discovered_at TEXT NOT NULL, fetched_at TEXT
            );
            """
        )
        self.db.commit()

    def add_url(self, url: str, source: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO urls(url,source,discovered_at) VALUES(?,?,?)", (url, source, utc_now()))
        self.db.commit()

    def add_asset(self, url: str, source_url: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO assets(url,source_url,discovered_at) VALUES(?,?,?)", (url, source_url, utc_now()))
        self.db.commit()

    def pending_urls(self, limit: int | None = None) -> list[str]:
        query = "SELECT url FROM urls WHERE fetched_at IS NULL ORDER BY url"
        if limit is not None:
            query += " LIMIT ?"
            return [row["url"] for row in self.db.execute(query, (limit,))]
        return [row["url"] for row in self.db.execute(query)]

    def pending_assets(self) -> list[str]:
        return [row["url"] for row in self.db.execute("SELECT url FROM assets WHERE fetched_at IS NULL ORDER BY url")]

    def finish_url(self, url: str, *, status: int | None, content_type: str | None, content_hash: str | None, path: str | None, error: str | None) -> None:
        self.db.execute("UPDATE urls SET status=?,content_type=?,content_hash=?,path=?,error=?,fetched_at=? WHERE url=?", (status, content_type, content_hash, path, error, utc_now(), url))
        self.db.commit()

    def finish_asset(self, url: str, *, status: int | None, content_type: str | None, size: int | None, content_hash: str | None, path: str | None, error: str | None) -> None:
        self.db.execute("UPDATE assets SET status=?,content_type=?,bytes=?,content_hash=?,path=?,error=?,fetched_at=? WHERE url=?", (status, content_type, size, content_hash, path, error, utc_now(), url))
        self.db.commit()

    def write_bytes(self, category: str, url: str, data: bytes, suffix: str) -> str:
        path = self.root / category / archive_name(url, suffix)
        path.write_bytes(data)
        return str(path.relative_to(self.root))

    def write_json(self, url: str, value: dict) -> str:
        path = self.root / "metadata" / archive_name(url, ".json")
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(path.relative_to(self.root))

    def write_markdown(self, url: str, text: str) -> str:
        path = self.root / "markdown" / archive_name(url, ".md")
        path.write_text(text, encoding="utf-8")
        return str(path.relative_to(self.root))

    def summary(self) -> dict:
        def counts(table: str) -> dict[str, int]:
            rows = self.db.execute(f"SELECT COALESCE(CAST(status AS TEXT),'pending') status, COUNT(*) n FROM {table} GROUP BY status").fetchall()
            return {row["status"]: row["n"] for row in rows}
        return {"generated_at": utc_now(), "pages": counts("urls"), "assets": counts("assets")}

    def close(self) -> None:
        self.db.close()

