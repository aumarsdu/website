from __future__ import annotations

from .config import Settings
from .normalize import read_table
from .storage import read_json, write_json


def build_report(settings: Settings) -> None:
    datasets = {
        "pages": read_table(settings, "pages"),
        "projects": read_table(settings, "projects"),
        "articles": read_table(settings, "articles"),
        "filters": read_table(settings, "filters"),
        "hot_search_terms": read_table(settings, "hot_search_terms"),
        "assets": read_table(settings, "assets"),
    }
    quality = read_json(settings.processed_dir / "data_quality_summary.json", {})
    summary = {
        "target": settings.base_url,
        "scope": "www.dianedu.com only; admin.dianedu.com excluded",
        "user_agent": settings.user_agent,
        "counts": {name: len(items) for name, items in datasets.items()},
        "quality": quality,
        "outputs": {
            "sqlite": str(settings.db_path),
            "processed_dir": str(settings.processed_dir),
            "archive_zip": str(settings.archives_dir / "dianedu_archive_report.zip"),
        },
    }
    write_json(settings.reports_dir / "summary.json", summary)
    lines = [
        "# DianEdu Crawl Summary",
        "",
        f"- target: `{summary['target']}`",
        f"- scope: `{summary['scope']}`",
        f"- user-agent: `{summary['user_agent']}`",
        "",
        "## Counts",
        "",
    ]
    for name, count in summary["counts"].items():
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Compliance", "", "- 不抓取 admin.dianedu.com。", "- 不绕过登录、验证码、鉴权或风控。", "- 401/403 记录后停止对应 URL；429 自动退避。"])
    (settings.reports_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
