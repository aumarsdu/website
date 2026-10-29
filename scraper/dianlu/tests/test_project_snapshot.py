import pytest

from dianedu_archiver.refresh_projects import fresh_record, reference_set


def test_rich_text_media_preserves_literal_legacy_endpoint():
    refs = reference_set({"raw": {"Description": '<img src="/_Framework/GetFile?Id=x&amp;stream=true"><img data-src="//cdn.dianedu.com/p.png"><video src="/v.mp4" poster="/p.jpg"></video><img src="data:image/png;base64,abc"><a href="/login">login</a>'}})
    assert refs == {"https://www.dianedu.com/_Framework/GetFile?Id=x&stream=true", "https://cdn.dianedu.com/p.png", "https://www.dianedu.com/v.mp4", "https://www.dianedu.com/p.jpg"}


def test_rich_text_attachment_and_css_resource_without_page_navigation():
    refs = reference_set({"raw": {"Description": '<a href="/_Framework/GetFile?id=poster">poster</a><a href="/file.pdf">file</a><a href="/login">login</a><span style="background:url(/word.gif)"></span>'}})
    assert refs == {"https://www.dianedu.com/_Framework/GetFile?id=poster", "https://www.dianedu.com/file.pdf", "https://www.dianedu.com/word.gif"}


def test_fresh_detail_validates_id_and_uses_observed_api_identifier():
    url = "https://www.dianedu.com/api/Project/project-1"
    record = fresh_record({"Entity": {"ID": "project-1", "Name": "Project", "PictureId": "picture-2"}}, {"id": "project-1"}, url, "2026-10-14T14:00:00+00:00")
    assert record["canonical_url"] == url
    assert record["crawled_at"] == "2026-10-14T14:00:00+00:00"
    assert record["detail_freshness"] == "refreshed_this_batch"
    assert "https://www.dianedu.com/api/_file/GetFile/picture-2" in reference_set(record)


def test_wrong_detail_id_cannot_replace_old_record():
    with pytest.raises(ValueError):
        fresh_record({"Entity": {"ID": "wrong", "Name": "Other"}}, {"id": "project-1"}, "https://www.dianedu.com/api/Project/project-1", "2026-10-14T14:00:00+00:00")


def test_reference_delta_tracks_removed_and_added_files():
    before = reference_set({"raw": {"FileId": "old"}})
    after = reference_set({"raw": {"FileId": "new", "PrimaryPictureId": "new"}})
    assert len(after) == 1
    assert after - before == {"https://www.dianedu.com/api/_file/GetFile/new"}
    assert before - after == {"https://www.dianedu.com/api/_file/GetFile/old"}


def test_refresh_updates_json_sqlite_and_accounts_api_bytes(tmp_path, monkeypatch):
    import asyncio
    import json
    import sqlite3
    from datetime import datetime
    import httpx
    from dianedu_archiver import refresh_projects
    from dianedu_archiver.storage import write_json
    from test_referenced_archive import mock_archive, Stream

    async def run():
        calls = []
        def handler(request):
            calls.append((request.method, request.url.path))
            if request.url.path == "/robots.txt":
                return httpx.Response(404, stream=Stream([]))
            data = {"Count": 2, "Data": [{"ID": "old", "Name": "Latest"}, {"ID": "recent", "Name": "Recent"}]} if request.method == "POST" else {"Entity": {"ID": "old", "Name": "Latest", "FileId": "new-file"}}
            return httpx.Response(200, headers={"content-type": "application/json"}, stream=Stream([json.dumps(data).encode()]))
        archive = await mock_archive(tmp_path, handler)
        archive.limits["started_at"] = "2026-10-14T03:03:34+00:00"
        write_json(archive.settings.reports_dir / "resource_limits.json", archive.limits)
        old = fresh_record({"Entity": {"ID": "old", "Name": "Old", "FileId": "old-file"}}, {"id": "old"}, "https://www.dianedu.com/api/Project/old", "2026-06-01T00:00:00+00:00")
        recent = fresh_record({"Entity": {"ID": "recent", "Name": "Recent"}}, {"id": "recent"}, "https://www.dianedu.com/api/Project/recent", "2026-10-14T04:00:00+00:00")
        write_json(archive.settings.processed_dir / "projects.json", [old, recent])
        monkeypatch.setattr(refresh_projects, "ReferencedArchive", lambda *args: archive)
        await refresh_projects.refresh(tmp_path)
        rows = json.loads((archive.settings.processed_dir / "projects.json").read_text())
        assert rows[0]["title"] == "Latest"
        assert rows[1] == recent
        progress = json.loads((archive.settings.reports_dir / "project_refresh_progress.json").read_text())
        assert progress["refreshed"] == progress["targeted"] == 1
        assert progress["latest_list_matches_archive"]
        assert archive.transferred_bytes > 0
        assert ("GET", "/api/Project/recent") not in calls
        conn = sqlite3.connect(archive.settings.db_path)
        assert conn.execute("SELECT count(*) FROM projects").fetchone()[0] == 2
        conn.close()
    asyncio.run(run())
