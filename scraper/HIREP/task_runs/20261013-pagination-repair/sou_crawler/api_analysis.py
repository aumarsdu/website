from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import json
import re

from .config import Settings
from .storage import iter_jsonl, write_json
from .utils import UUID_RE

KEYWORDS = {
    "list": ["list", "search", "page", "total", "records", "rows"],
    "detail": ["detail", "info", "id", "uuid", "courseextendid", "projectid"],
    "category": ["category", "classify", "level", "subject", "filter"],
    "asset": ["oss-cn", "aliyuncs", "pdf", "jpg", "png", "jpeg", "webp", "poster", "syllabus"],
    "project_fields": ["title", "name", "teacher", "instructor", "professor", "university", "major", "prerequisite", "intro", "description"],
}


def analyze_network_logs(settings: Settings) -> list[dict[str, Any]]:
    log_path = settings.discovery_dir / "network_logs.jsonl"
    records = list(iter_jsonl(log_path) or [])
    classified = [classify_record(record) for record in records]
    classified.sort(key=lambda item: item["score"], reverse=True)
    write_json(settings.discovery_dir / "api_classification.json", classified)
    write_classification_md(settings.discovery_dir / "api_classification.md", classified)
    return classified


def classify_record(record: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(record, ensure_ascii=False).lower()
    counters = {kind: sum(1 for token in tokens if token in text) for kind, tokens in KEYWORDS.items()}
    summary = record.get("body_summary") or {}
    array_paths = summary.get("array_paths") or []
    paths = summary.get("paths_sample") or []
    has_array = bool(array_paths)
    has_pagination = any(token in text for token in ["total", "pages", "pagenum", "pagesize", "records", "rows"])
    has_assets = counters["asset"] > 0
    has_uuid = bool(UUID_RE.search(text))

    score = (
        counters["list"] * 3
        + counters["detail"] * 2
        + counters["category"] * 2
        + counters["asset"] * 3
        + counters["project_fields"] * 2
        + int(has_array) * 3
        + int(has_pagination) * 4
        + int(has_uuid) * 2
    )

    likely_types: list[str] = []
    if counters["category"] >= 2:
        likely_types.append("分类/筛选项接口")
    if has_pagination or counters["list"] >= 2:
        likely_types.append("项目列表接口")
    if counters["detail"] >= 2 and not has_pagination:
        likely_types.append("项目详情接口")
    if has_assets:
        likely_types.append("附件资源接口")
    if not likely_types:
        likely_types.append("其他接口")

    parsed = urlparse(record.get("url", ""))
    return {
        "url": record.get("url"),
        "base_url": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        "method": record.get("method"),
        "status": record.get("status"),
        "resource_type": record.get("resource_type"),
        "score": score,
        "likely_types": likely_types,
        "signals": {
            "keyword_counts": counters,
            "has_array": has_array,
            "has_pagination": has_pagination,
            "has_assets": has_assets,
            "has_uuid": has_uuid,
            "array_paths": array_paths,
            "paths_sample": paths[:25],
        },
        "requires_auth": record.get("requires_auth", False),
        "query_params": record.get("query_params", {}),
        "post_data_sample": record.get("post_data"),
    }


def write_classification_md(path: Path, classified: list[dict[str, Any]]) -> None:
    lines = ["# API Classification", "", "按启发式信号排序，分数越高越值得人工复核。", ""]
    for item in classified:
        lines.extend(
            [
                f"## score {item['score']} - `{item['method']} {item['base_url']}`",
                "",
                f"- likely types: `{', '.join(item['likely_types'])}`",
                f"- full URL: `{item['url']}`",
                f"- status: `{item.get('status')}`",
                f"- requires auth: `{item.get('requires_auth')}`",
                f"- query params: `{json.dumps(item.get('query_params', {}), ensure_ascii=False)}`",
                f"- post body sample: `{json.dumps(item.get('post_data_sample'), ensure_ascii=False)}`",
                f"- signals: `{json.dumps(_compact_signals(item['signals']), ensure_ascii=False)}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _compact_signals(signals: dict[str, Any]) -> dict[str, Any]:
    return {
        "keyword_counts": {k: v for k, v in signals["keyword_counts"].items() if v},
        "has_array": signals["has_array"],
        "has_pagination": signals["has_pagination"],
        "has_assets": signals["has_assets"],
        "has_uuid": signals["has_uuid"],
        "array_paths": signals["array_paths"][:10],
    }
