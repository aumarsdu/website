from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .sanitize import dumps_safe, sanitize_url


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def guess_endpoint_type(url: str, sample_body: str | None, statuses: Counter[str]) -> str:
    lowered = f"{url} {sample_body or ''}".lower()
    if "401" in statuses or "403" in statuses:
        return "auth"
    if any(token in lowered for token in ("filter", "options", "countries", "majors", "schools", "degrees")):
        return "filter"
    if any(token in lowered for token in ("list", "items", "results", "page", "total", "records", "rows")):
        return "list"
    path = urlsplit(url).path.lower()
    if any(part in path for part in ("/detail", "/id/", "/schools/", "/cases/")):
        return "detail"
    if path.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".css", ".js", ".ico")):
        return "asset"
    return "unknown"


def summarize_network(network_path: Path) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "statuses": Counter(),
            "query_keys": set(),
            "content_types": Counter(),
            "has_post_body": False,
            "sample_url": None,
            "sample_post_data": None,
            "sample_body": None,
        }
    )
    for item in read_jsonl(network_path):
        url = str(item.get("request_url") or item.get("url") or "")
        method = str(item.get("method") or "GET").upper()
        parsed = urlsplit(url)
        key = f"{method} {parsed.scheme}://{parsed.netloc}{parsed.path}"
        row = grouped[key]
        row["count"] += 1
        row["statuses"][str(item.get("status", "unknown"))] += 1
        row["sample_url"] = row["sample_url"] or sanitize_url(url)
        post_data = item.get("post_data")
        if post_data:
            row["has_post_body"] = True
            row["sample_post_data"] = row["sample_post_data"] or post_data
        for query_key, _ in parse_qsl(parsed.query):
            row["query_keys"].add(query_key)
        content_type = item.get("response_content_type") or item.get("content_type")
        if content_type:
            row["content_types"][str(content_type)] += 1
        sample = item.get("response_body_sample") or item.get("body_sample")
        if sample and not row["sample_body"]:
            row["sample_body"] = str(sample)[:1000]

    rows = []
    for endpoint, data in sorted(grouped.items(), key=lambda pair: (-pair[1]["count"], pair[0])):
        statuses = data["statuses"]
        sample_body = data["sample_body"]
        rows.append(
            {
                "endpoint": endpoint,
                "count": data["count"],
                "statuses": dict(statuses),
                "query_keys": sorted(data["query_keys"]),
                "has_post_body": data["has_post_body"],
                "content_types": dict(data["content_types"]),
                "sample_url": data["sample_url"],
                "sample_post_data": data["sample_post_data"],
                "sample_body_preview": sample_body,
                "guessed_type": guess_endpoint_type(endpoint, sample_body, statuses),
            }
        )
    return rows


def write_summary(rows: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "endpoints_summary.json").write_text(dumps_safe(rows, indent=2), encoding="utf-8")
    lines = [
        "# Openision Endpoint Summary",
        "",
        "| Endpoint | Count | Statuses | Query Keys | Type |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['endpoint']}` | {row['count']} | `{row['statuses']}` | `{', '.join(row['query_keys'])}` | {row['guessed_type']} |"
        )
    candidates = [row for row in rows if row["guessed_type"] in {"list", "detail", "filter"}]
    lines.extend(["", "## Next API Candidates", ""])
    if candidates:
        for row in candidates:
            lines.append(f"- `{row['endpoint']}` ({row['guessed_type']})")
    else:
        lines.append("- No clear API candidates found yet. Run `probe` with Playwright installed to capture XHR/fetch responses.")
    (out_dir / "endpoints_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
