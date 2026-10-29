"""Bounded public-content completion; preserves the previous archive.

Only replay public search/detail operations found in the site's frontend.
Never traverse account, student, order, application or payment endpoints.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from .api_crawler import normalize_article_item, normalize_project_detail
from .config import Settings
from .fetcher import Fetcher
from .schema import ArticleRecord, ProjectRecord
from .storage import append_jsonl, iter_jsonl, read_json, upsert_records, write_json
from .utils import utc_now

LOGGER = logging.getLogger(__name__)


def checkpoint(path: Path, records: list[dict]) -> None:
    """Publish a complete snapshot atomically for readers and resume."""
    temporary = path.with_suffix(".json.tmp")
    write_json(temporary, records)
    temporary.replace(path)


def valid_entity(payload: object, expected_id: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Detail payload is not an object")
    entity = payload.get("Entity", payload)
    if not isinstance(entity, dict) or str(entity.get("ID")) != str(expected_id):
        raise ValueError("Detail ID missing or mismatched")
    return entity


async def complete(root: Path, previous: Path) -> None:
    settings = Settings(root_dir=root, max_pages=20000, rate_limit=2, timeout=20, retries=2)
    settings.ensure_dirs()
    fetcher = Fetcher(settings)
    errors: list[dict] = []
    coverage: dict = {"started_at": utc_now(), "scope": "public project/article/school content; www.dianedu.com only", "reused_project_details": True}

    async def request(url: str, payload: dict | None = None):
        result = await (fetcher.get(url) if payload is None else fetcher.post_json(url, payload))
        if result.error:
            error = result.error.model_dump()
            errors.append(error)
            append_jsonl(settings.raw_dir / "completion_errors.jsonl", error)
            if result.status_code in {401, 403, 429}:
                raise RuntimeError(f"Access/rate boundary: {result.status_code} {url}")
            return None
        try:
            data = json.loads(result.text or "")
        except ValueError:
            raise RuntimeError(f"Non-JSON public API response: {url}")
        append_jsonl(settings.raw_dir / "completion_responses.jsonl", {"source_url": url, "request": payload, "data": data, "crawled_at": utc_now()})
        return data

    async def listing(kind: str) -> list[dict]:
        url = f"https://www.dianedu.com/api/{kind}/Search"
        items: dict[str, dict] = {}
        page = 1
        while True:
            data = await request(url, {"Page": page, "Limit": 100})
            if not isinstance(data, dict) or not isinstance(data.get("Data"), list) or not isinstance(data.get("Count"), int):
                raise RuntimeError(f"Invalid search envelope: {kind}")
            total = data["Count"]
            if total > settings.max_pages:
                raise RuntimeError(f"Safety cap exceeded: {kind} {total}")
            for item in data["Data"]:
                if not isinstance(item, dict) or not item.get("ID"):
                    raise RuntimeError(f"Missing list item ID: {kind}")
                items[str(item["ID"])] = item
            if page * 100 >= total:
                break
            if not data["Data"]:
                raise RuntimeError(f"Early empty page: {kind} {page}")
            page += 1
        coverage[f"{kind.lower()}_listed"] = len(items)
        coverage[f"{kind.lower()}_server_count"] = total
        if len(items) != total:
            raise RuntimeError(f"List count mismatch: {kind} {len(items)}/{total}")
        write_json(settings.processed_dir / f"{kind.lower()}_list.json", list(items.values()))
        return list(items.values())

    try:
        project_items = read_json(settings.processed_dir / "project_list_items.json", [])
        cached = {str(x["id"]): x for x in read_json(previous / "data/processed/projects.json", []) if x.get("id") and x.get("raw", {}).get("Entity")}
        previous_ids = set(cached)
        # Recover new details from append-only responses even if an older writer
        # was interrupted during publication of its JSON snapshot.
        by_id = {str(x["id"]): x for x in project_items}
        for response in iter_jsonl(settings.raw_dir / "completion_responses.jsonl"):
            url = response.get("source_url", "")
            if "/api/Project/" not in url or response.get("request") is not None:
                continue
            key = url.rsplit("/", 1)[-1]
            if key in by_id:
                valid_entity(response["data"], key)
                record = normalize_project_detail(response["data"], by_id[key], url)
                record["crawled_at"] = response["crawled_at"]
                cached[key] = record
        projects = []
        for item in project_items:
            key = str(item["id"])
            record = cached.get(key)
            if record is None:
                url = f"https://www.dianedu.com/api/Project/{key}"
                data = await request(url)
                if data is None:
                    continue
                valid_entity(data, key)
                record = normalize_project_detail(data, item, url)
                ProjectRecord.model_validate(record)
                cached[key] = record
            projects.append(record)
            if len(projects) % 100 == 0 or len(projects) == len(project_items):
                checkpoint(settings.processed_dir / "projects.json", projects)
        upsert_records(settings.db_path, "projects", projects, "canonical_url")
        coverage["project_listed"] = len(project_items)
        coverage["project_details"] = len(projects)
        coverage["project_details_reused"] = sum(str(x["id"]) in previous_ids for x in projects)
        LOGGER.info("Project coverage: %s/%s", len(projects), len(project_items))

        for kind in ("Article", "School"):
            items = await listing(kind)
            filename = "articles.json" if kind == "Article" else "schools.json"
            cached = {str(x["id"]): x for x in read_json(settings.processed_dir / filename, []) if x.get("id")}
            records = []
            for idx, item in enumerate(items, 1):
                key = str(item["ID"])
                record = cached.get(key)
                if record is None:
                    url = f"https://www.dianedu.com/api/{kind}/{key}"
                    data = await request(url)
                    if data is None:
                        continue
                    entity = valid_entity(data, key)
                    if kind == "Article":
                        record = normalize_article_item({**item, **entity})
                        record["source_url"] = url
                        record["detail_payload"] = data
                        ArticleRecord.model_validate(record)
                    else:
                        record = {"id": key, "source_url": url, "canonical_url": f"https://www.dianedu.com/internationalSchoolDetail?id={key}", "title": entity.get("Name") or entity.get("SchoolName"), "crawled_at": utc_now(), "raw": data}
                    cached[key] = record
                records.append(record)
                checkpoint(settings.processed_dir / filename, records)
                coverage[f"{kind.lower()}_details"] = len(records)
                write_json(settings.reports_dir / "completion_coverage.json", coverage)
                if idx % 10 == 0:
                    LOGGER.info("%s coverage: %s/%s", kind, len(records), len(items))
            if kind == "Article":
                upsert_records(settings.db_path, "articles", records, "canonical_url")
        coverage["finished_at"] = utc_now()
        coverage["status"] = "content_complete" if not errors else "incomplete"
    except Exception as exc:
        coverage["status"] = "blocked"
        coverage["stop_reason"] = str(exc)
        raise
    finally:
        coverage["errors"] = len(errors)
        write_json(settings.reports_dir / "completion_coverage.json", coverage)
        await fetcher.close()


if __name__ == "__main__":
    from .logging_utils import configure_logging
    configure_logging(False)
    base = Path(__file__).resolve().parents[1]
    asyncio.run(complete(base / "task_runs/20261014", base))
