"""中科浩博 index builder (需求文档 3.1 / 三期), 含学科打标与 overrides."""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from . import common, direction
from .common import SCRAPER_ROOT

SUPPLIER = "中科浩博"
ROOT = SCRAPER_ROOT / "中科"
PROCESSED = ROOT / "output/processed/projects.jsonl"
NEW_PROCESSED = ROOT / "output_check_20260703/new_projects/processed/new_projects.jsonl"
POSTER_SHUANG = ROOT / "Poster/双教授课题（鲸鱼座）"
POSTER_ZHONGFANG = ROOT / "Poster/中方课题（研途有果）"
SITE_MIRROR = ROOT / "output/site"
OCT_INVENTORY = ROOT / "中科-开课时间-2026年10月1日以后/poster_inventory.csv"

def _load_records(path: Path, id_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            record["_source_file"] = str(path)
            records.append(record)
    # 需求 5.1：同一课题只保留一条。中科的 uuid 是"每次抓取记录"的标识，
    # 同名课题会被多批次重复抓取（同一标题最多 23 条记录），
    # 因此业务去重键 = 课题标题（与海报目录组织一致），无标题时退回 uuid。
    return common.dedup_keep_latest(
        records,
        key_fn=lambda r: (str(r.get("title") or "").strip() or next(
            (str(r.get(f) or "") for f in id_fields if r.get(f)), "")),
        crawled_fn=lambda r: r.get("crawled_at"),
    )


def norm_title(title: str) -> str:
    """标题规范化：去除空白与常见中英文标点差异（——/-、？/? 等），用于变体匹配。"""
    return re.sub(r"[\s—－―–\-－・·，,。.；;：:？?！!（）()\[\]【】\"\"'''\"]+", "", title or "")


def _poster_stem_map(folder: Path) -> dict[str, dict[str, list[Path]]]:
    """返回 {"exact": 标题->文件, "norm": 规范化标题->文件} 两级索引。"""
    exact: dict[str, list[Path]] = {}
    norm: dict[str, list[Path]] = {}
    for f in folder.rglob("*"):
        if f.is_file() and common.is_image(f):
            stem = f.parent.name if len(f.relative_to(folder).parts) > 1 else None
            if not stem:
                match = re.match(r"^(?:Finish)?(.+?)__[0-9a-f]{8,}\.(?:jpg|png|jpeg|webp)$", f.name, re.IGNORECASE)
                stem = match.group(1).strip() if match else None
            if not stem:
                continue
            exact.setdefault(stem, []).append(f)
            norm.setdefault(norm_title(stem), []).append(f)
    return {"exact": exact, "norm": norm}


def _site_poster_map(folder: Path) -> dict[str, list[Path]]:
    """站点镜像海报：output/site/<分类>/<方向>/<课题[ __uuid]>/图片，按规范化标题索引。"""
    out: dict[str, list[Path]] = {}
    bad = re.compile(r"speaker|avatar|teacher|banner|icon|logo|header", re.IGNORECASE)
    for f in folder.rglob("*"):
        if f.is_file() and common.is_image(f):
            rel = f.relative_to(folder)
            if len(rel.parts) < 3 or bad.search(f.name):
                continue
            stem = re.sub(r"__[0-9a-f]{16,}$", "", rel.parts[-2], flags=re.IGNORECASE)
            out.setdefault(norm_title(stem), []).append(f)
    return out


def _candidates_for(title: str, poster_map: dict[str, dict[str, list[Path]]]) -> list[Path]:
    """先精确标题，再规范化变体（需求 5.1 同一课题判定）。"""
    candidates = poster_map["exact"].get(title, [])
    if not candidates:
        candidates = poster_map["norm"].get(norm_title(title), [])
    return candidates


def _october_dates() -> tuple[dict[str, str], dict[str, str]]:
    """(id -> start_date, title -> start_date) from the October inventory."""
    by_id: dict[str, str] = {}
    by_title: dict[str, str] = {}
    if not OCT_INVENTORY.exists():
        return by_id, by_title
    with open(OCT_INVENTORY, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            starts = common.normalize_date(row.get("start_date"))
            if not starts:
                continue
            if row.get("id"):
                by_id[str(row["id"])] = starts
            if row.get("title"):
                by_title[str(row["title"])] = starts
    return by_id, by_title


def build(root: Path = ROOT) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    oct_by_id, oct_by_title = _october_dates()
    items: list[dict[str, Any]] = []
    missing_posters: list[str] = []
    orphan_posters: list[str] = []
    subject_counts: dict[str, int] = {}
    variant_counts = {"processed": 0, "raw": 0}
    with_dates = future = 0
    today = date.today().isoformat()

    # ---- 双教授课题：库内分类 + 站点目录结构 ----
    shuang = _load_records(PROCESSED, ("uuid", "id"))
    shuang_posters = _poster_stem_map(POSTER_SHUANG)
    site_posters = _site_poster_map(SITE_MIRROR)
    for record in shuang:
        title = str(record.get("title") or "").strip()
        rid = str(record.get("uuid") or record.get("id") or "")
        subject_original = common.map_subject(record.get("category")) or "其他"
        tagged = direction.classify(
            title,
            corpus=str(record.get("description") or ""),
            override_key=f"{SUPPLIER}:{rid}",
        )
        subject = tagged["subject"]
        subject_counts[subject] = subject_counts.get(subject, 0) + 1
        candidates = _candidates_for(title, shuang_posters)
        if not candidates:
            candidates = site_posters.get(norm_title(title), [])
        selected, variant, usable = common.select_poster(candidates)
        if selected is None:
            missing_posters.append(rid or title)
            continue
        variant_counts[variant] = variant_counts.get(variant, 0) + 1
        begins = (
            oct_by_id.get(str(record.get("uuid") or ""))
            or oct_by_id.get(str(record.get("id") or ""))
            or oct_by_title.get(title)
        )
        if begins:
            with_dates += 1
            if begins > today:
                future += 1
        instructor = str(record.get("teacher") or "").strip()
        corpus = {
            k: record.get(k)
            for k in ("description", "direction", "university", "teacher", "source_url")
            if record.get(k)
        }
        items.append(common.build_item(
            supplier=SUPPLIER,
            recordId=rid,
            title=title,
            subject=subject,
            subjectSource=tagged["directionBasis"]["source"],
            subjectOriginal=subject_original,
            direction=tagged["direction"],
            directionSecondary=tagged["directionSecondary"],
            directionBasis=tagged["directionBasis"],
            projectType="双教授课题（鲸鱼座）",
            schoolBegins=begins,
            instructors=[instructor] if instructor else [],
            corpus=corpus,
            posterPath=str(selected),
            posterVariant=variant,
            posterSha256=common.sha256_file(selected),
            posterCandidates=[p for p in usable if p != selected],
            sourceFile=str(record.get("_source_file") or ""),
            crawledAt=record.get("crawled_at"),
        ))

    # ---- 中方课题：无学科字段，全量打标 ----
    zhongfang = _load_records(NEW_PROCESSED, ("uuid", "id"))
    zhong_posters = _poster_stem_map(POSTER_ZHONGFANG)
    known_norm = {norm_title(str(r.get("title") or "").strip()) for r in zhongfang}
    for record in zhongfang:
        title = str(record.get("title") or "").strip()
        rid = str(record.get("uuid") or record.get("id") or "")
        raw = record.get("raw") or {}
        subject_original = "其他"
        tagged = direction.classify(
            title,
            corpus=str(record.get("description") or ""),
            override_key=f"{SUPPLIER}:{rid}",
        )
        subject = tagged["subject"]
        subject_counts[subject] = subject_counts.get(subject, 0) + 1
        candidates = _candidates_for(title, zhong_posters)
        selected, variant, usable = common.select_poster(candidates)
        if selected is None:
            missing_posters.append(rid or title)
            continue
        variant_counts[variant] = variant_counts.get(variant, 0) + 1
        begins = common.normalize_date(raw.get("startTime"))
        if begins:
            with_dates += 1
            if begins > today:
                future += 1
        instructor = str(record.get("teacher") or "").strip()
        corpus = {
            k: record.get(k)
            for k in ("description", "teacher", "university", "source_url")
            if record.get(k)
        }
        items.append(common.build_item(
            supplier=SUPPLIER,
            recordId=rid,
            title=title,
            subject=subject,
            subjectSource=tagged["directionBasis"]["source"],
            subjectOriginal=subject_original,
            direction=tagged["direction"],
            directionSecondary=tagged["directionSecondary"],
            directionBasis=tagged["directionBasis"],
            projectType="中方课题（研途有果）",
            schoolBegins=begins,
            instructors=[instructor] if instructor else [],
            corpus=corpus,
            posterPath=str(selected),
            posterVariant=variant,
            posterSha256=common.sha256_file(selected),
            posterCandidates=[p for p in usable if p != selected],
            sourceFile=str(record.get("_source_file") or ""),
            crawledAt=record.get("crawled_at"),
        ))

    for stem, files in zhong_posters["exact"].items():
        if norm_title(stem) not in known_norm:
            orphan_posters.extend(str(p) for p in files)

    report = {
        "total_courses": len(shuang) + len(zhongfang),
        "posters_found": len(items),
        "missing_poster_count": len(missing_posters),
        "missing_poster_ids": sorted(missing_posters)[:200],
        "orphan_poster_files": len(orphan_posters),
        "with_school_begins": with_dates,
        "school_begins_future": future,
        "subject_distribution": subject_counts,
        "poster_variant_distribution": variant_counts,
        **direction.summarize(items),
    }
    return items, report
