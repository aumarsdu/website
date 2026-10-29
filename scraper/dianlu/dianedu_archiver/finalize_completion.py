"""Validate API coverage and export the independent completion batch."""
from pathlib import Path
import json
from collections import Counter
import sqlite3
import zipfile

from .config import Settings
from .exporter import export_outputs, write_html
from .report import build_report
from .storage import read_json, upsert_records, write_csv, write_json, write_jsonl
from .utils import utc_now


def write_completion_archive(settings: Settings) -> None:
    """Package inspectable records and receipts, leaving large media loose."""
    root = settings.root_dir
    export = settings.archives_dir / "export"
    with zipfile.ZipFile(settings.archives_dir / "dianedu_archive_report.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(export.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(export))
        for name in ("completion_acceptance.md", "completion_audit.json", "completion_coverage.json", "referenced_progress.json", "resource_limits.json", "run_scope.md", "summary.md", "pending_references.json", "pending_references.csv", "failed_references.csv", "project_refresh_plan.json", "project_refresh_progress.json", "project_reference_changes.json", "project_richtext_resource_audit.json", "project_snapshot_runtime_code.sha256", "richtext_runtime_code.sha256"):
            path = settings.reports_dir / name
            if path.is_file():
                archive.write(path, Path("reports") / name)
        for name in ("referenced_manifest.json", "data_quality_summary.json"):
            path = settings.processed_dir / name
            if path.is_file():
                archive.write(path, path.relative_to(root))
        for path in sorted(settings.raw_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root))
        for directory in sorted(settings.reports_dir.glob("runtime_code_*")):
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root))
        runtime_metadata = settings.reports_dir / "resource_runtime_current.json"
        if runtime_metadata.is_file():
            archive.write(runtime_metadata, runtime_metadata.relative_to(root))
        cohort_audit = settings.reports_dir / "resource_24h_resume_audit.json"
        if cohort_audit.is_file():
            archive.write(cohort_audit, cohort_audit.relative_to(root))


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "task_runs/20261014"
    settings = Settings(root_dir=root)
    coverage = read_json(settings.reports_dir / "completion_coverage.json", {})
    references = read_json(settings.processed_dir / "referenced_manifest.json", [])
    referenced_progress = read_json(settings.reports_dir / "referenced_progress.json", {})
    external_bodies = {x["url"]: x for x in references if x.get("body_path")}
    checks = {}
    for filename, listname in (("projects", "project_list_items"), ("articles", "article_list"), ("schools", "school_list")):
        records = read_json(settings.processed_dir / f"{filename}.json", [])
        listed = read_json(settings.processed_dir / f"{listname}.json", [])
        # The legacy /project/{id} and /article/{id} paths were derived, not
        # verified frontend routes. Use the observed API record as identifier.
        if filename in {"projects", "articles"}:
            conn = sqlite3.connect(settings.db_path)
            with conn:
                for record in records:
                    old_url = record["canonical_url"]
                    record["canonical_url"] = record["source_url"]
                    record["canonical_url_kind"] = "observed_public_api_record"
                    if filename == "projects":
                        record["page_url"] = f"https://www.dianedu.com/easyStudyDetail?id={record['id']}"
                    else:
                        record["page_url"] = record.get("raw", {}).get("WechatUrl") or record.get("raw", {}).get("Link")
                    conn.execute(f"UPDATE {filename} SET canonical_url=?, data_json=? WHERE canonical_url=?", (record["canonical_url"], json.dumps(record, ensure_ascii=False), old_url))
            conn.close()
            write_json(settings.processed_dir / f"{filename}.json", records)
        expected = {str(x.get("id") or x.get("ID")) for x in listed}
        actual = {str(x["id"]) for x in records}
        checks[filename] = {"listed": len(listed), "details": len(records), "missing": sorted(expected - actual), "unexpected": sorted(actual - expected), "duplicate_ids": len(records) - len(actual)}
        checks[filename]["invalid_required_fields"] = sum(not x.get("title") or not x.get("source_url") or not x.get("crawled_at") for x in records)
        if filename == "articles":
            for record in records:
                content = record.get("raw", {}).get("Content")
                record["body_html"] = content or None
                # Do not mislabel a list abstract as the article body.
                if not content:
                    record["body_markdown"] = None
                record["content_status"] = "body_returned" if content else "external_reference" if record.get("raw", {}).get("Link") or record.get("raw", {}).get("WechatUrl") else "body_missing"
                if not content:
                    from .referenced_archive import reference_key
                    for key in ("Link", "WechatUrl"):
                        url = record.get("raw", {}).get(key)
                        external = external_bodies.get(reference_key(url)) if url else None
                        if external:
                            record["body_source_url"] = external["url"]
                            record["external_body_path"] = external["body_path"]
                            record["body_markdown"] = (root / external["body_path"]).read_text(encoding="utf-8")
                            record["content_status"] = "external_body_saved"
                            break
            write_json(settings.processed_dir / "articles.json", records)
            upsert_records(settings.db_path, "articles", records, "canonical_url")
            checks[filename]["body_returned"] = sum(x["content_status"] == "body_returned" for x in records)
            checks[filename]["external_reference"] = sum(x["content_status"] == "external_reference" for x in records)
            checks[filename]["external_body_saved"] = sum(x["content_status"] == "external_body_saved" for x in records)
        if filename == "schools":
            conn = sqlite3.connect(settings.db_path)
            with conn:
                conn.execute("CREATE TABLE IF NOT EXISTS schools (id TEXT PRIMARY KEY, source_url TEXT NOT NULL, crawled_at TEXT NOT NULL, data_json TEXT NOT NULL)")
                conn.executemany("INSERT OR REPLACE INTO schools VALUES (?,?,?,?)", [(x["id"], x["source_url"], x["crawled_at"], json.dumps(x, ensure_ascii=False)) for x in records])
            conn.close()
    api_complete = all(x["listed"] == x["details"] and not x["missing"] and not x["unexpected"] and not x["duplicate_ids"] and not x["invalid_required_fields"] for x in checks.values()) and coverage.get("status") == "content_complete"
    assets = read_json(settings.reports_dir / "asset_coverage.json", {})
    if referenced_progress:
        assets = {"downloaded": referenced_progress.get("downloaded", 0), "failed": referenced_progress.get("errors", 0), "remaining_queue": referenced_progress.get("queued", 0), "transferred_bytes": referenced_progress.get("transferred_bytes", 0)}
    audit = {"verified_at": utc_now(), "public_api_coverage_complete": api_complete, "checks": checks, "assets": assets, "project_details_reused": coverage.get("project_details_reused"), "current_snapshot": coverage.get("current_project_snapshot", False), "whole_site_offline_complete": False, "limitations": ["Project snapshot spans the recorded per-detail crawl timestamps", "External article bodies and external resources require expanded scope", "Account, student, order, payment, application and admin endpoints excluded"]}
    audit["project_refresh"] = read_json(settings.reports_dir / "project_refresh_progress.json", {})
    audit["current_snapshot"] = audit["current_snapshot"] and audit["project_refresh"].get("status") == "finished"
    audit["project_reference_changes"] = read_json(settings.reports_dir / "project_reference_changes.json", {})
    audit["referenced_resources"] = referenced_progress
    audit["resource_budget"] = read_json(settings.reports_dir / "resource_limits.json", {})
    audit["saved_resource_bytes"] = sum(x.get("size_bytes", 0) for x in references if x.get("local_path"))
    audit["saved_resource_kinds"] = dict(Counter(x["kind"] for x in references if x.get("local_path")))
    audit["saved_resource_content_types"] = dict(Counter((x.get("content_type") or "unknown").split(";", 1)[0] for x in references if x.get("local_path")))
    audit["partial_files"] = [str(x.relative_to(root)) for x in settings.assets_dir.glob("*.part")]
    audit["resource_error_categories"] = dict(Counter(x["error_type"] for x in references if x.get("error_type")))
    audit["public_content_archive_complete"] = api_complete and referenced_progress.get("status") == "finished" and referenced_progress.get("errors") == 0 and checks["articles"].get("external_reference") == 0
    audit["limitations"][1] = "External-reference access denials and missing bodies are retained as failures; no bypass"
    audit["cached_file_integrity_failures"] = []
    from .referenced_archive import cached_file_valid
    for record in references:
        if record.get("local_path") and not cached_file_valid(root, record):
            audit["cached_file_integrity_failures"].append(record["url"])
    if audit["cached_file_integrity_failures"]:
        audit["public_content_archive_complete"] = False
    conn = sqlite3.connect(settings.db_path)
    audit["sqlite_integrity"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    write_json(settings.reports_dir / "completion_audit.json", audit)
    build_report(settings)
    export_outputs(settings)
    schools = read_json(settings.processed_dir / "schools.json", [])
    export = settings.archives_dir / "export"
    write_json(export / "schools.json", schools)
    write_jsonl(export / "schools.jsonl", schools)
    if schools:
        write_csv(export / "schools.csv", schools)
    lines = ["# 点路教育公开内容续抓验收", "", f"核验时间：{audit['verified_at']}", "", "| 数据集 | 列表发现 | 已归档详情 | 缺失 |", "|---|---:|---:|---:|"]
    for name, check in checks.items():
        lines.append(f"| {name} | {check['listed']} | {check['details']} | {len(check['missing'])} |")
    budget = audit["resource_budget"]
    total_hours = budget.get("total_hours", 6)
    max_gb = budget.get("max_bytes", 20000000000) / 1000 ** 3
    lines.extend(["", f"公开接口覆盖核验：{'通过' if api_complete else '未通过'}。", f"项目详情复用旧归档：{audit['project_details_reused']} 条，保留原始时间，不代表当前快照。", f"主站正文：{checks['articles'].get('body_returned', 0)} 条；外域正文已保存：{checks['articles'].get('external_body_saved', 0)} 条；外域正文待获取：{checks['articles'].get('external_reference', 0)} 条。", f"引用文件已下载：{assets.get('downloaded', 0)}；失败/排除：{assets.get('failed', 0)}；剩余队列（未去重）：{assets.get('remaining_queue', 0)}。", f"公开内容归档完整核验：{'通过' if audit['public_content_archive_complete'] else '未通过'}。", "", f"资源范围已扩展到主站直接引用的公开文章与资源，包含视频，上限{max_gb:g} GB、{total_hours:g}小时（从原始起点累计）。", "robots/鉴权/验证码拒绝或资源上限均保留为未完成，不绕过。", "后台、账户、学生资料、订单、支付及申请接口均排除。", "大媒体保留在 data/assets/，不重复塞入 ZIP。", "", "详见 completion_audit.json、completion_coverage.json、referenced_progress.json。"])
    report = settings.reports_dir / "completion_acceptance.md"
    if audit["project_refresh"]:
        refresh = audit["project_refresh"]
        lines.extend(["", f"本次项目详情刷新：{refresh.get('refreshed', 0)}/{refresh.get('targeted', 0)}；刷新状态：{refresh.get('status')}。", f"最新项目列表数量：{refresh.get('latest_list_count')}；ID集合一致：{refresh.get('latest_list_matches_archive')}。", f"当前项目详情快照验收：{'通过' if audit['current_snapshot'] else '未通过'}（按各详情采集时间形成，非同时刻原子快照）。", f"项目内引用变化去重：新增 {refresh.get('added_references', 0)}；移除 {refresh.get('removed_references', 0)}；全局变化见引用集合验收（历史文件保留）。"])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (export / "README.md").write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
    write_html(export / "index.html", {name: read_json(export / f"{name}.json", []) for name in ("projects", "articles", "schools", "pages", "filters", "hot_search_terms", "assets")})
    write_completion_archive(settings)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
