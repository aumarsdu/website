from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS crawl_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    target TEXT,
                    config_hash TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS raw_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    method TEXT NOT NULL,
                    url TEXT NOT NULL,
                    params_json TEXT,
                    post_data_hash TEXT,
                    status_code INTEGER,
                    content_type TEXT,
                    body_hash TEXT NOT NULL,
                    body_text TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_body_hash ON raw_responses(body_hash);
                CREATE TABLE IF NOT EXISTS endpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method TEXT NOT NULL,
                    url_pattern TEXT NOT NULL,
                    endpoint_type TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    sample_body_hash TEXT,
                    notes TEXT,
                    UNIQUE(method, url_pattern)
                );
                CREATE TABLE IF NOT EXISTS crawl_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    target TEXT,
                    method TEXT,
                    url TEXT,
                    params_json TEXT,
                    status_code INTEGER,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    list_endpoint TEXT,
                    detail_endpoint TEXT,
                    raw_json TEXT,
                    normalized_json TEXT,
                    content_hash TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    UNIQUE(source_type, source_id)
                );
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    asset_type TEXT,
                    referer_url TEXT,
                    local_path TEXT,
                    sha256 TEXT,
                    status TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS program_library (
                    program_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS school_library (
                    school_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS admission_case_library (
                    case_id TEXT PRIMARY KEY,
                    program_id TEXT NOT NULL,
                    target_school_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def start_run(self, target: str, notes: str = "") -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO crawl_runs(started_at, status, target, notes) VALUES (?, ?, ?, ?)",
                (utc_now(), "running", target, notes),
            )
            return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE crawl_runs SET finished_at = ?, status = ? WHERE id = ?",
                (utc_now(), status, run_id),
            )

    def save_raw_response(
        self,
        *,
        run_id: int | None,
        method: str,
        url: str,
        status_code: int | None,
        content_type: str | None,
        body_text: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        body_hash = sha256_text(body_text)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO raw_responses(
                    run_id, method, url, params_json, status_code, content_type,
                    body_hash, body_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    method,
                    url,
                    json.dumps(params or {}, ensure_ascii=False),
                    status_code,
                    content_type,
                    body_hash,
                    body_text,
                    utc_now(),
                ),
            )
        return body_hash

    def upsert_endpoint(self, method: str, url_pattern: str, endpoint_type: str, body_hash: str | None) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO endpoints(method, url_pattern, endpoint_type, first_seen_at, last_seen_at, sample_body_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(method, url_pattern) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    endpoint_type = excluded.endpoint_type,
                    sample_body_hash = COALESCE(endpoints.sample_body_hash, excluded.sample_body_hash)
                """,
                (method, url_pattern, endpoint_type, now, now, body_hash),
            )

    def save_error(self, *, run_id: int | None, target: str, method: str, url: str, error_type: str, message: str, status_code: int | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO crawl_errors(run_id, target, method, url, status_code, error_type, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, target, method, url, status_code, error_type, message, utc_now()),
            )

    def upsert_source_record(self, source_type: str, source_id: str, raw_json: dict[str, Any], normalized_json: dict[str, Any]) -> None:
        now = utc_now()
        raw_text = json.dumps(raw_json, ensure_ascii=False, sort_keys=True)
        normalized_text = json.dumps(normalized_json, ensure_ascii=False, sort_keys=True)
        content_hash = sha256_text(raw_text)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_records(source_type, source_id, raw_json, normalized_json, content_hash, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_id) DO UPDATE SET
                    raw_json = excluded.raw_json,
                    normalized_json = excluded.normalized_json,
                    content_hash = excluded.content_hash,
                    last_seen_at = excluded.last_seen_at
                """,
                (source_type, source_id, raw_text, normalized_text, content_hash, now, now),
            )

    def upsert_asset(self, url: str, asset_type: str, referer_url: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO assets(url, asset_type, referer_url, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (url, asset_type, referer_url, "listed", utc_now()),
            )

    def upsert_program_library(self, rows: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO program_library(program_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(program_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        str(row["program_id"]),
                        json.dumps(row, ensure_ascii=False, sort_keys=True),
                        row.get("updated_at"),
                    )
                    for row in rows
                ],
            )

    def upsert_school_library(self, rows: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO school_library(school_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(school_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        str(row["school_id"]),
                        json.dumps(row, ensure_ascii=False, sort_keys=True),
                        row.get("updated_at"),
                    )
                    for row in rows
                ],
            )

    def upsert_admission_case_library(self, rows: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO admission_case_library(case_id, program_id, target_school_id, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    program_id = excluded.program_id,
                    target_school_id = excluded.target_school_id,
                    payload_json = excluded.payload_json
                """,
                [
                    (
                        str(row["case_id"]),
                        str(row["program_id"]),
                        str(row["target_school_id"]),
                        json.dumps(row, ensure_ascii=False, sort_keys=True),
                    )
                    for row in rows
                ],
            )
