"""Refresh legacy project details using the existing shared bounded transport."""
import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import shutil
import time

from .api_crawler import normalize_project_detail, normalize_project_list_item
from .complete import checkpoint, valid_entity
from .referenced_archive import ReferencedArchive, cached_file_valid, referenced_files, referenced_html_assets
from .schema import ProjectRecord
from .storage import append_jsonl, iter_jsonl, read_json, upsert_records, write_json
from .utils import find_asset_urls, utc_now


def reference_set(record):
    return set(record.get("assets", [])) | set(find_asset_urls(json.dumps(record.get("raw", {}), ensure_ascii=False))) | {x["url"] for x in referenced_files(record.get("raw", {}))} | {x["url"] for x in referenced_html_assets(record.get("raw", {}))}


def fresh_record(payload, item, url, crawled_at):
    valid_entity(payload, item["id"])
    record = normalize_project_detail(payload, item, url)
    record.update(crawled_at=crawled_at, canonical_url=url, canonical_url_kind="observed_public_api_record", page_url=f"https://www.dianedu.com/easyStudyDetail?id={item['id']}", detail_freshness="refreshed_this_batch")
    ProjectRecord.model_validate(record)
    return record


async def refresh(root):
    archive = ReferencedArchive(root, 20, 12, True)
    settings = archive.settings
    progress_path = settings.reports_dir / "project_refresh_progress.json"
    projects = read_json(settings.processed_dir / "projects.json", [])
    by_id = {str(x["id"]): x for x in projects}
    plan_path = settings.reports_dir / "project_refresh_plan.json"
    plan = read_json(plan_path, {})
    if not plan:
        target_ids = [x["id"] for x in projects if datetime.fromisoformat(x["crawled_at"]).timestamp() < datetime.fromisoformat(archive.limits["started_at"]).timestamp()]
        plan = {"started_at": utc_now(), "target_ids": target_ids, "original_batch_started_at": archive.limits["started_at"], "deadline_epoch": archive.limits["deadline_epoch"]}
        write_json(plan_path, plan)
    snapshot = settings.reports_dir / "before_project_refresh"
    snapshot.mkdir(exist_ok=True)
    for source in (settings.processed_dir / "projects.json", settings.reports_dir / "completion_audit.json", settings.reports_dir / "completion_acceptance.md"):
        if source.is_file() and not (snapshot / source.name).exists():
            shutil.copy2(source, snapshot / source.name)
    original = {str(x["id"]): x for x in read_json(snapshot / "projects.json", [])}
    done = {}
    for receipt in iter_jsonl(settings.raw_dir / "project_refresh_receipts.jsonl"):
        if receipt.get("record"):
            record = receipt["record"]
            key = record.get("id")
            if key not in plan["target_ids"] or receipt.get("url") != f"https://www.dianedu.com/api/Project/{key}":
                raise RuntimeError("invalid_refresh_recovery_identity")
            if not cached_file_valid(root, receipt):
                append_jsonl(settings.raw_dir / "project_refresh_errors.jsonl", {"project_id": key, "error_type": "invalid_refresh_cache_refetch_required", "checked_at": utc_now()})
                continue
            data = json.loads((root / receipt["local_path"]).read_text(encoding="utf-8"))
            recovered = fresh_record(data, by_id[key], receipt["url"], receipt["downloaded_at"])
            if datetime.fromisoformat(recovered["crawled_at"]) < datetime.fromisoformat(plan["started_at"]):
                raise RuntimeError("refresh_recovery_timestamp_predates_job")
            done[key] = by_id[key] = recovered
    errors = []
    state = {"started_at": plan["started_at"], "targeted": len(plan["target_ids"]), "refreshed": len(done), "status": "running", "errors": errors}
    write_json(progress_path, state)
    resource_progress = read_json(settings.reports_dir / "referenced_progress.json", {})
    resource_progress.update(status="refreshing_project_details", stop_reason=None, updated_at=utc_now())
    write_json(settings.reports_dir / "referenced_progress.json", resource_progress)

    async def query(item):
        receipt = await archive.download_with_retries(item)
        if receipt.get("error_type"):
            append_jsonl(settings.raw_dir / "project_refresh_errors.jsonl", receipt)
            raise RuntimeError(f"snapshot_request_failed:{receipt['error_type']}")
        path = root / receipt["local_path"]
        data = json.loads(path.read_text(encoding="utf-8"))
        return receipt, data

    try:
        listed = {}
        page = 1
        while True:
            receipt, data = await query({"url": "https://www.dianedu.com/api/Project/Search", "method": "POST", "payload": {"Page": page, "Limit": 100}, "kind": "public_json"})
            if not isinstance(data, dict) or not isinstance(data.get("Data"), list) or type(data.get("Count")) is not int or not 0 <= data["Count"] <= 20000:
                raise RuntimeError("invalid_latest_project_list")
            append_jsonl(settings.raw_dir / "project_refresh_list_receipts.jsonl", receipt)
            for item in data["Data"]:
                record = normalize_project_list_item(item)
                if not record["id"]:
                    raise RuntimeError("latest_list_missing_id")
                listed[record["id"]] = record
            if page * 100 >= data["Count"]:
                break
            page += 1
        if len(listed) != data["Count"]:
            raise RuntimeError("latest_list_count_mismatch")
        state.update(latest_list_count=len(listed), latest_list_matches_archive=set(listed) == set(by_id), latest_list_verified_at=utc_now())
        checkpoint(settings.processed_dir / "project_latest_list.json", list(listed.values()))
        if state["latest_list_matches_archive"]:
            checkpoint(settings.processed_dir / "project_list_items.json", list(listed.values()))
        for key in plan["target_ids"]:
            if key in done:
                continue
            receipt, data = await query({"url": f"https://www.dianedu.com/api/Project/{key}", "kind": "public_json", "project_id": key})
            record = fresh_record(data, listed.get(key, by_id[key]), receipt["url"], receipt["downloaded_at"])
            append_jsonl(settings.raw_dir / "project_refresh_receipts.jsonl", {**receipt, "record": record})
            done[key] = by_id[key] = record
            state["refreshed"] = len(done)
            if len(done) % 10 == 0:
                checkpoint(settings.processed_dir / "projects.json", [by_id[x["id"]] for x in projects])
                write_json(progress_path, state)
        state["status"] = "finished"
    except BaseException as exc:
        state.update(status="stopped", stop_reason="time_budget_reached" if isinstance(exc, asyncio.CancelledError) else str(exc))
        errors.append(state["stop_reason"])
        raise
    finally:
        checkpoint(settings.processed_dir / "projects.json", [by_id[x["id"]] for x in projects])
        upsert_records(settings.db_path, "projects", list(by_id.values()), "canonical_url")
        added, removed = set(), set()
        changed = []
        for key in done:
            before, after = reference_set(original[key]), reference_set(done[key])
            added |= after - before
            removed |= before - after
            if before != after:
                changed.append({"project_id": key, "added": sorted(after - before), "removed": sorted(before - after)})
        write_json(settings.reports_dir / "project_reference_changes.json", {"verified_at": utc_now(), "refreshed": len(done), "changed_projects": changed, "added_references": sorted(added), "removed_references": sorted(removed)})
        state.update(finished_at=utc_now(), transferred_bytes=archive.transferred_bytes, added_references=len(added), removed_references=len(removed))
        write_json(progress_path, state)
        coverage = read_json(settings.reports_dir / "completion_coverage.json", {})
        remaining = sum(datetime.fromisoformat(x["crawled_at"]).timestamp() < datetime.fromisoformat(archive.limits["started_at"]).timestamp() for x in by_id.values())
        coverage.update(project_details_reused=remaining, reused_project_details=remaining > 0, current_project_snapshot=remaining == 0 and state.get("latest_list_matches_archive", False), project_refresh=state)
        write_json(settings.reports_dir / "completion_coverage.json", coverage)
        resource_progress = read_json(settings.reports_dir / "referenced_progress.json", {})
        resource_progress["blocked_hosts"] = sorted(archive.blocked_hosts)
        resource_progress["transferred_bytes"] = archive.transferred_bytes
        write_json(settings.reports_dir / "referenced_progress.json", resource_progress)
        await archive.client.aclose()


async def execute(root):
    limits = read_json(root / "reports/resource_limits.json", {})
    try:
        await asyncio.wait_for(refresh(root), max(0, limits["deadline_epoch"] - time.time()))
        archive = ReferencedArchive(root, 20, 12, True)
        try:
            await asyncio.wait_for(archive.run(), max(0, limits["deadline_epoch"] - time.time()))
        except TimeoutError:
            archive.save("stopped", "time_budget_reached")
    except Exception as exc:
        progress = read_json(root / "reports/referenced_progress.json", {})
        progress.update(status="stopped", stop_reason=f"project_refresh:{type(exc).__name__}:{exc}", updated_at=utc_now())
        write_json(root / "reports/referenced_progress.json", progress)
    finally:
        from .finalize_completion import main as finalize
        from .acceptance_inventory import main as reconcile
        finalize()
        reconcile()
        write_json(root / "reports/project_snapshot_finished.json", {"finished_at": utc_now(), "refresh": read_json(root / "reports/project_refresh_progress.json", {})})


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(execute(Path(__file__).resolve().parents[1] / "task_runs/20261014"))
