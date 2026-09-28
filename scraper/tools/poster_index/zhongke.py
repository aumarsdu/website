"""中科浩博 index builder (需求文档 3.1 / 三期), 含学科打标与 overrides."""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from . import common
from .common import OUTPUT_DIR, SCRAPER_ROOT

SUPPLIER = "中科浩博"
ROOT = SCRAPER_ROOT / "中科"
PROCESSED = ROOT / "output/processed/projects.jsonl"
NEW_PROCESSED = ROOT / "output_check_20260703/new_projects/processed/new_projects.jsonl"
POSTER_SHUANG = ROOT / "Poster/双教授课题（鲸鱼座）"
POSTER_ZHONGFANG = ROOT / "Poster/中方课题（研途有果）"
OCT_INVENTORY = ROOT / "中科-开课时间-2026年10月1日以后/poster_inventory.csv"
OVERRIDES_PATH = OUTPUT_DIR / "中科浩博.subject_overrides.json"

# 主导学科判读规则（与 overrides 生成逻辑一致）：取标题首部学科定语按序匹配。
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("计算机与人工智能", (
        "人工智能", "AI", "机器学习", "深度学习", "数据科学", "数据分析", "计算机科学", "计算机",
        "软件工程", "软件", "编程", "算法", "网络安全", "网络与信息安全", "信息安全", "密码学",
        "人机交互", "交互设计", "MIS", "管理信息系统", "脑机接口", "虚拟场景", "网络系统",
    )),
    ("人文社科", (
        "应用语言学", "实验语言学", "认知语言学", "认知神经与语言学", "语言学", "TESOL", "翻译",
        "语言教育", "教育学", "教育", "数字教育", "教育领导力", "教育心理", "心理", "传播学",
        "传媒", "传播", "新媒体", "媒体", "数字媒体", "新闻", "广告", "影视", "电影", "动画",
        "艺术史", "艺术研究", "艺术", "戏剧", "文学", "性别研究", "哲学", "宗教", "历史", "考古",
        "全球史", "社会学", "公共政策", "公共管理", "公共治理", "国际关系", "国际安全", "全球安全",
        "全球治理", "政治", "国际法", "国际法治", "法律", "法学", "法经济", "合同法", "侵权法",
        "刑法", "民商法", "商法", "金融法", "信息科技法", "环境法", "司法",
    )),
    ("金融商科", (
        "计量经济", "健康经济", "环境经济", "能源经济", "劳动经济", "社会经济", "应用经济", "经济",
        "金融工程", "金融科技", "金融", "投资", "资本市场", "会计", "营销", "市场营销", "品牌",
        "市场管理", "消费者", "商业分析", "商业", "工商管理", "企业管理", "企业战略", "企业融资",
        "企业治理", "战略管理", "公司", "人力资源", "管理会计", "管理", "供应链", "物流", "贸易",
        "数字营销", "自媒体", "工程管理", "数字化战略", "ESG", "估值",
    )),
    ("理工科", (
        "机械", "车辆", "航空", "飞机", "土木", "建筑", "城市规划", "城市与交通", "工程",
        "工业工程", "智能制造", "机器人", "自动化", "传感器", "集成电路", "芯片", "半导体",
        "微处理器", "微电子", "嵌入式", "电子信息", "电子工程", "EE", "ECE", "通信工程", "通信",
        "信号", "光电", "光通信", "光子", "电力", "电路", "硬件", "物联网", "卫星", "数学",
        "应用数学", "统计", "概率", "蒙特卡洛", "运筹", "决策优化", "热力学", "物理", "天文",
        "量子", "天文动力", "遥感", "地理信息", "GIS", "地理", "测绘", "气候", "气象", "厄尔尼诺",
        "双碳", "环境", "能源", "大气", "生物信息", "生物", "基因", "神经科学", "脑科学", "脑疾病",
        "神经", "医学", "医药", "药物", "药理", "临床", "疾病", "免疫", "疫苗", "公共卫生",
        "流行病学", "质谱", "营养", "食品", "运动科学", "运动生理", "运动康复", "运动人体",
        "衰老", "生命科学", "环境管理", "智慧交通", "智能硬件", "智能遥", "农业",
    )),
]
_LEAD_SPLIT = re.compile(r"[：:（(]")


def rule_tag(title: str, description: str = "") -> tuple[str | None, str]:
    """按标题首部学科定语判定主导学科；首部无命中再查全文；否则 None。"""
    del description  # 简介多学科词会制造歧义，仅用标题（2026-09-28 实测口径）
    lead = _LEAD_SPLIT.split(title, 1)[0]
    for lead_only in (True, False):
        text = lead if lead_only else title
        for subject, keywords in RULES:
            matched = [kw for kw in keywords if kw.lower() in text.lower()]
            if matched:
                zone = "首部" if lead_only else "全文"
                return subject, f"主导学科({zone})关键词: {','.join(matched[:5])}"
    return None, "无学科定语命中"


def _load_overrides() -> dict[str, dict[str, Any]]:
    if not OVERRIDES_PATH.exists():
        return {}
    data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("overrides"), dict):
        return data["overrides"]
    return data


def _apply_subject(
    title: str,
    *,
    supplier_subject: str | None,
    supplier_native: bool,
    description: str,
    overrides: dict[str, dict[str, Any]],
    stats: dict[str, int],
    others: list[dict[str, str]],
) -> tuple[str, str, str]:
    """Return (subject, subjectSource, basis); 记录打标依据（需求 5.3）。"""
    override = overrides.get(title)
    if override and override.get("subject") in common.SUBJECTS:
        stats["override"] += 1
        return str(override["subject"]), "tagged", f"人工/LLM修正覆盖: {override.get('basis', '')}"
    mapped = common.map_subject(supplier_subject)
    if mapped:
        stats["supplier" if supplier_native else "tagged"] += 1
        source = "供应商分类" if supplier_native else "爬虫关键词兜底"
        return mapped, ("supplier" if supplier_native else "tagged"), f"{source}: {supplier_subject}"
    subject, basis = rule_tag(title, description)
    if subject:
        stats["tagged"] += 1
        return subject, "tagged", basis
    stats["other"] += 1
    others.append({"title": title, "basis": basis})
    return "其他", "tagged", basis


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
    return common.dedup_keep_latest(
        records,
        key_fn=lambda r: next((str(r.get(f) or "") for f in id_fields if r.get(f)), ""),
        crawled_fn=lambda r: r.get("crawled_at"),
    )


def _poster_stem_map(folder: Path) -> dict[str, list[Path]]:
    """课题标题 -> 海报文件列表（文件名 Finish<标题>__<hash>.jpg，目录名即标题）。"""
    out: dict[str, list[Path]] = {}
    for f in folder.rglob("*"):
        if f.is_file() and common.is_image(f):
            stem = f.parent.name if len(f.relative_to(folder).parts) > 1 else None
            if not stem:
                match = re.match(r"^(?:Finish)?(.+?)__[0-9a-f]{8,}\.(?:jpg|png|jpeg|webp)$", f.name, re.IGNORECASE)
                stem = match.group(1).strip() if match else None
            if stem:
                out.setdefault(stem, []).append(f)
    return out


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
    overrides = _load_overrides()
    oct_by_id, oct_by_title = _october_dates()
    items: list[dict[str, Any]] = []
    missing_posters: list[str] = []
    orphan_posters: list[str] = []
    subject_counts: dict[str, int] = {}
    tag_stats: dict[str, int] = {"supplier": 0, "tagged": 0, "override": 0, "other": 0}
    others: list[dict[str, str]] = []
    variant_counts = {"processed": 0, "raw": 0}
    with_dates = future = 0
    today = date.today().isoformat()

    # ---- 双教授课题：库内分类 + 站点目录结构 ----
    shuang = _load_records(PROCESSED, ("uuid", "id"))
    shuang_posters = _poster_stem_map(POSTER_SHUANG)
    for record in shuang:
        title = str(record.get("title") or "").strip()
        rid = str(record.get("uuid") or record.get("id") or "")
        native = record.get("taxonomy_source") == "topic_category"
        subject, source, _basis = _apply_subject(
            title,
            supplier_subject=record.get("category"),
            supplier_native=native,
            description=str(record.get("description") or ""),
            overrides=overrides,
            stats=tag_stats,
            others=others,
        )
        subject_counts[subject] = subject_counts.get(subject, 0) + 1
        candidates = shuang_posters.get(title, [])
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
            subjectSource=source,
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
    known_titles = {str(r.get("title") or "").strip() for r in zhongfang}
    for record in zhongfang:
        title = str(record.get("title") or "").strip()
        rid = str(record.get("uuid") or record.get("id") or "")
        raw = record.get("raw") or {}
        subject, source, _basis = _apply_subject(
            title,
            supplier_subject=None,
            supplier_native=False,
            description="",
            overrides=overrides,
            stats=tag_stats,
            others=others,
        )
        subject_counts[subject] = subject_counts.get(subject, 0) + 1
        candidates = zhong_posters.get(title, [])
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
            subjectSource=source,
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

    for stem in zhong_posters:
        if stem not in known_titles:
            orphan_posters.extend(str(p) for p in zhong_posters[stem])

    # 最终标注为"其他"的条目（含 overrides 指定）一律进入人工确认清单（需求 5.3/验收）
    others.extend(
        {"title": i["title"], "basis": f"覆盖标注为其他（{i.get('recordId')}），待军亮确认"}
        for i in items
        if i["subject"] == "其他"
    )

    report = {
        "total_courses": len(shuang) + len(zhongfang),
        "posters_found": len(items),
        "missing_poster_ids": sorted(missing_posters)[:200],
        "orphan_poster_files": len(orphan_posters),
        "with_school_begins": with_dates,
        "school_begins_future": future,
        "subject_distribution": subject_counts,
        "poster_variant_distribution": variant_counts,
        "tagging": {"stats": tag_stats, "needs_manual_review": others},
    }
    return items, report
