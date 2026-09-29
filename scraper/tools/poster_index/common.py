"""poster_index — 供应商课题海报统一索引（需求文档 2026-09-28 版）.

只读素材库（~/Workspace/knowledge-legacy/scraper/ 的指定子目录），输出索引与
报告到 ~/Workspace/_private-tasks/xhs-cover-gen/posters/。纯标准库实现。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRAPER_ROOT = Path("/Users/liujunliang/Workspace/knowledge-legacy/scraper")
OUTPUT_DIR = Path.home() / "Workspace" / "_private-tasks" / "xhs-cover-gen" / "posters"

SUBJECTS = ("计算机与人工智能", "理工科", "金融商科", "人文社科", "其他")
# 授课形式（索引修正需求 §2，军亮 2026-09-29 确认四值）
FORMATS = ("小组科研", "班课科研", "1V1", "其他")

# 供应商/站点原始分类 → 统一学科（需求 5.3 映射表）
SUPPLIER_SUBJECT_MAP = {
    "文科": "人文社科",
    "理科": "理工科",
    "理工": "理工科",
    "工科": "理工科",
    "商科": "金融商科",
    "人文": "人文社科",
    "计算机": "计算机与人工智能",
    # 集思未来 manifest subject 已是五值枚举，原样通过
    "计算机与人工智能": "计算机与人工智能",
    "金融商科": "金融商科",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_FINISH_RE = re.compile(r"finish", re.IGNORECASE)


class IndexItemError(ValueError):
    """Raised when a built item violates the 4.1 field contract."""


def map_subject(raw_subject: str | None) -> str | None:
    """Map a supplier-native subject onto the unified enum; None if unknown."""
    if not raw_subject:
        return None
    raw = str(raw_subject).strip()
    if raw in SUBJECTS:
        return raw
    return SUPPLIER_SUBJECT_MAP.get(raw)


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def is_processed_name(name: str) -> bool:
    """处理版标记：Finish 前缀/后缀（见 scraper/docs/poster-naming-convention.md）。"""
    return bool(_FINISH_RE.search(name))


def normalize_date(value: Any) -> str | None:
    """Best-effort ISO 8601 date (YYYY-MM-DD); returns None when absent/garbage."""
    if not value:
        return None
    text = str(value).strip()
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return "-".join(match.groups())
    return None


def dedup_keep_latest(records: Iterable[dict[str, Any]], key_fn, crawled_fn) -> list[dict[str, Any]]:
    """Keep one record per key, preferring the latest crawled timestamp."""
    best: dict[Any, tuple[str, dict[str, Any]]] = {}
    for record in records:
        key = key_fn(record)
        if not key:
            continue
        crawled = str(crawled_fn(record) or "")
        current = best.get(key)
        if current is None or crawled >= current[0]:
            best[key] = (crawled, record)
    return [item for _, item in best.values()]


def select_poster(
    candidates: list[Path],
    *,
    manifest_sha256: str | None = None,
) -> tuple[Path | None, str, list[Path]]:
    """Pick the poster per需求 5.1: manifest sha256 > processed > latest mtime.

    Returns (selected_path, variant, candidates_kept). Only existing, non-empty
    image files are considered.
    """
    usable = [p for p in candidates if p.is_file() and p.stat().st_size > 0 and is_image(p)]
    if not usable:
        return None, "raw", []

    def variant_of(p: Path) -> str:
        return "processed" if is_processed_name(p.name) else "raw"

    if manifest_sha256:
        for p in usable:
            if sha256_file(p) == manifest_sha256:
                return p, variant_of(p), usable
    processed = [p for p in usable if variant_of(p) == "processed"]
    pool = processed or usable
    selected = max(pool, key=lambda p: p.stat().st_mtime)
    return selected, variant_of(selected), usable


def build_item(**fields: Any) -> dict[str, Any]:
    """Validate and normalize one index item (4.1 + 细分方向标签 §5/§8-D1)."""
    item = {
        "supplier": fields.get("supplier"),
        "recordId": str(fields.get("recordId") or ""),
        "title": str(fields.get("title") or ""),
        "subject": fields.get("subject"),
        "subjectSource": fields.get("subjectSource"),
        "subjectOriginal": fields.get("subjectOriginal"),
        "direction": fields.get("direction"),
        "directionSecondary": fields.get("directionSecondary"),
        "directionBasis": fields.get("directionBasis"),
        "projectType": str(fields.get("projectType") or ""),
        "format": fields.get("format"),
        "schoolBegins": fields.get("schoolBegins"),
        "instructors": list(fields.get("instructors") or []),
        "corpus": fields.get("corpus") or {},
        "posterPath": str(fields.get("posterPath") or ""),
        "posterVariant": fields.get("posterVariant"),
        "posterSha256": str(fields.get("posterSha256") or ""),
        "posterCandidates": [str(p) for p in (fields.get("posterCandidates") or [])],
        "sourceFile": str(fields.get("sourceFile") or ""),
        "crawledAt": fields.get("crawledAt"),
    }
    missing = [k for k in ("supplier", "subject", "subjectSource", "posterVariant",
                           "direction", "directionBasis", "subjectOriginal") if not item[k]]
    if missing:
        raise IndexItemError(f"item {item['recordId'] or item['title'][:20]} missing {missing}")
    if item["subject"] not in SUBJECTS:
        raise IndexItemError(f"item {item['recordId']}: subject {item['subject']!r} not in enum")
    # D1: subjectSource = direction 判定来源
    if item["subjectSource"] not in ("label", "title", "corpus", "override"):
        raise IndexItemError(f"item {item['recordId']}: subjectSource must be label|title|corpus|override")
    from .direction import allowed_directions
    if item["direction"] not in allowed_directions():
        raise IndexItemError(f"item {item['recordId']}: direction {item['direction']!r} not in taxonomy")
    if item["directionSecondary"] is not None and item["directionSecondary"] not in allowed_directions():
        raise IndexItemError(f"item {item['recordId']}: directionSecondary {item['directionSecondary']!r} not in taxonomy")
    if not isinstance(item["directionBasis"], dict) or "source" not in item["directionBasis"]:
        raise IndexItemError(f"item {item['recordId']}: directionBasis must be an object with source")
    if item["format"] not in FORMATS:
        raise IndexItemError(f"item {item['recordId']}: format {item['format']!r} not in {FORMATS}")
    if item["posterVariant"] not in ("processed", "raw"):
        raise IndexItemError(f"item {item['recordId']}: posterVariant must be processed|raw")
    if not item["recordId"] or not item["title"] or not item["posterPath"] or not item["posterSha256"]:
        raise IndexItemError(f"item {item['recordId']}: recordId/title/posterPath/posterSha256 required")
    return item


def write_index_and_report(supplier: str, items: list[dict[str, Any]], report: dict[str, Any]) -> tuple[Path, Path]:
    """Atomic-write <供应商>.index.json / .report.json (tmp + os.replace)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    index_doc = {"supplier": supplier, "generatedAt": now, "items": items}
    report_doc = {"supplier": supplier, "generatedAt": now, **report}
    paths = []
    for name, doc in ((f"{supplier}.index.json", index_doc), (f"{supplier}.report.json", report_doc)):
        target = OUTPUT_DIR / name
        tmp = target.with_suffix(target.suffix + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, target)
        paths.append(target)
    return paths[0], paths[1]


def find_in_index(
    items: Iterable[dict[str, Any]],
    *,
    subject: str | None = None,
    direction: str | None = None,
    project_type: str | None = None,
    begins_from: str | None = None,
    begins_to: str | None = None,
    open_only: bool = False,
    today: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Filter items per the find contract; sort by schoolBegins ascending (nulls last)."""
    today = today or datetime.now().strftime("%Y-%m-%d")
    out = []
    for item in items:
        if subject and item["subject"] != subject:
            continue
        if direction and item.get("direction") != direction:
            continue
        if project_type and item["projectType"] != project_type:
            continue
        begins = item.get("schoolBegins")
        if open_only and (not begins or begins <= today):
            continue
        if begins_from and (not begins or begins < begins_from):
            continue
        if begins_to and (not begins or begins > begins_to):
            continue
        out.append(item)
    out.sort(key=lambda i: (i.get("schoolBegins") is None, i.get("schoolBegins") or "", i["title"]))
    if limit:
        out = out[:limit]
    return out


def resolve_format(supplier: str, project_type: str) -> str:
    """projectType -> format（format_map.json 配置，未映射走 fallback=其他）。"""
    cfg = json.loads((Path(__file__).resolve().parent / "format_map.json").read_text(encoding="utf-8"))
    mapped = cfg.get("maps", {}).get(supplier, {}).get(project_type)
    if mapped in FORMATS:
        return str(mapped)
    return str(cfg.get("fallback") or "其他")


def format_distribution(items: list[dict[str, Any]], *, today: str | None = None) -> dict[str, dict[str, int]]:
    """报告：按 format 的课题数与可报名数（索引修正需求 §3）。"""
    from datetime import date as _date

    today = today or _date.today().isoformat()
    out: dict[str, dict[str, int]] = {}
    for item in items:
        slot = out.setdefault(str(item.get("format")), {"courses": 0, "open": 0})
        slot["courses"] += 1
        begins = item.get("schoolBegins")
        if begins and begins > today:
            slot["open"] += 1
    return out
