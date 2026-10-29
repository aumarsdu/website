from __future__ import annotations

from typing import Any
import json
import sqlite3

from .config import Settings
from .storage import write_csv, write_json, write_jsonl


def normalize(settings: Settings) -> None:
    records = {
        "projects": read_table(settings, "projects"),
        "articles": read_table(settings, "articles"),
        "pages": read_table(settings, "pages"),
        "filters": read_table(settings, "filters"),
        "hot_search_terms": read_table(settings, "hot_search_terms"),
        "assets": read_table(settings, "assets"),
    }
    for name, items in records.items():
        write_json(settings.processed_dir / f"{name}.normalized.json", items)
        write_jsonl(settings.processed_dir / f"{name}.normalized.jsonl", items)
        if items:
            write_csv(settings.processed_dir / f"{name}.normalized.csv", flatten_records(items))
    summary = {
        name: len(items)
        for name, items in records.items()
    }
    summary["data_quality"] = build_quality_summary(records)
    write_json(settings.processed_dir / "data_quality_summary.json", summary)


def read_table(settings: Settings, table: str) -> list[dict[str, Any]]:
    if not settings.db_path.exists():
        return []
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        data_json = item.pop("data_json", None)
        if data_json:
            try:
                data = json.loads(data_json)
                data.update({k: v for k, v in item.items() if k not in data or data.get(k) in (None, "")})
                out.append(data)
            except json.JSONDecodeError:
                out.append(item)
        else:
            out.append(item)
    return out


def flatten_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        for key, value in record.items():
            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
            else:
                row[key] = value
        flattened.append(row)
    return flattened


def build_quality_summary(records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    projects = records.get("projects", [])
    articles = records.get("articles", [])
    return {
        "projects_without_title": sum(1 for item in projects if not item.get("title")),
        "projects_without_category": sum(1 for item in projects if not item.get("category")),
        "articles_without_body": sum(1 for item in articles if not item.get("body_markdown")),
        "assets_without_local_file": sum(1 for item in records.get("assets", []) if not item.get("local_path")),
    }
