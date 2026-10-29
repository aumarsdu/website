from __future__ import annotations

import sqlite3
from pathlib import Path


def init_sqlite_db(root: Path) -> Path:
    db_path = root / "data" / "seed_intel.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = Path(__file__).with_name("schema.sql")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
    return db_path
