from xntj_archive.storage import ArchiveStore, archive_name


def test_store_deduplicates_and_records_status(tmp_path) -> None:
    store = ArchiveStore(tmp_path)
    try:
        store.add_url("https://xntj.tv/", "test")
        store.add_url("https://xntj.tv/", "test")
        assert store.pending_urls() == ["https://xntj.tv/"]
        path = store.write_bytes("pages", "https://xntj.tv/", b"hello", ".html")
        store.finish_url("https://xntj.tv/", status=200, content_type="text/html", content_hash="abc", path=path, error=None)
        assert store.summary()["pages"] == {"200": 1}
    finally:
        store.close()


def test_archive_name_is_stable_and_safe() -> None:
    name = archive_name("https://xntj.tv/ep/live-ep0001/?a=1", ".html")
    assert name.startswith("ep--live-ep0001--")
    assert name.endswith(".html")
