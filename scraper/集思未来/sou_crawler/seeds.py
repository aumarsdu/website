"""Seed construction for the full/incremental refresh crawlers.

List seeds are replayed public list-API bodies discovered during Playwright
network capture; signatures/labels identify a seed across runs.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT
from .utils import iter_jsonl


@dataclass(frozen=True)
class ListSeed:
    label: str
    url: str
    body: dict[str, Any]
    origin: str
    referer: str
    limit: int


@dataclass(frozen=True)
class SiteSpec:
    name: str
    base_url: str
    seeds: list[ListSeed]
    asset_cache_dirs: list[Path] = field(default_factory=list)


def page_body(body: dict[str, Any], page: int, limit: int) -> dict[str, Any]:
    out = copy.deepcopy(body)
    out["page"] = page
    if limit:
        out["limit"] = limit
    return out


def seed_signature(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "levelList": body.get("levelList"),
        "typeId": body.get("typeId"),
        "typeIdList": body.get("typeIdList"),
        "isAiHub": body.get("isAiHub"),
        "types": body.get("types"),
        "isAstra": body.get("isAstra"),
    }


def domestic_seed_signature(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "pageType": body.get("pageType"),
        "level1": body.get("level1"),
        "level2": body.get("level2"),
        "typeIdList": body.get("typeIdList"),
        "types": body.get("types"),
        "isCnPage": body.get("isCnPage"),
    }


def label_from_body(body: dict[str, Any]) -> str:
    level_list = body.get("levelList")
    if isinstance(level_list, list) and level_list:
        names = [str(item.get("name")) for item in level_list if isinstance(item, dict) and item.get("name")]
        if names:
            return "+".join(names)
    if body.get("isAiHub"):
        return "aiHub"
    if body.get("typeIdList"):
        return "typeIdList=" + ",".join(str(item) for item in body["typeIdList"])
    return "all"


def domestic_label(body: dict[str, Any]) -> str:
    parts = []
    if body.get("pageType") is not None:
        parts.append(f"pageType={body['pageType']}")
    if body.get("types"):
        parts.append(str(body["types"]))
    if body.get("typeIdList"):
        parts.append("typeIdList=" + ",".join(str(item) for item in body["typeIdList"]))
    return " ".join(parts) or "domestic"


def build_sou_tools_seeds() -> list[ListSeed]:
    path = PROJECT_ROOT / "output" / "discovery" / "network_logs.jsonl"
    seeds: list[ListSeed] = []
    seen: set[str] = set()
    for row in iter_jsonl(path):
        if row.get("event") != "response" or not row.get("is_json"):
            continue
        url = str(row.get("url", ""))
        if not (url.endswith("/soutools/v2/course/query/common") or url.endswith("/soutools/v2/course/query/aiHub")):
            continue
        body = row.get("post_data_json")
        if not isinstance(body, dict):
            continue
        seed_body = copy.deepcopy(body)
        seed_body["page"] = 1
        seed_body["limit"] = 50
        signature = json.dumps(seed_signature(seed_body), ensure_ascii=False, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        seeds.append(
            ListSeed(
                label=label_from_body(seed_body),
                url=url,
                body=seed_body,
                origin="https://sou-tools.gecacademy.cn",
                referer="https://sou-tools.gecacademy.cn/",
                limit=50,
            )
        )
    if not seeds:
        raise RuntimeError(f"No sou-tools list seeds found in {path}")
    return seeds


def build_domestic_seeds() -> list[ListSeed]:
    seeds = build_domestic_seeds_from_network_logs(
        PROJECT_ROOT / "output" / "discovery" / "network_logs.jsonl"
    )
    if seeds:
        return seeds

    report_path = (
        PROJECT_ROOT
        / "output"
        / "domestic_full"
        / "20260602-ensure-pages"
        / "reports"
        / "domestic_full_list_stats.json"
    )
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        seeds = []
        for summary in report.get("seed_summaries", []):
            body = copy.deepcopy(summary.get("body_page1") or {})
            body["page"] = 1
            limit = int(body.get("limit") or 20)
            seeds.append(
                ListSeed(
                    label=domestic_label(body),
                    url=summary["url"],
                    body=body,
                    origin="https://domestic.gecacademy.cn",
                    referer="https://domestic.gecacademy.cn/",
                    limit=limit,
                )
            )
        if seeds:
            return seeds
    raise RuntimeError(f"No domestic list seeds found in {report_path}")


def build_domestic_seeds_from_network_logs(path: Path) -> list[ListSeed]:
    seeds: list[ListSeed] = []
    seen: set[str] = set()
    for row in iter_jsonl(path):
        if row.get("event") != "response" or not row.get("is_json"):
            continue
        url = str(row.get("url", ""))
        if not url.endswith("/soutools/course/query/course"):
            continue
        body = row.get("post_data_json")
        if not isinstance(body, dict):
            continue
        seed_body = copy.deepcopy(body)
        seed_body["page"] = 1
        seed_body["limit"] = int(seed_body.get("limit") or 20)
        signature = json.dumps(
            domestic_seed_signature(seed_body),
            ensure_ascii=False,
            sort_keys=True,
        )
        if signature in seen:
            continue
        seen.add(signature)
        seeds.append(
            ListSeed(
                label=domestic_label(seed_body),
                url=url,
                body=seed_body,
                origin="https://domestic.gecacademy.cn",
                referer="https://domestic.gecacademy.cn/",
                limit=int(seed_body["limit"]),
            )
        )
    return seeds

