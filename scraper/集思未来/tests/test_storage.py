from pathlib import Path

from sou_crawler.normalizer import write_csv, write_sqlite


def test_storage_serialization(tmp_path: Path) -> None:
    rows = [
        {
            "record_key": "1",
            "source_url": "https://example.com/api?id=1",
            "canonical_url": "https://example.com/api?id=1",
            "crawled_at": "2026-05-21T00:00:00+00:00",
            "title": "Sample",
            "asset_urls": ["https://example.com/a.pdf"],
            "raw": {"id": 1, "title": "Sample"},
        }
    ]
    csv_path = tmp_path / "records.csv"
    sqlite_path = tmp_path / "records.sqlite"

    write_csv(csv_path, rows)
    write_sqlite(sqlite_path, rows)

    assert "Sample" in csv_path.read_text(encoding="utf-8")
    assert sqlite_path.exists()

