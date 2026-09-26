from __future__ import annotations

import json
import os
import shutil
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .asset_downloader import asset_path
from .config import CrawlConfig, ensure_output_dirs
from .utils import deep_find_asset_urls, iter_jsonl, safe_filename, write_json


CATEGORY_BY_SEED = {
    1: "金融商科",
    2: "理工科",
    3: "人文社科",
    5: "计算机与人工智能",
    6: "2026暑期线下科研项目",
    7: "全球在研",
    8: "Astra 1v1",
}


@dataclass(frozen=True)
class TopicEntry:
    category: str
    course_id: str
    list_record: dict[str, Any]
    crawl_label: str | None = None


def organize_assets(config: CrawlConfig) -> None:
    ensure_output_dirs(config)
    output_dir = config.output_dir / "organized_by_site"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    list_records = load_list_records(config)
    list_meta = load_list_record_meta(config)
    detail_records = load_detail_records(config)
    entries = build_category_entries(config)
    categorized_ids = {entry.course_id for entry in entries}
    for course_id, list_record in list_records.items():
        if course_id not in categorized_ids:
            meta = list_meta.get(course_id, {})
            entries.append(
                TopicEntry(
                    fallback_category(list_record, detail_records.get(course_id, {})),
                    course_id,
                    list_record,
                    label_from_meta(meta),
                )
            )

    stats = {
        "topics_total": 0,
        "categories": {},
        "directions": {},
        "files_copied": 0,
        "missing_assets": [],
        "name_truncations": [],
    }
    manifest: list[dict[str, Any]] = []

    for entry in entries:
        category = entry.category
        course_id = entry.course_id
        list_record = entry.list_record
        detail_record = detail_records.get(course_id, {})
        title = list_record.get("name") or detail_record.get("name") or course_id
        teacher_name = list_record.get("teacherName") or detail_record.get("teacherName") or "unknown_teacher"
        direction = resolve_direction(category, title, list_record, detail_record, entry.crawl_label)

        category_dir = output_dir / make_component(category)
        direction_dir = category_dir / make_component(direction)
        topic_dir_name = make_component(title, fallback=course_id, max_bytes=180)
        topic_dir = unique_dir(direction_dir / topic_dir_name, course_id)
        topic_dir.mkdir(parents=True, exist_ok=True)

        topic_manifest = {
            "id": course_id,
            "category": category,
            "direction": direction,
            "title": title,
            "teacherName": teacher_name,
            "folder": str(topic_dir),
            "files": [],
        }

        copied = copy_course_assets(config, topic_dir, title, teacher_name, list_record, detail_record, topic_manifest, stats)
        write_json(
            topic_dir / "metadata.json",
            {
                "id": course_id,
                "category": category,
                "direction": direction,
                "title": title,
                "teacherName": teacher_name,
                "list_record": list_record,
                "detail_record": detail_record,
                "files": topic_manifest["files"],
            },
        )
        write_topic_detail_files(
            topic_dir,
            course_id,
            category,
            direction,
            title,
            teacher_name,
            list_record,
            detail_record,
            topic_manifest["files"],
        )

        stats["topics_total"] += 1
        stats["files_copied"] += copied
        stats["categories"][category] = stats["categories"].get(category, 0) + 1
        direction_key = f"{category}/{direction}"
        stats["directions"][direction_key] = stats["directions"].get(direction_key, 0) + 1
        if topic_dir.name != title:
            stats["name_truncations"].append({"id": course_id, "title": title, "folder": topic_dir.name})
        manifest.append(topic_manifest)

    write_json(config.reports_dir / "organized_assets_manifest.json", manifest)
    write_json(config.reports_dir / "organized_assets_stats.json", stats)


def load_list_records(config: CrawlConfig) -> OrderedDict[str, dict[str, Any]]:
    records: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in iter_jsonl(config.raw_dir / "list_records.jsonl"):
        record = list_record_from_row(row)
        if isinstance(record, dict):
            course_id = course_id_of(record)
            if course_id:
                records[course_id] = record
    return records


def load_detail_records(config: CrawlConfig) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(config.raw_dir / "detail_responses.jsonl"):
        payload = row.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            course_id = str(data.get("id") or row.get("id") or "")
            if course_id:
                records[course_id] = data
    return records


def load_list_record_meta(config: CrawlConfig) -> dict[str, dict[str, Any]]:
    meta_by_id: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(config.raw_dir / "list_records.jsonl"):
        record = list_record_from_row(row)
        if isinstance(record, dict):
            course_id = course_id_of(record)
            if not course_id:
                continue
            meta_by_id[course_id] = {
                "label": row.get("label"),
                "seed": row.get("seed"),
                "source_url": row.get("source_url"),
                "page": row.get("page"),
            }
    return meta_by_id


def build_category_membership(config: CrawlConfig) -> dict[str, str]:
    membership: dict[str, str] = {}
    seed_index = 0
    last_signature: tuple[str | None, int | None] | None = None
    for row in iter_jsonl(config.raw_dir / "list_responses.jsonl"):
        payload = row.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            continue
        signature = (row.get("api"), data.get("allNumber"))
        if signature != last_signature or row.get("page") == 1:
            seed_index += 1
            last_signature = signature
        category = CATEGORY_BY_SEED.get(seed_index)
        if not category:
            continue
        for record in data.get("courseList") or []:
            course_id = course_id_of(record)
            if course_id and course_id not in membership:
                membership[course_id] = category
    return membership


def build_category_entries(config: CrawlConfig) -> list[TopicEntry]:
    entries: list[TopicEntry] = []
    seen_in_category: set[tuple[str, str]] = set()
    seed_index = 0
    last_signature: tuple[str | None, int | None] | None = None
    for row in iter_jsonl(config.raw_dir / "list_responses.jsonl"):
        payload = row.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            continue
        signature = (row.get("api"), data.get("allNumber"))
        if signature != last_signature or row.get("page") == 1:
            seed_index += 1
            last_signature = signature
        category = CATEGORY_BY_SEED.get(seed_index)
        if not category:
            continue
        for record in data.get("courseList") or []:
            course_id = course_id_of(record)
            if not course_id:
                continue
            key = (category, course_id)
            if key in seen_in_category:
                continue
            seen_in_category.add(key)
            entries.append(TopicEntry(category, course_id, record, label_from_meta(row)))
    return entries


def course_id_of(record: dict[str, Any]) -> str | None:
    for key in ("id", "uuid", "projectId", "courseId", "itemId", "detailId"):
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def fallback_category(list_record: dict[str, Any], detail_record: dict[str, Any]) -> str:
    explicit = list_record.get("_category") or list_record.get("category") or detail_record.get("_category")
    if explicit:
        return str(explicit)
    type_id = list_record.get("typeId") or detail_record.get("typeId")
    if type_id == 56:
        return "全球在研"
    if type_id == 57:
        return "Astra 1v1"
    if type_id == 38:
        return "2026暑期线下科研项目"
    return "未归类"


def copy_course_assets(
    config: CrawlConfig,
    topic_dir: Path,
    title: str,
    teacher_name: str,
    list_record: dict[str, Any],
    detail_record: dict[str, Any],
    topic_manifest: dict[str, Any],
    stats: dict[str, Any],
) -> int:
    copied = 0
    copied_urls: set[str] = set()

    copied += copy_named_url(
        config,
        list_record.get("courseImgUrl"),
        topic_dir,
        title,
        "课程海报",
        topic_manifest,
        stats,
        copied_urls,
    )
    copied += copy_named_url(
        config,
        detail_record.get("teacherHeadImgUrl") or list_record.get("teacherHeadImgUrl"),
        topic_dir,
        teacher_name,
        "教授头像",
        topic_manifest,
        stats,
        copied_urls,
    )
    copied += copy_named_url(
        config,
        list_record.get("imageHeader") or detail_record.get("imageHeader"),
        topic_dir,
        f"{title}_缩略图",
        "列表缩略图",
        topic_manifest,
        stats,
        copied_urls,
    )
    copied += copy_named_url(
        config,
        detail_record.get("dTeacherHeaderImageUrl"),
        topic_dir,
        f"{teacher_name}_副导师头像",
        "副导师头像",
        topic_manifest,
        stats,
        copied_urls,
    )

    for attachment in detail_record.get("allAttachmentsArray") or []:
        if isinstance(attachment, dict):
            copied += copy_named_url(
                config,
                attachment.get("url"),
                topic_dir,
                attachment.get("str") or "附件",
                "附件",
                topic_manifest,
                stats,
                copied_urls,
            )

    known = {
        list_record.get("courseImgUrl"),
        detail_record.get("teacherHeadImgUrl"),
        list_record.get("teacherHeadImgUrl"),
        list_record.get("imageHeader"),
        detail_record.get("imageHeader"),
        detail_record.get("dTeacherHeaderImageUrl"),
    }
    for url in deep_find_asset_urls({"list": list_record, "detail": detail_record}):
        if url in known or url in copied_urls:
            continue
        copied += copy_named_url(
            config,
            url,
            topic_dir,
            source_stem(url),
            "其他素材",
            topic_manifest,
            stats,
            copied_urls,
        )
    return copied


DIRECTION_KEYS = {
    "direction",
    "directionName",
    "researchDirection",
    "researchDirectionName",
    "topicDirection",
    "topicDirectionName",
    "level2Name",
    "levelTwoName",
    "courseLevel2Name",
    "courseLevel3Name",
    "secondLevelName",
    "subCategory",
    "subCategoryName",
    "subject",
    "subjectName",
    "major",
    "majorName",
    "field",
    "fieldName",
}


GENERIC_LABELS = {
    "all",
    "aiHub",
    "domestic",
    "未归类",
}


def resolve_direction(
    category: str,
    title: str,
    list_record: dict[str, Any],
    detail_record: dict[str, Any],
    crawl_label: str | None,
) -> str:
    for value in iter_direction_candidates(list_record):
        if is_usable_direction(value, category, title):
            return value
    for value in iter_direction_candidates(detail_record):
        if is_usable_direction(value, category, title):
            return value
    for value in split_label(crawl_label):
        if is_usable_direction(value, category, title):
            return value
    return "未分方向"


def iter_direction_candidates(value: Any) -> list[str]:
    candidates: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, inner in node.items():
                if key in DIRECTION_KEYS:
                    candidates.extend(string_values(inner))
                elif isinstance(inner, (dict, list)):
                    walk(inner)
        elif isinstance(node, list):
            for inner in node:
                if isinstance(inner, (dict, list)):
                    walk(inner)

    walk(value)
    return candidates


def string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, dict):
        for key in ("name", "label", "title", "value"):
            if value.get(key):
                return string_values(value[key])
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(string_values(item))
        return out
    return []


def split_label(label: str | None) -> list[str]:
    if not label:
        return []
    text = str(label).strip()
    if not text or text.startswith(("typeIdList=", "pageType=")):
        return []
    for sep in ("+", "/", "／", ">", "｜", "|", ",", "，"):
        text = text.replace(sep, "\n")
    return [part.strip() for part in text.splitlines() if part.strip()]


def is_usable_direction(value: str, category: str, title: str) -> bool:
    text = str(value).strip()
    if not text:
        return False
    if text in GENERIC_LABELS:
        return False
    if text == category or text == title:
        return False
    if "=" in text:
        return False
    return True


def label_from_meta(meta: dict[str, Any]) -> str | None:
    label = meta.get("label")
    return str(label) if label not in (None, "") else None


def list_record_from_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    record = row.get("record")
    if isinstance(record, dict):
        return record
    if course_id_of(row):
        return row
    return None


def write_topic_detail_files(
    topic_dir: Path,
    course_id: str,
    category: str,
    direction: str,
    title: str,
    teacher_name: str,
    list_record: dict[str, Any],
    detail_record: dict[str, Any],
    files: list[dict[str, Any]],
) -> None:
    asset_urls = deep_find_asset_urls({"list": list_record, "detail": detail_record})
    pdf_urls = [url for url in asset_urls if Path(urlsplit(url).path).suffix.lower() == ".pdf"]
    detail_info = {
        "id": course_id,
        "category": category,
        "direction": direction,
        "title": title,
        "teacherName": teacher_name,
        "asset_urls": asset_urls,
        "pdf_urls": pdf_urls,
        "files": files,
        "list_record": list_record,
        "detail_record": detail_record,
    }
    write_json(topic_dir / "详情页信息.json", detail_info)
    write_detail_markdown(topic_dir / "详情页信息.md", detail_info)


def write_detail_markdown(path: Path, detail_info: dict[str, Any]) -> None:
    files = detail_info.get("files") or []
    file_lines = [
        f"- {item.get('role', '文件')}: {Path(str(item.get('target', ''))).name or item.get('url')}"
        for item in files
        if isinstance(item, dict)
    ]
    pdf_lines = [f"- {url}" for url in detail_info.get("pdf_urls", [])]
    text = "\n".join(
        [
            f"# {detail_info['title']}",
            "",
            f"- id: `{detail_info['id']}`",
            f"- category: `{detail_info['category']}`",
            f"- direction: `{detail_info['direction']}`",
            f"- teacherName: `{detail_info['teacherName']}`",
            "",
            "## 附件文件",
            "",
            *(file_lines or ["- none"]),
            "",
            "## PDF 附件 URL",
            "",
            *(pdf_lines or ["- none"]),
            "",
            "## 完整详情 JSON",
            "",
            "```json",
            json.dumps(detail_info.get("detail_record", {}), ensure_ascii=False, indent=2),
            "```",
        ]
    )
    path.write_text(text + "\n", encoding="utf-8")


def copy_named_url(
    config: CrawlConfig,
    url: str | None,
    topic_dir: Path,
    desired_stem: str,
    role: str,
    topic_manifest: dict[str, Any],
    stats: dict[str, Any],
    copied_urls: set[str],
) -> int:
    if not url:
        return 0
    copied_urls.add(url)
    source = asset_path(config, url)
    suffix = source.suffix or Path(urlsplit(url).path).suffix or ".bin"
    filename = make_component(desired_stem, fallback=role, max_bytes=180) + suffix
    target = unique_file(topic_dir / filename)
    entry = {"role": role, "url": url, "source": str(source), "target": str(target), "copied": False}
    if not source.exists():
        stats["missing_assets"].append(entry)
        topic_manifest["files"].append(entry)
        return 0
    link_or_copy(source, target)
    entry["copied"] = True
    topic_manifest["files"].append(entry)
    return 1


def link_or_copy(source: Path, target: Path) -> None:
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def make_component(value: Any, fallback: str = "untitled", max_bytes: int = 220) -> str:
    text = str(value or fallback).strip()
    text = text.replace("/", "／").replace(":", "：")
    text = "".join(ch for ch in text if ch not in "\\\0")
    text = text.strip(" .")
    if not text:
        text = fallback
    while len(text.encode("utf-8")) > max_bytes and len(text) > 1:
        text = text[:-1]
    return text or fallback


def unique_dir(path: Path, course_id: str) -> Path:
    if not path.exists():
        return path
    suffix = course_id[:8]
    base = make_component(path.name, max_bytes=190)
    candidate = path.with_name(make_component(f"{base}_{suffix}", max_bytes=220))
    index = 2
    while candidate.exists():
        candidate = path.with_name(make_component(f"{base}_{suffix}_{index}", max_bytes=220))
        index += 1
    return candidate


def unique_file(path: Path) -> Path:
    if not path.exists():
        return path
    stem = make_component(path.stem, max_bytes=150)
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(make_component(f"{stem}_{index}", max_bytes=180) + suffix)
        if not candidate.exists():
            return candidate
        index += 1


def source_stem(url: str) -> str:
    path = Path(urlsplit(url).path)
    return safe_filename(path.stem or "素材")
