import json

from dianedu_archiver.acceptance_inventory import inventory
from dianedu_archiver.config import Settings


def test_resume_cohort_counts_canonical_targets_and_failed_or_pending_separately():
    from dianedu_archiver.acceptance_inventory import resume_cohort
    initial = [{"url": "https://www.dianedu.com/a.png#one"}, {"url": "https://www.dianedu.com/a.png#two"}, {"url": "https://www.dianedu.com/b.png"}, {"url": "https://www.dianedu.com/c.png"}]
    saved = {"url": "https://www.dianedu.com/a.png", "local_path": "a.png", "size_bytes": 1}
    result = resume_cohort(initial, [saved, {"url": "https://www.dianedu.com/b.png", "error_type": "http_404"}], [saved])
    assert result == {"initial_unique_targets": 3, "processed": 2, "nonempty_saved": 1, "processed_without_valid_file": 1, "error_categories": {"http_404": 1}, "pending_count": 1, "pending_urls": ["https://www.dianedu.com/c.png"]}


def test_offline_inventory_finds_nested_faq_file_without_network_or_budget_change(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No network client during offline inventory")))
    settings = Settings(root_dir=tmp_path)
    settings.ensure_dirs()
    budget = settings.reports_dir / "resource_limits.json"
    budget.write_text('{"transferred_bytes":123,"deadline_epoch":456}')
    project = {"id": "project-1", "source_url": "https://www.dianedu.com/api/Project/GetDetail/project-1", "canonical_url": "https://www.dianedu.com/api/Project/GetDetail/project-1", "fields": {"FAQGroup": "group-1"}, "raw": {"FileId": "file-a", "PrimaryPictureId": "file-a"}}
    (settings.processed_dir / "projects.json").write_text(json.dumps([project]))
    faq_url = "https://www.dianedu.com/api/Project/GetFaqs?projectId=project-1"
    faq_path = settings.assets_dir / "faq.json"
    faq_path.write_text('{"Nested":{"FileId":"file-b"}}')
    receipts = [
        {"url": "https://www.dianedu.com/api/_file/GetFile/file-a", "kind": "asset", "error_type": "http_404"},
        {"url": faq_url, "kind": "faq", "local_path": str(faq_path.relative_to(tmp_path)), "content_type": "application/json"},
    ]
    result = inventory(settings, receipts)
    assert result["attempted_unique_references"] == 2
    assert result["pending_count"] == 3  # two home responses and the nested file
    assert "https://www.dianedu.com/api/_file/GetFile/file-b" in {x["url"] for x in result["pending"]}
    assert not result["discovery_errors"]
    assert budget.read_text() == '{"transferred_bytes":123,"deadline_epoch":456}'


def test_failed_article_is_attempted_and_fragment_aliases_are_deduplicated(tmp_path):
    settings = Settings(root_dir=tmp_path)
    settings.ensure_dirs()
    article = {"id": "article-1", "source_url": "https://www.dianedu.com/api/Article/GetDetail/article-1", "raw": {"Link": "https://example.com/article#one", "WechatUrl": "https://example.com/article#two"}}
    (settings.processed_dir / "articles.json").write_text(json.dumps([article]))
    result = inventory(settings, [{"url": "https://example.com/article", "kind": "article", "error_type": "robots_disallowed"}])
    assert result["attempted_unique_references"] == 1
    assert result["discovered_unique_references"] == 3
    assert result["pending_by_kind"] == {"public_json": 2}


def test_final_inventory_flags_empty_http_200_without_rewriting_receipts(tmp_path, monkeypatch):
    import hashlib
    from dianedu_archiver import acceptance_inventory, finalize_completion
    monkeypatch.setattr(acceptance_inventory, "__file__", str(tmp_path / "dianedu_archiver/acceptance_inventory.py"))
    monkeypatch.setattr(finalize_completion, "write_completion_archive", lambda settings: None)
    settings = Settings(root_dir=tmp_path / "task_runs/20261014")
    settings.ensure_dirs()
    (settings.archives_dir / "export").mkdir()
    (settings.reports_dir / "referenced_progress.json").write_text('{"status":"stopped"}')
    (settings.reports_dir / "completion_acceptance.md").write_text("# Original report\n")
    records = []
    for name, payload in (("empty", b""), ("valid", b"content")):
        path = settings.assets_dir / f"{name}.bin"
        path.write_bytes(payload)
        records.append({"url": f"https://www.dianedu.com/api/_file/GetFile/{name}", "kind": "asset", "status_code": 200, "local_path": str(path.relative_to(settings.root_dir)), "content_type": "application/octet-stream", "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    for endpoint in ("Swiper", "Search"):
        path = settings.assets_dir / f"{endpoint}.json"
        path.write_bytes(b"{}")
        records.append({"url": f"https://www.dianedu.com/api/HomeBanner/{endpoint}", "kind": "public_json", "local_path": str(path.relative_to(settings.root_dir)), "content_type": "application/json", "size_bytes": 2, "sha256": hashlib.sha256(b"{}").hexdigest()})
    (settings.reports_dir / "pending_references.csv").write_text("obsolete pending rows\n")
    manifest = settings.processed_dir / "referenced_manifest.json"
    manifest.write_text(json.dumps(records))
    before = manifest.read_bytes()
    acceptance_inventory.main()
    acceptance_inventory.main()
    audit = json.loads((settings.reports_dir / "completion_audit.json").read_text())
    assert audit["validated_nonempty_resource_files"] == 3
    assert audit["final_error_categories"] == {"empty_payload": 1}
    assert audit["empty_resource_records"][0]["status_code"] == 200
    assert manifest.read_bytes() == before
    assert (settings.reports_dir / "completion_acceptance.md").read_text().count("## 引用集合验收") == 1
    assert "empty_payload" in (settings.reports_dir / "failed_references.csv").read_text()
    assert audit["reference_inventory"]["pending_count"] == 0
    assert (settings.reports_dir / "pending_references.csv").read_text(encoding="utf-8-sig") == "url,kind,source_url\n"
