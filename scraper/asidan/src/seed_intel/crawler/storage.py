from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from seed_intel.common.hashing import sha256_bytes, stable_text_hash
from seed_intel.extraction.schema import ParsedPage, ProjectRecord


class CrawlStorage:
    def __init__(self, root: Path, batch_id: str) -> None:
        self.root = root
        self.batch_id = batch_id
        self.batch_root = root / "data"

    def _safe_name(self, url: str, suffix: str) -> str:
        return f"{stable_text_hash(url)[:16]}{suffix}"

    def save_html(self, url: str, content: bytes, headers: dict[str, str]) -> Path:
        raw_path = self.batch_root / "bronze" / "raw_html" / self.batch_id / self._safe_name(url, ".html")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(content)
        header_path = self.batch_root / "bronze" / "headers" / self.batch_id / self._safe_name(url, ".json")
        header_path.parent.mkdir(parents=True, exist_ok=True)
        header_path.write_text(json.dumps(headers, ensure_ascii=False, indent=2), encoding="utf-8")
        return raw_path

    def save_asset(self, url: str, content: bytes) -> Path:
        path = self.batch_root / "bronze" / "raw_assets" / self.batch_id / self._safe_name(url, Path(url.split("?", 1)[0]).suffix or ".bin")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def save_page(self, page: ParsedPage) -> Path:
        path = self.batch_root / "silver" / "cleaned_pages" / self.batch_id / self._safe_name(page.source_url, ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(page.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path = self.batch_root / "silver" / "markdown_pages" / self.batch_id / self._safe_name(page.source_url, ".md")
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(page.markdown, encoding="utf-8")
        return path

    def has_html(self, url: str) -> bool:
        path = self.batch_root / "bronze" / "raw_html" / self.batch_id / self._safe_name(url, ".html")
        return path.is_file()

    def has_asset(self, url: str) -> bool:
        suffix = Path(url.split("?", 1)[0]).suffix or ".bin"
        path = self.batch_root / "bronze" / "raw_assets" / self.batch_id / self._safe_name(url, suffix)
        return path.is_file()

    def load_pages(self) -> list[ParsedPage]:
        directory = self.batch_root / "silver" / "cleaned_pages" / self.batch_id
        if not directory.exists():
            return []
        return [ParsedPage.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]

    def save_projects_jsonl(self, records: Iterable[ProjectRecord]) -> Path:
        path = self.batch_root / "gold" / "projects" / f"projects_{self.batch_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(record.model_dump_json() + "\n")
        return path

    def save_errors(self, errors: list[dict[str, object]]) -> Path:
        path = self.batch_root / "gold" / "reports" / f"errors_{self.batch_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for error in errors:
                handle.write(json.dumps(error, ensure_ascii=False) + "\n")
        return path


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
