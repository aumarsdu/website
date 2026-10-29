from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings
from .storage import iter_jsonl, read_json, write_json


def build_report(settings: Settings) -> dict[str, Any]:
    projects = list(iter_jsonl(settings.processed_dir / "projects.jsonl") or [])
    assets = read_json(settings.processed_dir / "asset_manifest.json", [])
    data_quality = read_json(settings.processed_dir / "data_quality_summary.json", {})
    stats = {
        "discovery_logs": _count_jsonl(settings.discovery_dir / "network_logs.jsonl"),
        "list_items": _count_jsonl(settings.raw_dir / "list_items.jsonl"),
        "detail_items": _count_jsonl(settings.raw_dir / "details_raw.jsonl"),
        "normalized_projects": len(projects),
        "downloaded_assets": len(assets or []),
        "data_quality": data_quality,
        "crawl_lists_stats": read_json(settings.reports_dir / "crawl_lists_stats.json", {}),
        "crawl_details_stats": read_json(settings.reports_dir / "crawl_details_stats.json", {}),
        "download_assets_stats": read_json(settings.reports_dir / "download_assets_stats.json", {}),
    }
    write_json(settings.reports_dir / "summary.json", stats)
    _write_report_md(settings.reports_dir / "summary.md", stats)
    return stats


def _count_jsonl(path: Path) -> int:
    return sum(1 for _ in (iter_jsonl(path) or []))


def _write_report_md(path: Path, stats: dict[str, Any]) -> None:
    lines = [
        "# Crawl Report",
        "",
        "## Summary",
        "",
        f"- discovery network logs: {stats['discovery_logs']}",
        f"- list items: {stats['list_items']}",
        f"- detail items: {stats['detail_items']}",
        f"- normalized projects: {stats['normalized_projects']}",
        f"- downloaded assets: {stats['downloaded_assets']}",
        "",
        "## Data Quality",
        "",
    ]
    for key, value in (stats.get("data_quality") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Runtime Stats", ""])
    for key in ["crawl_lists_stats", "crawl_details_stats", "download_assets_stats"]:
        lines.append(f"### {key}")
        value = stats.get(key) or {}
        if not value:
            lines.append("- not run")
        else:
            for stat_key, stat_value in value.items():
                lines.append(f"- {stat_key}: {stat_value}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
