from __future__ import annotations

from pathlib import Path
import json
import zipfile

from .config import Settings
from .normalize import normalize, read_table
from .storage import write_csv, write_json, write_jsonl


def export_outputs(settings: Settings) -> None:
    if settings.dry_run:
        print({"command": "export", "will_write": ["jsonl", "csv", "markdown", "html", "zip"]})
        return
    normalize(settings)
    export_dir = settings.archives_dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    datasets = {
        "projects": read_table(settings, "projects"),
        "articles": read_table(settings, "articles"),
        "pages": read_table(settings, "pages"),
        "filters": read_table(settings, "filters"),
        "hot_search_terms": read_table(settings, "hot_search_terms"),
        "assets": read_table(settings, "assets"),
    }
    for name, records in datasets.items():
        write_json(export_dir / f"{name}.json", records)
        write_jsonl(export_dir / f"{name}.jsonl", records)
        if records:
            write_csv(export_dir / f"{name}.csv", records)
    write_markdown(export_dir / "README.md", datasets)
    write_html(export_dir / "index.html", datasets)
    zip_path = settings.archives_dir / "dianedu_archive_report.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in export_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(export_dir))
        for path in [settings.processed_dir / "data_quality_summary.json", settings.reports_dir / "summary.md"]:
            if path.exists():
                zf.write(path, Path("reports") / path.name)


def write_markdown(path: Path, datasets: dict[str, list[dict]]) -> None:
    lines = ["# DianEdu Archive Export", ""]
    for name, records in datasets.items():
        lines.append(f"- {name}: {len(records)}")
    lines.extend(["", "## Notes", "", "- 默认仅包含 www.dianedu.com 授权主站范围。", "- admin.dianedu.com 被显式排除。"])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html(path: Path, datasets: dict[str, list[dict]]) -> None:
    rows = "\n".join(f"<tr><td>{name}</td><td>{len(records)}</td></tr>" for name, records in datasets.items())
    payload = json.dumps({name: len(records) for name, records in datasets.items()}, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>DianEdu Archive Report</title></head>
<body>
<h1>DianEdu Archive Report</h1>
<table border="1" cellpadding="6" cellspacing="0"><thead><tr><th>Dataset</th><th>Rows</th></tr></thead><tbody>{rows}</tbody></table>
<script type="application/json" id="summary">{payload}</script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
