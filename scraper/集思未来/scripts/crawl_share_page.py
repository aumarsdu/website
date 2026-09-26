#!/usr/bin/env python3
"""Collect one public SOU mobile share page into the standard local structure."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx

from sou_crawler.config import DEFAULT_USER_AGENT, PROJECT_ROOT, CrawlConfig
from sou_crawler.full_refresh import (
    DETAIL_ENDPOINT,
    RefreshOptions,
    SiteSpec,
    download_assets_for_site,
)
from sou_crawler.normalizer import normalize_outputs
from sou_crawler.organizer import organize_assets
from sou_crawler.utils import append_jsonl, deep_find_asset_urls, utc_now_iso, write_json


COMPUTER_WORDS = (
    "计算机",
    "人工智能",
    "数据科学",
    "机器学习",
    "深度学习",
    "软件",
    "编程",
    "数据库",
    "搜索引擎",
    "算法",
    "网络安全",
    "信息系统",
)
HUMANITIES_WORDS = ("文学", "历史", "哲学", "社会学", "教育", "心理", "法律", "传播", "语言", "艺术")
FINANCE_WORDS = ("金融", "经济", "商业", "管理", "市场营销", "财务", "会计", "供应链", "投资")


@dataclass(frozen=True)
class ShareCollectOptions:
    share_url: str
    output_dir: Path
    user_agent: str
    timeout: float
    retries: int
    rate_limit: float
    concurrency: int


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect one public SOU share page.")
    parser.add_argument("share_url")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args(argv)

    options = ShareCollectOptions(
        share_url=args.share_url,
        output_dir=args.output_dir,
        user_agent=args.user_agent,
        timeout=args.timeout,
        retries=args.retries,
        rate_limit=args.rate_limit,
        concurrency=args.concurrency,
    )
    asyncio.run(collect_share_page(options))
    return 0


async def collect_share_page(options: ShareCollectOptions) -> None:
    course_id = parse_share_id(options.share_url)
    output_dir = options.output_dir
    for subdir in ("raw", "processed", "reports", "assets"):
        (output_dir / subdir).mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        timeout=options.timeout,
        headers={"User-Agent": options.user_agent, "Accept": "application/json,text/plain,*/*"},
        follow_redirects=True,
    ) as client:
        page_report = await save_share_html(client, options.share_url, output_dir)
        payload, detail_meta = await fetch_detail(client, options, course_id)

    detail_record = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(detail_record, dict) or not detail_record.get("id"):
        raise RuntimeError(f"Detail API did not return a usable record for {course_id}")

    list_record = build_list_record(course_id, detail_record)
    existing = find_existing_list_record(course_id)
    if existing:
        list_record.update({key: value for key, value in existing.items() if value not in (None, "")})
        list_record.update(build_directory_hints(list_record, detail_record))
    else:
        list_record.update(build_directory_hints(list_record, detail_record))

    write_run_inputs(output_dir, course_id, options.share_url, list_record, payload, detail_meta)

    config = CrawlConfig(
        base_url="https://sou-tools.gecacademy.cn/",
        mobile_base_url="https://sou-m.gecacademy.cn/",
        user_agent=options.user_agent,
        output_dir=output_dir,
        timeout=options.timeout,
        retries=options.retries,
        rate_limit=options.rate_limit,
        concurrency=options.concurrency,
        max_pages=1,
        max_details=1,
    )
    normalize_outputs(config)
    asset_report = await download_assets_for_site(
        SiteSpec(
            name="sou_tools",
            base_url="https://sou-tools.gecacademy.cn/",
            seeds=[],
            asset_cache_dirs=asset_cache_dirs(),
        ),
        output_dir,
        RefreshOptions(
            run_id=output_dir.name,
            output_root=output_dir.parent,
            user_agent=options.user_agent,
            timeout=options.timeout,
            retries=options.retries,
            rate_limit=options.rate_limit,
            concurrency=options.concurrency,
            max_pages=1,
            max_details=1,
            download_assets=True,
        ),
    )
    organize_assets(config)

    summary = {
        "share_url": options.share_url,
        "id": course_id,
        "title": detail_record.get("name"),
        "teacherName": detail_record.get("teacherName"),
        "category": list_record.get("_category"),
        "direction": list_record.get("direction"),
        "detail_fields": len(detail_record),
        "asset_urls_found": len(deep_find_asset_urls({"list": list_record, "detail": detail_record})),
        "attachments": len(detail_record.get("allAttachmentsArray") or []),
        "share_page": page_report,
        "asset_report": asset_report,
        "finished_at": utc_now_iso(),
    }
    write_json(output_dir / "reports" / "share_collect_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_share_id(share_url: str) -> str:
    parsed = urlsplit(share_url)
    values = parse_qs(parsed.query).get("id") or []
    if not values or not values[0].strip():
        raise ValueError(f"Missing id query parameter in share URL: {share_url}")
    return values[0].strip()


async def save_share_html(client: httpx.AsyncClient, share_url: str, output_dir: Path) -> dict[str, Any]:
    try:
        response = await client.get(share_url)
    except httpx.HTTPError as exc:
        return {"saved": False, "error": type(exc).__name__}
    html_path = output_dir / "raw" / "share_page.html"
    html_path.write_text(response.text, encoding="utf-8")
    return {
        "saved": True,
        "path": str(html_path),
        "status": response.status_code,
        "bytes": len(response.content),
    }


async def fetch_detail(
    client: httpx.AsyncClient,
    options: ShareCollectOptions,
    course_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    last_error = "unknown_error"
    for attempt in range(options.retries + 1):
        if attempt:
            await asyncio.sleep(options.rate_limit * (2**attempt))
        else:
            await asyncio.sleep(options.rate_limit)
        try:
            response = await client.post(
                DETAIL_ENDPOINT,
                json={"id": course_id, "isQrcode": False},
                headers={
                    "Origin": "https://sou-m.gecacademy.cn",
                    "Referer": options.share_url,
                    "Content-Type": "application/json;charset=UTF-8",
                },
            )
        except httpx.TimeoutException:
            last_error = "timeout"
            continue
        except httpx.HTTPError as exc:
            last_error = type(exc).__name__
            continue
        meta = {
            "url": str(response.url),
            "method": "POST",
            "status": response.status_code,
        }
        if response.status_code in {429} or response.status_code >= 500:
            last_error = f"http_{response.status_code}"
            continue
        response.raise_for_status()
        return response.json(), meta
    raise RuntimeError(f"Failed to fetch detail for {course_id}: {last_error}")


def build_list_record(course_id: str, detail_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": course_id,
        "name": detail_record.get("name"),
        "teacherName": detail_record.get("teacherName"),
        "teacherHeadImgUrl": detail_record.get("teacherHeadImgUrl"),
        "typeId": detail_record.get("typeId"),
        "suggestBasics": detail_record.get("suggestBasics"),
        "schoolBegins": detail_record.get("schoolBegins"),
    }


def find_existing_list_record(course_id: str) -> dict[str, Any] | None:
    for path in existing_list_record_paths():
        for row in read_jsonl(path):
            record = row.get("record") if isinstance(row, dict) else None
            if not isinstance(record, dict):
                continue
            if str(record.get("id") or record.get("uuid") or "") == course_id:
                return dict(record)
    return None


def existing_list_record_paths() -> list[Path]:
    candidates = [
        PROJECT_ROOT / "output" / "raw" / "list_records.jsonl",
        PROJECT_ROOT / "output" / "full_refresh" / "20260703-new-check" / "sou_tools" / "raw" / "list_records.jsonl",
        PROJECT_ROOT / "output" / "full_refresh" / "20260602-full-refresh" / "sou_tools" / "raw" / "list_records.jsonl",
    ]
    return [path for path in candidates if path.exists()]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_directory_hints(list_record: dict[str, Any], detail_record: dict[str, Any]) -> dict[str, str]:
    title = str(detail_record.get("name") or list_record.get("name") or "")
    text = " ".join(
        str(value or "")
        for value in (
            title,
            detail_record.get("suggestBasics"),
            list_record.get("suggestBasics"),
            detail_record.get("foundationCourseName"),
        )
    )
    return {
        "_category": infer_category(text),
        "direction": infer_direction(title, text),
    }


def infer_category(text: str) -> str:
    if any(word in text for word in COMPUTER_WORDS):
        return "计算机与人工智能"
    if any(word in text for word in HUMANITIES_WORDS):
        return "人文社科"
    if any(word in text for word in FINANCE_WORDS):
        return "金融商科"
    return "理工科"


def infer_direction(title: str, text: str) -> str:
    match = re.search(r"：([^：]{2,40}专题)：", title)
    if match:
        return match.group(1).removesuffix("专题")
    for keyword in ("数据库系统", "搜索引擎", "信息系统管理", "软件工程", "人工智能", "数据科学"):
        if keyword in text:
            return keyword
    return "未分方向"


def write_run_inputs(
    output_dir: Path,
    course_id: str,
    share_url: str,
    list_record: dict[str, Any],
    payload: dict[str, Any],
    detail_meta: dict[str, Any],
) -> None:
    for path in (
        output_dir / "raw" / "list_records.jsonl",
        output_dir / "raw" / "detail_responses.jsonl",
        output_dir / "raw" / "list_responses.jsonl",
    ):
        path.write_text("", encoding="utf-8")

    append_jsonl(
        output_dir / "raw" / "list_records.jsonl",
        {
            "source_url": share_url,
            "label": f"{list_record.get('_category') or '未归类'}+{list_record.get('direction') or '未分方向'}",
            "page": 1,
            "crawled_at": utc_now_iso(),
            "record": list_record,
        },
    )
    append_jsonl(
        output_dir / "raw" / "detail_responses.jsonl",
        {
            "crawled_at": utc_now_iso(),
            "api": f"POST {DETAIL_ENDPOINT}",
            "id": course_id,
            "meta": detail_meta,
            "payload": payload,
        },
    )


def asset_cache_dirs() -> list[Path]:
    candidates = [
        PROJECT_ROOT / "output" / "assets",
        PROJECT_ROOT / "output" / "full_refresh" / "20260703-new-check" / "sou_tools" / "assets",
        PROJECT_ROOT / "output" / "full_refresh" / "20260602-full-refresh" / "sou_tools" / "assets",
        PROJECT_ROOT / "output" / "incremental" / "20260724-new-check" / "sou_tools" / "assets",
    ]
    return [path for path in candidates if path.exists()]


if __name__ == "__main__":
    raise SystemExit(main())
