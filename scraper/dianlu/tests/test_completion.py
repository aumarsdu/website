import pytest

from dianedu_archiver.complete import checkpoint, valid_entity
import json
from dianedu_archiver.complete_assets import dependencies


def test_detail_envelope_and_flat_article():
    assert valid_entity({"Entity": {"ID": "a", "Name": "Example"}}, "a")["Name"] == "Example"
    assert valid_entity({"ID": "a", "Content": "Body"}, "a")["Content"] == "Body"


@pytest.mark.parametrize("payload", [None, [], {}, {"Entity": None}, {"Entity": {"ID": "wrong"}}])
def test_invalid_detail_is_not_counted_as_success(payload):
    with pytest.raises(ValueError):
        valid_entity(payload, "a")


def test_frontend_dependencies_resolve_from_vite_root_and_module():
    assert dependencies('import "./chunk.js"; const x=["assets/style.css"]', "https://www.dianedu.com/assets/main.js") == [
        "https://www.dianedu.com/assets/chunk.js",
        "https://www.dianedu.com/assets/style.css",
    ]


def test_checkpoint_is_readable_and_replaces_complete_snapshot(tmp_path):
    path = tmp_path / "records.json"
    checkpoint(path, [{"id": "a"}])
    checkpoint(path, [{"id": "a"}, {"id": "b"}])
    assert json.loads(path.read_text()) == [{"id": "a"}, {"id": "b"}]
    assert not path.with_suffix(".json.tmp").exists()


def test_css_unquoted_resource_and_data_uri_exclusion():
    assert dependencies('url(../fonts/font.woff2) url(data:abc) url(#icon)', "https://www.dianedu.com/assets/main.css") == ["https://www.dianedu.com/fonts/font.woff2"]


def test_completion_archive_has_school_inventory_receipts_without_media(tmp_path):
    import zipfile
    from dianedu_archiver.config import Settings
    from dianedu_archiver.finalize_completion import write_completion_archive

    settings = Settings(root_dir=tmp_path)
    settings.ensure_dirs()
    export = settings.archives_dir / "export"
    export.mkdir()
    (export / "schools.json").write_text('[{"id":"school-1"}]')
    (settings.processed_dir / "referenced_manifest.json").write_text("[]")
    (settings.reports_dir / "resource_limits.json").write_text('{"max_bytes":20000000000}')
    (settings.raw_dir / "referenced_attempts.jsonl").write_text('{"url":"https://example.com/image.png"}\n')
    (settings.assets_dir / "large.mp4").write_bytes(b"media")
    write_completion_archive(settings)
    write_completion_archive(settings)
    with zipfile.ZipFile(settings.archives_dir / "dianedu_archive_report.zip") as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert "schools.json" in names
        assert "reports/resource_limits.json" in names
        assert "data/processed/referenced_manifest.json" in names
        assert "data/raw/referenced_attempts.jsonl" in names
        assert not any(name.endswith(".mp4") for name in names)
        assert json.loads(archive.read("schools.json"))[0]["id"] == "school-1"
        assert archive.testzip() is None
