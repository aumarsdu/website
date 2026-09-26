#!/usr/bin/env python3
"""Audit SOU crawl scope, completeness, and organized folder placement."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sou_crawler.config import DEFAULT_USER_AGENT, PROJECT_ROOT, SITE_TARGETS
from sou_crawler.full_refresh import (
    RefreshOptions,
    SiteSpec,
    build_domestic_seeds,
    build_sou_tools_seeds,
    crawl_list_pages,
    record_id_of,
)
from sou_crawler.organizer import make_component
from sou_crawler.utils import deep_find_asset_urls, iter_jsonl, read_json, write_json


ALLOWED_SOURCE_HOSTS = {
    "sou-tools.gecacademy.cn",
    "domestic.gecacademy.cn",
    "sou-m.gecacademy.cn",
    "gec-api.gecacademy.cn",
}
ALLOWED_ASSET_HOSTS = {
    "gecacademy.oss-cn-beijing.aliyuncs.com",
    "gec-download.oss-cn-beijing.aliyuncs.com",
    "cdn.gecacademy.cn",
}
SITE_LABELS = {
    "sou_tools": "海外教授",
    "domestic": "华人教授",
}


@dataclass
class LocalInventory:
    detail_ids: dict[str, set[str]] = field(default_factory=lambda: {"sou_tools": set(), "domestic": set()})
    organized_ids: dict[str, set[str]] = field(default_factory=lambda: {"sou_tools": set(), "domestic": set()})
    organized_paths: dict[str, list[str]] = field(default_factory=dict)
    placement_issues: list[dict[str, Any]] = field(default_factory=list)
    non_scope_items: list[dict[str, Any]] = field(default_factory=list)
    external_asset_hosts: dict[str, int] = field(default_factory=dict)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit crawl scope, completeness, and organized paths.")
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime("%Y%m%d-scope-audit"),
        help="Audit run identifier.",
    )
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "output" / "audit")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument(
        "--delete-non-scope",
        action="store_true",
        help="Delete only generated organized topic folders that the audit classifies as non-scope.",
    )
    args = parser.parse_args(argv)

    options = RefreshOptions(
        run_id=args.run_id,
        output_root=args.output_root,
        user_agent=args.user_agent,
        timeout=args.timeout,
        retries=args.retries,
        rate_limit=args.rate_limit,
        concurrency=args.concurrency,
        max_pages=args.max_pages,
        max_details=0,
        download_assets=False,
    )
    asyncio.run(run_audit(options, delete_non_scope=args.delete_non_scope))
    return 0


async def run_audit(options: RefreshOptions, *, delete_non_scope: bool = False) -> None:
    run_dir = options.output_root / options.run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite an existing audit directory: {run_dir}")
    run_dir.mkdir(parents=True)

    current = await collect_current_scope(run_dir, options)
    inventory = build_local_inventory(exclude_roots={run_dir, options.output_root})
    deleted = delete_non_scope_generated_items(inventory.non_scope_items) if delete_non_scope else []

    sites: dict[str, dict[str, Any]] = {}
    for site, current_ids in current.items():
        detail_ids = inventory.detail_ids.get(site, set())
        organized_ids = inventory.organized_ids.get(site, set())
        missing_detail = sorted(current_ids - detail_ids)
        missing_organized = sorted(current_ids - organized_ids)
        sites[site] = {
            "label": SITE_LABELS[site],
            "current_ids": len(current_ids),
            "local_detail_ids": len(detail_ids),
            "local_organized_ids": len(organized_ids),
            "missing_detail_count": len(missing_detail),
            "missing_organized_count": len(missing_organized),
            "missing_detail_ids": missing_detail,
            "missing_organized_ids": missing_organized,
            "complete": not missing_detail and not missing_organized,
        }

    all_topics_collected = all(site["complete"] for site in sites.values())
    all_current_topics_have_organized_dir = all(
        site["missing_organized_count"] == 0 for site in sites.values()
    )
    summary = {
        "run_id": options.run_id,
        "scope": {
            "sou_tools": "https://sou-tools.gecacademy.cn/",
            "domestic": "https://domestic.gecacademy.cn/",
            "supporting_hosts": sorted(ALLOWED_SOURCE_HOSTS | ALLOWED_ASSET_HOSTS),
        },
        "sites": sites,
        "placement_issue_count": len(inventory.placement_issues),
        "placement_issues": inventory.placement_issues,
        "non_scope_count": len(inventory.non_scope_items),
        "non_scope_items": inventory.non_scope_items,
        "external_asset_hosts": dict(sorted(inventory.external_asset_hosts.items())),
        "deleted_non_scope_items": deleted,
        "all_topics_collected": all_topics_collected,
        "all_topics_correctly_placed": all_current_topics_have_organized_dir
        and not inventory.placement_issues,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_dir / "scope_completeness_audit.json", summary)
    write_markdown(run_dir / "scope_completeness_audit.md", summary)
    print(json.dumps(compact_summary(summary), ensure_ascii=False, indent=2))


async def collect_current_scope(run_dir: Path, options: RefreshOptions) -> dict[str, set[str]]:
    target_by_name = {target.name: target for target in SITE_TARGETS}
    specs = [
        SiteSpec(
            name="sou_tools",
            base_url=target_by_name["sou_tools"].base_url,
            seeds=build_sou_tools_seeds(),
        ),
        SiteSpec(
            name="domestic",
            base_url=target_by_name["domestic"].base_url,
            seeds=build_domestic_seeds(),
        ),
    ]
    current: dict[str, set[str]] = {}
    for spec in specs:
        site_dir = run_dir / "current_scope" / spec.name
        for subdir in ("raw", "reports"):
            (site_dir / subdir).mkdir(parents=True, exist_ok=True)
        await crawl_list_pages(spec, site_dir, options)
        current[spec.name] = collect_list_ids(site_dir / "raw" / "list_records.jsonl")
    return current


def collect_list_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    for row in iter_jsonl(path):
        record = row.get("record") if isinstance(row, dict) else None
        if isinstance(record, dict):
            record_id = record_id_of(record)
            if record_id:
                ids.add(record_id)
    return ids


def build_local_inventory(*, exclude_roots: set[Path] | None = None) -> LocalInventory:
    inventory = LocalInventory()
    exclude_roots = {path.resolve() for path in (exclude_roots or set())}
    for path in PROJECT_ROOT.rglob("raw/detail_responses.jsonl"):
        if is_excluded(path, exclude_roots):
            continue
        site = infer_site_from_path(path)
        if site not in inventory.detail_ids:
            continue
        for row in iter_jsonl(path):
            payload = row.get("payload") if isinstance(row, dict) else None
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, dict):
                record_id = str(data.get("id") or row.get("id") or "")
                if record_id:
                    inventory.detail_ids[site].add(record_id)
            collect_non_scope_from_row(inventory, path, row)

    for detail_path in PROJECT_ROOT.rglob("organized_by_site/**/详情页信息.json"):
        if is_excluded(detail_path, exclude_roots):
            continue
        info = read_json(detail_path, {})
        if not isinstance(info, dict):
            continue
        record_id = str(info.get("id") or "")
        site = infer_site_from_path(detail_path) or infer_site_from_detail_info(info)
        if site in inventory.organized_ids and record_id:
            inventory.organized_ids[site].add(record_id)
            inventory.organized_paths.setdefault(record_id, []).append(str(detail_path.parent))
        issue = placement_issue(detail_path, info)
        if issue:
            inventory.placement_issues.append(issue)
        collect_non_scope_from_detail_info(inventory, detail_path, info)
    return inventory


def is_excluded(path: Path, exclude_roots: set[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved == root or root in resolved.parents for root in exclude_roots)


def infer_site_from_path(path: Path) -> str | None:
    parts = path.parts
    if "domestic" in parts or "output_domestic" in parts:
        return "domestic"
    if "sou_tools" in parts:
        return "sou_tools"
    try:
        relative = path.relative_to(PROJECT_ROOT)
    except ValueError:
        return None
    if relative.parts[:2] == ("output", "raw") or relative.parts[:2] == ("output", "organized_by_site"):
        return "sou_tools"
    return None


def infer_site_from_detail_info(info: dict[str, Any]) -> str | None:
    for url in deep_find_asset_urls(info):
        host = urlsplit(url).netloc.lower()
        if "domestic" in host:
            return "domestic"
    list_record = info.get("list_record") if isinstance(info.get("list_record"), dict) else {}
    detail_record = info.get("detail_record") if isinstance(info.get("detail_record"), dict) else {}
    type_id = list_record.get("typeId") or detail_record.get("typeId")
    if type_id in (None, ""):
        return None
    return "sou_tools"


def placement_issue(detail_path: Path, info: dict[str, Any]) -> dict[str, Any] | None:
    try:
        after_root = detail_path.parent.relative_to(next(parent for parent in detail_path.parents if parent.name == "organized_by_site"))
    except (StopIteration, ValueError):
        return {"path": str(detail_path), "reason": "not_under_organized_by_site"}
    parts = after_root.parts
    if len(parts) < 3:
        return {"path": str(detail_path), "reason": "path_depth_less_than_category_direction_topic"}

    expected_category = make_component(info.get("category"), fallback="未归类")
    expected_direction = make_component(info.get("direction"), fallback="未分方向")
    expected_topic = make_component(info.get("title") or info.get("id"), fallback=str(info.get("id") or "untitled"), max_bytes=180)
    actual_category, actual_direction, actual_topic = parts[0], parts[1], parts[2]
    if actual_category != expected_category:
        return {
            "path": str(detail_path),
            "reason": "category_mismatch",
            "expected": expected_category,
            "actual": actual_category,
        }
    if actual_direction != expected_direction:
        return {
            "path": str(detail_path),
            "reason": "direction_mismatch",
            "expected": expected_direction,
            "actual": actual_direction,
        }
    if not actual_topic.startswith(expected_topic):
        return {
            "path": str(detail_path),
            "reason": "topic_folder_mismatch",
            "expected_prefix": expected_topic,
            "actual": actual_topic,
        }
    return None


def collect_non_scope_from_row(inventory: LocalInventory, path: Path, row: Any) -> None:
    if not isinstance(row, dict):
        return
    for key in ("source_url", "api"):
        value = row.get(key)
        if isinstance(value, str):
            add_non_scope_url(inventory, path, value, "source")
    meta = row.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("url"), str):
        add_non_scope_url(inventory, path, str(meta["url"]), "source")
    for url in deep_find_asset_urls(row):
        collect_asset_host(inventory, url)


def collect_non_scope_from_detail_info(inventory: LocalInventory, path: Path, info: dict[str, Any]) -> None:
    for url in deep_find_asset_urls(info):
        collect_asset_host(inventory, url)


def add_non_scope_url(inventory: LocalInventory, path: Path, url: str, role: str) -> None:
    host = urlsplit(url).netloc.lower()
    if not host:
        return
    allowed = ALLOWED_SOURCE_HOSTS | ALLOWED_ASSET_HOSTS
    if host not in allowed:
        inventory.non_scope_items.append({"path": str(path), "url": url, "host": host, "role": role})


def collect_asset_host(inventory: LocalInventory, url: str) -> None:
    host = urlsplit(url).netloc.lower()
    if not host or host in ALLOWED_ASSET_HOSTS:
        return
    inventory.external_asset_hosts[host] = inventory.external_asset_hosts.get(host, 0) + 1


def delete_non_scope_generated_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deleted: list[dict[str, Any]] = []
    for item in items:
        path = Path(str(item.get("path") or ""))
        topic_dir = topic_dir_from_generated_path(path)
        if topic_dir is None or not topic_dir.exists():
            continue
        shutil.rmtree(topic_dir)
        deleted.append({**item, "deleted": str(topic_dir)})
    return deleted


def topic_dir_from_generated_path(path: Path) -> Path | None:
    if path.name != "详情页信息.json":
        return None
    if "organized_by_site" not in path.parts:
        return None
    return path.parent


def compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": summary["run_id"],
        "all_topics_collected": summary["all_topics_collected"],
        "all_topics_correctly_placed": summary["all_topics_correctly_placed"],
        "sites": {
            site: {
                "current_ids": data["current_ids"],
                "missing_detail_count": data["missing_detail_count"],
                "missing_organized_count": data["missing_organized_count"],
                "complete": data["complete"],
            }
            for site, data in summary["sites"].items()
        },
        "placement_issue_count": summary["placement_issue_count"],
        "non_scope_count": summary["non_scope_count"],
        "deleted_non_scope_items": len(summary["deleted_non_scope_items"]),
        "external_asset_hosts": summary["external_asset_hosts"],
    }


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Scope Completeness Audit",
        "",
        "## Conclusion",
        "",
        f"- all_topics_collected: `{summary['all_topics_collected']}`",
        f"- all_topics_correctly_placed: `{summary['all_topics_correctly_placed']}`",
        f"- placement_issue_count: `{summary['placement_issue_count']}`",
        f"- non_scope_count: `{summary['non_scope_count']}`",
        f"- deleted_non_scope_items: `{len(summary['deleted_non_scope_items'])}`",
        "",
        "## Scope",
        "",
        "- 海外教授: `https://sou-tools.gecacademy.cn/`",
        "- 华人教授: `https://domestic.gecacademy.cn/`",
        "",
        "## Sites",
        "",
    ]
    for site, data in summary["sites"].items():
        lines.extend(
            [
                f"### {data['label']} ({site})",
                "",
                f"- current_ids: `{data['current_ids']}`",
                f"- local_detail_ids: `{data['local_detail_ids']}`",
                f"- local_organized_ids: `{data['local_organized_ids']}`",
                f"- missing_detail_count: `{data['missing_detail_count']}`",
                f"- missing_organized_count: `{data['missing_organized_count']}`",
                "",
            ]
        )
    if summary["placement_issues"]:
        lines.extend(["## Placement Issues", ""])
        for issue in summary["placement_issues"][:100]:
            lines.append(f"- `{issue.get('reason')}`: `{issue.get('path')}`")
        lines.append("")
    if summary["non_scope_items"]:
        lines.extend(["## Non-Scope Items", ""])
        for item in summary["non_scope_items"][:100]:
            lines.append(f"- `{item.get('host')}` in `{item.get('path')}`")
        lines.append("")
    if summary["external_asset_hosts"]:
        lines.extend(["## External Asset Hosts", ""])
        for host, count in sorted(summary["external_asset_hosts"].items()):
            lines.append(f"- `{host}`: `{count}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
