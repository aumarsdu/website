#!/usr/bin/env python3
"""Organize processed posters by project type, subject, and topic.

The script reads the website manifests and list/detail records produced by the
full refresh. It never removes source posters; ``--dry-run`` only writes a
classification report, while a normal run copies files into the poster tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SITE_NAMES = ("domestic", "sou_tools")
SUBJECTS = {
    "金融商科",
    "理工科",
    "人文社科",
    "计算机与人工智能",
}
DOMESTIC_PAGE_SUBJECTS = {
    1: "金融商科",
    2: "理工科",
    3: "人文社科",
    4: "计算机与人工智能",
}
SOU_LABEL_SUBJECTS = {
    "金融商科": "金融商科",
    "理工": "理工科",
    "人文社科": "人文社科",
    "计算机与人工智能": "计算机与人工智能",
}
TYPE_ID_PROJECT_TYPES = {
    1: "专业选修课程",
    4: "实验室RA项目",
    38: "2026暑期线下营地项目",
    39: "2026暑期线下营地项目",
    45: "职业通途计划",
    56: "全球在研",
    57: "Astra 1v1",
}

FINANCE_WORDS = (
    "金融",
    "经济",
    "商业",
    "管理",
    "市场营销",
    "营销",
    "财务",
    "会计",
    "贸易",
    "供应链",
    "投资",
    "金融数学",
    "金融工程",
)
HUMANITIES_WORDS = (
    "文学",
    "历史",
    "哲学",
    "社会学",
    "教育",
    "心理",
    "政治",
    "法律",
    "传播",
    "语言",
    "人类学",
    "艺术",
    "音乐",
    "电影",
    "考古",
    "国际关系",
    "公共政策",
)
COMPUTER_WORDS = (
    "计算机",
    "人工智能",
    "数据科学",
    "机器学习",
    "深度学习",
    "软件",
    "编程",
    "电子",
    "通信",
    "机器人",
    "数字媒体",
    "人机交互",
    "网络安全",
    "算法",
    "芯片",
)


@dataclass(frozen=True)
class PosterRecord:
    site: str
    source: Path
    record_id: str
    title: str
    project_type: str
    subject: str
    topic_dir: str


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def safe_component(value: str, fallback: str = "未命名", max_bytes: int = 180) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value)).strip()
    text = text.replace("/", "／").replace("\\", "＼")
    text = re.sub(r"\s+", " ", text)
    if not text:
        text = fallback
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    trimmed = encoded[:max_bytes]
    while True:
        try:
            return trimmed.decode("utf-8").rstrip() or fallback
        except UnicodeDecodeError:
            trimmed = trimmed[:-1]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_list_meta(path: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_jsonl(path):
        record = row.get("record") if isinstance(row.get("record"), dict) else row
        record_id = record.get("id")
        if record_id:
            result[str(record_id)].append({"label": row.get("label"), "record": record})
    return result


def load_detail_meta(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        record_id = row.get("record_key") or (row.get("raw") or {}).get("id")
        if record_id:
            result[str(record_id)] = row.get("raw") or {}
    return result


def page_subject(entries: list[dict[str, Any]]) -> str | None:
    for entry in entries:
        match = re.search(r"pageType=(\d+)", str(entry.get("label") or ""))
        if match and int(match.group(1)) in DOMESTIC_PAGE_SUBJECTS:
            return DOMESTIC_PAGE_SUBJECTS[int(match.group(1))]
    for entry in entries:
        label = str(entry.get("label") or "").strip()
        if label in SOU_LABEL_SUBJECTS:
            return SOU_LABEL_SUBJECTS[label]
    return None


def direction_subject(entries: list[dict[str, Any]]) -> str | None:
    for entry in entries:
        direction_id = (entry.get("record") or {}).get("directionId")
        if direction_id == 7:
            return "金融商科"
        if direction_id == 11:
            return "理工科"
        if direction_id == 17:
            return "人文社科"
    return None


def infer_subject(title: str, detail: dict[str, Any]) -> str:
    text = " ".join(
        str(detail.get(key) or "")
        for key in ("name", "fitList", "suggestBasics", "foundationCourseName")
    )
    text = f"{title} {text}"
    if any(word in text for word in COMPUTER_WORDS):
        return "计算机与人工智能"
    if any(word in text for word in HUMANITIES_WORDS):
        return "人文社科"
    if any(word in text for word in FINANCE_WORDS):
        return "金融商科"
    return "理工科"


def project_type(detail: dict[str, Any], title: str) -> str:
    raw_type = str(detail.get("types") or "").strip()
    if raw_type == "研助起航系列" or "研助起航计划" in title:
        return "研助起航计划"
    if raw_type in {"全球在研", "全球在研ultra"}:
        return "全球在研"
    type_id = detail.get("typeId")
    if type_id in TYPE_ID_PROJECT_TYPES:
        return TYPE_ID_PROJECT_TYPES[type_id]
    if raw_type:
        return raw_type
    return "未归类项目类型"


def build_records(root: Path, output_root: Path) -> list[PosterRecord]:
    records: list[PosterRecord] = []
    for site in SITE_NAMES:
        site_root = root.parent / "output" / "full_refresh" / "20260703-new-check" / site
        source_root = root / "全量处理" / "20260703-new-check" / site
        manifest_by_id = {
            str(item["id"]): item for item in load_json(site_root / "posters_manifest.json")
        }
        list_meta = load_list_meta(site_root / "raw" / "list_records.jsonl")
        detail_meta = load_detail_meta(site_root / "processed" / "records.jsonl")
        for source in sorted(source_root.glob("Finish*")):
            if source.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            record_id = source.name.removeprefix("Finish").split("_", 1)[0]
            item = manifest_by_id.get(record_id, {})
            title = str(item.get("title") or source.stem.removeprefix("Finish"))
            detail = detail_meta.get(record_id, {})
            entries = list_meta.get(record_id, [])
            subject = page_subject(entries) or direction_subject(entries) or infer_subject(title, detail)
            records.append(
                PosterRecord(
                    site=site,
                    source=source,
                    record_id=record_id,
                    title=title,
                    project_type=project_type(detail, title),
                    subject=subject if subject in SUBJECTS else "未归类学科",
                    topic_dir=safe_component(title),
                )
            )
    return records


def destination_for(record: PosterRecord, output_root: Path, used_topics: set[Path]) -> Path:
    topic = output_root / safe_component(record.project_type) / safe_component(record.subject) / record.topic_dir
    if topic in used_topics:
        topic = output_root / safe_component(record.project_type) / safe_component(record.subject) / (
            f"{record.topic_dir}_{record.record_id[:8]}"
        )
    used_topics.add(topic)
    return topic / record.source.name


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def organize(root: Path, output_root: Path, dry_run: bool) -> dict[str, Any]:
    records = build_records(root, output_root)
    used_topics: set[Path] = set()
    rows: list[dict[str, Any]] = []
    collisions: list[dict[str, str]] = []
    source_names: dict[Path, PosterRecord] = {}
    for record in records:
        destination = destination_for(record, output_root, used_topics)
        if destination in source_names:
            destination = destination.with_name(
                f"{destination.stem}__{record.site}{destination.suffix}"
            )
            collisions.append({"destination": str(destination), "record_id": record.record_id})
        source_names[destination] = record
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(record.source, destination)
        rows.append(
            {
                "site": record.site,
                "record_id": record.record_id,
                "title": record.title,
                "project_type": record.project_type,
                "subject": record.subject,
                "source": str(record.source),
                "destination": str(destination),
                "sha256": sha256(record.source),
            }
        )

    manifest_path = output_root / "_organization_manifest.json"
    summary = {
        "records": len(rows),
        "by_site": dict(Counter(row["site"] for row in rows)),
        "by_project_type": dict(Counter(row["project_type"] for row in rows)),
        "by_subject": dict(Counter(row["subject"] for row in rows)),
        "collisions": collisions,
        "unclassified": [row for row in rows if row["subject"] == "未归类学科" or row["project_type"] == "未归类项目类型"],
        "dry_run": dry_run,
    }
    if not dry_run:
        write_json(manifest_path, rows)
        write_json(output_root / "_organization_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("poster"))
    parser.add_argument("--output-root", type=Path, default=Path("poster"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = organize(args.root, args.output_root, args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
