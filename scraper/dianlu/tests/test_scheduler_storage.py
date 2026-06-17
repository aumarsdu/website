from argparse import Namespace

from dianedu_archiver.config import load_settings
from dianedu_archiver.normalize import read_table
from dianedu_archiver.scheduler import UrlScheduler
from dianedu_archiver.storage import init_db, upsert_records


def make_settings(tmp_path):
    return load_settings(
        Namespace(
            root_dir=str(tmp_path),
            base_url="https://www.dianedu.com/",
            search_url="https://www.dianedu.com/Search",
            user_agent="AuthorizedDianEduArchiveCrawler/1.0",
            rate_limit=1.0,
            timeout=30.0,
            retries=2,
            concurrency=2,
            max_pages=10,
            dry_run=False,
            verbose=False,
            entry_url=None,
        )
    )


def test_scheduler_dedupes_and_rejects_admin(tmp_path) -> None:
    settings = make_settings(tmp_path)
    scheduler = UrlScheduler(settings, ["https://www.dianedu.com/", "https://www.dianedu.com"])
    assert len(scheduler.seen) == 1
    assert not scheduler.add("https://admin.dianedu.com/")
    assert not scheduler.add("https://example.com/")


def test_sqlite_roundtrip_pages(tmp_path) -> None:
    settings = make_settings(tmp_path)
    settings.ensure_dirs()
    init_db(settings.db_path)
    upsert_records(
        settings.db_path,
        "pages",
        [
            {
                "canonical_url": "https://www.dianedu.com/",
                "source_url": "https://www.dianedu.com/",
                "title": "Home",
                "content_type": "text/html",
                "status_code": 200,
                "html_path": "data/raw/html/index.html",
                "text_hash": "abc",
                "crawled_at": "2026-06-05T00:00:00+00:00",
            }
        ],
        "canonical_url",
    )
    rows = read_table(settings, "pages")
    assert rows[0]["title"] == "Home"
