from __future__ import annotations

from collections import Counter

from .config import CrawlConfig, ensure_output_dirs
from .utils import iter_jsonl, read_json


def generate_report(config: CrawlConfig) -> None:
    ensure_output_dirs(config)
    network_rows = iter_jsonl(config.discovery_dir / "network_logs.jsonl")
    apis = read_json(config.discovery_dir / "api_classification.json", [])
    list_records = iter_jsonl(config.raw_dir / "list_records.jsonl")
    detail_rows = iter_jsonl(config.raw_dir / "detail_responses.jsonl")
    normalized = iter_jsonl(config.processed_dir / "records.jsonl")
    errors = Counter()
    for stats_file in (
        config.reports_dir / "crawl_lists_stats.json",
        config.reports_dir / "crawl_details_stats.json",
        config.reports_dir / "download_assets_stats.json",
    ):
        stats = read_json(stats_file, {})
        for key, value in (stats.get("error_categories") or stats.get("errors") or {}).items():
            errors[key] += int(value)

    report = [
        "# SOU Crawler Report",
        "",
        "## Scope",
        "",
        f"- base_url: `{config.base_url}`",
        f"- mobile_base_url: `{config.mobile_base_url}`",
        f"- user_agent: `{config.user_agent}`",
        f"- rate_limit_seconds: `{config.rate_limit}`",
        f"- concurrency: `{config.concurrency}`",
        "",
        "## Outputs",
        "",
        f"- network log rows: {len(network_rows)}",
        f"- discovered API candidates: {len(apis)}",
        f"- raw list records: {len(list_records)}",
        f"- raw detail responses: {len(detail_rows)}",
        f"- normalized records: {len(normalized)}",
        f"- downloaded assets dir: `{config.assets_dir}`",
        "",
        "## Error Summary",
        "",
    ]
    if errors:
        report.extend(f"- {key}: {value}" for key, value in errors.most_common())
    else:
        report.append("- no recorded errors")
    report.extend(
        [
            "",
            "## Compliance Notes",
            "",
            "- Playwright is used for public SPA/XHR discovery only.",
            "- Direct API crawling uses a transparent User-Agent and conservative throttling.",
            "- Cookie, Authorization, token, session and secret-like headers are redacted before persistence.",
            "- 403 responses stop the related request path and are recorded as forbidden.",
            "",
        ]
    )
    (config.reports_dir / "crawl_report.md").write_text("\n".join(report), encoding="utf-8")

