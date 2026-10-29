"""Offline reconciliation of discovered references against saved receipts."""
from collections import Counter
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from .assets import collect_asset_candidates
from .complete_assets import dependencies
from .config import Settings
from .referenced_archive import reference_key, referenced_files, referenced_html_assets, safe_public_url
from .storage import iter_jsonl, read_json, write_csv, write_json
from .utils import find_asset_urls, utc_now


def resume_cohort(initial: list[dict], receipts: list[dict], valid_files: list[dict]) -> dict:
    def key(url):
        return reference_key(url) if safe_public_url(url) else url
    targets = {key(x["url"]) for x in initial}
    attempted = {key(x["url"]) for x in receipts}
    saved = {key(x["url"]) for x in valid_files}
    failed_keys = (targets & attempted) - saved
    receipt_map = {key(x["url"]): x for x in receipts}
    reasons = dict(Counter(receipt_map[x].get("error_type") or "invalid_or_empty_payload" for x in failed_keys))
    return {"initial_unique_targets": len(targets), "processed": len(targets & attempted), "nonempty_saved": len(targets & saved), "processed_without_valid_file": len(failed_keys), "error_categories": reasons, "pending_count": len(targets - attempted), "pending_urls": sorted(targets - attempted)}


def inventory(settings: Settings, receipts: list[dict]) -> dict:
    planned = {}

    def add(item):
        url = item["url"]
        key = reference_key(url) if safe_public_url(url) else url
        planned.setdefault(key, {**item, "url": key})

    for item in collect_asset_candidates(settings):
        add({**item, "kind": "asset"})
    for endpoint in ("Swiper", "Search"):
        add({"url": f"https://www.dianedu.com/api/HomeBanner/{endpoint}", "kind": "public_json"})
    for name in ("projects", "articles", "schools"):
        for record in read_json(settings.processed_dir / f"{name}.json", []):
            for item in referenced_files(record.get("raw", {})):
                add({**item, "source_url": record["source_url"]})
            for item in referenced_html_assets(record.get("raw", {})):
                add({**item, "source_url": record["source_url"]})
            if name == "projects" and record.get("fields", {}).get("FAQGroup"):
                add({"url": f"https://www.dianedu.com/api/Project/GetFaqs?projectId={record['id']}", "kind": "faq", "project_id": record["id"], "source_url": record["source_url"]})
            if name == "schools":
                for url in find_asset_urls(json.dumps(record, ensure_ascii=False)):
                    add({"url": url, "kind": "asset", "source_url": record["source_url"]})
            if name == "articles":
                for key in ("Link", "WechatUrl"):
                    url = record.get("raw", {}).get(key)
                    if isinstance(url, str) and url.startswith(("http://", "https://")):
                        add({"url": url, "kind": "article", "article_id": record["id"], "source_url": record["source_url"]})

    discovery_errors = []
    for record in receipts:
        add(record)
        if not record.get("local_path"):
            continue
        path = (settings.root_dir / record["local_path"]).resolve()
        if not path.is_relative_to(settings.root_dir.resolve()) or not path.is_file():
            discovery_errors.append({"url": record["url"], "error": "missing_or_invalid_local_path"})
            continue
        content_type = record.get("content_type") or ""
        try:
            if "javascript" in content_type or "text/css" in content_type:
                for url in dependencies(path.read_text(encoding="utf-8", errors="replace"), record["final_url"]):
                    add({"url": url, "kind": "asset", "source_url": record["url"]})
            elif record["kind"] in {"faq", "public_json"}:
                data = json.loads(path.read_text(encoding="utf-8"))
                for item in referenced_files(data):
                    add({**item, "source_url": record["url"]})
                for url in find_asset_urls(json.dumps(data, ensure_ascii=False)):
                    add({"url": url, "kind": "asset", "source_url": record["url"]})
            elif record["kind"] == "article" and record.get("body_path"):
                soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")
                body = soup.select_one("#js_content") or soup.select_one("article")
                if body:
                    for img in body.select("img[src], img[data-src]"):
                        value = img.get("data-src") or img.get("src")
                        if value:
                            add({"url": urljoin(record["final_url"], value), "kind": "asset", "source_url": record["url"]})
        except (OSError, ValueError, UnicodeError) as exc:
            discovery_errors.append({"url": record["url"], "error": type(exc).__name__})

    attempted = {reference_key(x["url"]) if safe_public_url(x["url"]) else x["url"] for x in receipts}
    pending = [planned[key] for key in sorted(planned.keys() - attempted)]
    return {"verified_at": utc_now(), "discovered_unique_references": len(planned), "attempted_unique_references": len(attempted), "pending_count": len(pending), "pending_by_kind": dict(Counter(x["kind"] for x in pending)), "pending": pending, "discovery_errors": discovery_errors}


def main():
    root = Path(__file__).resolve().parents[1] / "task_runs/20261014"
    settings = Settings(root_dir=root)
    progress = read_json(settings.reports_dir / "referenced_progress.json", {})
    if progress.get("status") not in {"finished", "stopped"}:
        raise RuntimeError("Resource batch must reach a terminal state before final inventory")
    receipts = read_json(settings.processed_dir / "referenced_manifest.json", [])
    result = inventory(settings, receipts)
    write_json(settings.reports_dir / "pending_references.json", result)
    if result["pending"]:
        write_csv(settings.reports_dir / "pending_references.csv", result["pending"])
    else:
        (settings.reports_dir / "pending_references.csv").write_text("url,kind,source_url\n", encoding="utf-8-sig")
    empty_files = [{**x, "error_type": "empty_payload", "validation_status": "invalid_empty_payload"} for x in receipts if x.get("local_path") and x.get("size_bytes") == 0 and not x.get("error_type")]
    failures = [x for x in receipts if x.get("error_type")] + empty_files
    valid_files = [x for x in receipts if x.get("local_path") and x.get("size_bytes", 0) > 0 and not x.get("error_type")]
    if failures:
        write_csv(settings.reports_dir / "failed_references.csv", failures)
    else:
        (settings.reports_dir / "failed_references.csv").write_text("url,kind,error_type,source_url\n", encoding="utf-8-sig")
    audit = read_json(settings.reports_dir / "completion_audit.json", {})
    refresh = read_json(settings.reports_dir / "project_refresh_progress.json", {})
    snapshot_note = ""
    if refresh:
        from .refresh_projects import reference_set
        from .referenced_archive import cached_file_valid
        refresh_receipts = list(iter_jsonl(settings.raw_dir / "project_refresh_receipts.jsonl"))
        list_receipts = list(iter_jsonl(settings.raw_dir / "project_refresh_list_receipts.jsonl"))
        raw_failures = [x["url"] for x in refresh_receipts + list_receipts if not cached_file_valid(root, x)]
        refreshed_ids = {x["record"]["id"] for x in refresh_receipts if x.get("record")}
        prior = read_json(root.parents[1] / "data/processed/projects.json", [])
        current = read_json(settings.processed_dir / "projects.json", [])
        old_ids = {x["id"] for x in prior} & {x["id"] for x in current}
        refresh.update(legacy_requested_targeted=len(old_ids), legacy_requested_refreshed=len(old_ids & refreshed_ids), legacy_unfinished_ids=sorted(old_ids - refreshed_ids), additional_same_batch_refreshed=len(refreshed_ids - old_ids), raw_response_integrity_failures=raw_failures)
        write_json(settings.reports_dir / "project_refresh_progress.json", refresh)
        audit["project_refresh"] = refresh
        if raw_failures or old_ids - refreshed_ids:
            audit["current_snapshot"] = False
        before = read_json(settings.reports_dir / "before_project_refresh/projects.json", [])
        before_refs = set().union(*(reference_set(x) for x in before))
        current_refs = set().union(*(reference_set(x) for x in current))
        changes = read_json(settings.reports_dir / "project_reference_changes.json", {})
        changes.update(global_added_references=sorted(current_refs - before_refs), global_removed_references=sorted(before_refs - current_refs), current_project_references=len(current_refs), raw_response_integrity_failures=raw_failures)
        write_json(settings.reports_dir / "project_reference_changes.json", changes)
        audit["project_reference_changes"] = changes
        snapshot_note = f"\n原复用旧详情核对：{refresh['legacy_requested_refreshed']}/{refresh['legacy_requested_targeted']}；另外重采本轮详情：{refresh['additional_same_batch_refreshed']}。\n详情/列表原始响应文件校验失败：{len(raw_failures)}。\n当前项目唯一资源引用：{len(current_refs)}；全局新增：{len(current_refs - before_refs)}；全局移除：{len(before_refs - current_refs)}。\n"
        html_refs = {reference_key(x["url"]) for record in current for x in referenced_html_assets(record.get("raw", {})) if safe_public_url(x["url"])}
        receipt_map = {reference_key(x["url"]): x for x in receipts if safe_public_url(x["url"])}
        legacy_refs = {x for x in html_refs if urlparse(x).path == "/_Framework/GetFile"}
        legacy_ids = {value for x in legacy_refs for key, values in parse_qs(urlparse(x).query).items() if key.lower() == "id" for value in values}
        saved_api_ids = {urlparse(x["url"]).path.rsplit("/", 1)[-1] for x in valid_files if "/api/_file/GetFile/" in x["url"]}
        html_summary = {"unique_public_literal_media_references": len(html_refs), "legacy_framework_references": len(legacy_refs), "legacy_unique_file_ids": len(legacy_ids), "legacy_ids_also_saved_via_independently_observed_api_reference": len(legacy_ids & saved_api_ids), "direct_nonempty_saved": sum(bool(receipt_map.get(x, {}).get("local_path")) and receipt_map[x].get("size_bytes", 0) > 0 and not receipt_map[x].get("error_type") for x in html_refs), "direct_errors": dict(Counter(receipt_map[x]["error_type"] for x in html_refs & receipt_map.keys() if receipt_map[x].get("error_type"))), "direct_pending": len(html_refs - receipt_map.keys()), "endpoint_policy": "Literal URLs only; matching file IDs are diagnostic, not evidence that legacy URLs work"}
        audit["project_richtext_resource_audit"] = html_summary
        write_json(settings.reports_dir / "project_richtext_resource_audit.json", html_summary)
        snapshot_note += f"\n项目正文公开媒体引用：{len(html_refs)}；其中旧 Framework 地址：{len(legacy_refs)}。原地址非空保存：{html_summary['direct_nonempty_saved']}；未处理：{html_summary['direct_pending']}；失败分类：{html_summary['direct_errors']}。\n旧地址文件 ID 中已有 {len(legacy_ids & saved_api_ids)} 个通过另一个独立发现的公开 API 引用保存；此对照不代表旧地址有效，也未据此改写 URL。\n"
    audit["reference_inventory"] = {k: v for k, v in result.items() if k != "pending"}
    audit["empty_resource_records"] = empty_files
    audit["validated_nonempty_resource_files"] = len(valid_files)
    audit["validated_resource_kinds"] = dict(Counter(x["kind"] for x in valid_files))
    audit["validated_resource_content_types"] = dict(Counter((x.get("content_type") or "unknown").split(";", 1)[0] for x in valid_files))
    audit["validated_unique_content_hashes"] = len({x["sha256"] for x in valid_files})
    audit["final_error_categories"] = dict(Counter(x["error_type"] for x in failures))
    audit["final_error_count"] = len(failures)
    resume_note = ""
    initial = read_json(settings.reports_dir / "acceptance_12h/pending_references.json", {})
    if initial.get("pending"):
        cohort = resume_cohort(initial["pending"], receipts, valid_files)
        audit["resource_24h_resume_cohort"] = cohort
        write_json(settings.reports_dir / "resource_24h_resume_audit.json", cohort)
        resume_note = f"\n24小时续抓目标核对：原未处理唯一引用 {cohort['initial_unique_targets']}；已处理 {cohort['processed']}；有效非空保存 {cohort['nonempty_saved']}；已处理但未取得有效文件 {cohort['processed_without_valid_file']}；仍未处理 {cohort['pending_count']}。\n本次续抓未成功原因：{cohort['error_categories']}。\n"
    if result["pending_count"] or result["discovery_errors"] or empty_files:
        audit["public_content_archive_complete"] = False
    write_json(settings.reports_dir / "completion_audit.json", audit)
    report = settings.reports_dir / "completion_acceptance.md"
    marker = "\n## 引用集合验收\n"
    base = report.read_text(encoding="utf-8").split(marker, 1)[0]
    if audit.get("project_details_reused") == 0:
        base = base.replace("项目详情复用旧归档：0 条，保留原始时间，不代表当前快照。", "项目详情复用旧归档：0 条；全部1097条已重新采集。")
    budget = read_json(settings.reports_dir / "resource_limits.json", {})
    runtime = read_json(settings.reports_dir / "resource_runtime_current.json", {})
    end_note = f"\n停止原因：{progress.get('stop_reason') or progress.get('status')}；网络阶段结束时间：{progress.get('updated_at')}。\n累计传输：{budget.get('transferred_bytes', 0):,} bytes；上限：{budget.get('max_bytes', 0):,} bytes，总{budget.get('total_hours', 12):g}小时从原起点累计。\n保留未完成分片：{len(audit.get('partial_files', []))} 个，不计为有效保存文件。\n\n| 失败/排除/质量原因 | 数量 |\n|---|---:|\n" + "".join(f"| {key} | {count} |\n" for key, count in audit["final_error_categories"].items()) + f"\n网络实际运行代码快照：{runtime.get('snapshot', 'reports/runtime_code_richtext/')}。正文图片、附件链接及CSS背景图按原地址核对，不改写文件端点。\n"
    report.write_text(base + marker + f"\n本地引用重建：发现 {result['discovered_unique_references']} 个唯一引用；已处理 {result['attempted_unique_references']}；未处理 {result['pending_count']}。\n有效非空文件：{len(valid_files)}；零字节无效文件：{len(empty_files)}（保留原始回执）；最终失败/排除/质量异常：{len(failures)}。\n文件按引用 URL 计数，有效内容 SHA-256 种类：{audit['validated_unique_content_hashes']}；不同 URL 可能保存相同内容。\n未处理清单：pending_references.json / pending_references.csv；失败清单：failed_references.csv。\n" + snapshot_note + resume_note + end_note, encoding="utf-8")
    (settings.archives_dir / "export/README.md").write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
    from .finalize_completion import write_completion_archive
    write_completion_archive(settings)
    print(json.dumps({k: v for k, v in result.items() if k != "pending"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
