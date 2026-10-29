"""Pure classification rules for the 河狸陪夏校 derived library.

Extracted from helipei_summer so the category/inference heuristics can be
unit-tested without touching SQLite. Add new poster/type rules here.
"""

from __future__ import annotations

import re
from typing import Any


SUMMER_TYPES = {
    "低龄走读营",
    "无学分大学营",
    "在线夏校",
    "中学营",
    "有学分大学营",
    "艺术营",
    "综合营",
    "语言营",
    "户外体育营",
    "海外课程",
    "精英夏校",
    "天才营",
    "辩论营",
    "无忧畅学夏校",
    "科技营",
    "数学营",
    "亲子营",
    "插班",
    "探校",
}

PRIMARY_SUMMER_CATEGORY = "夏校等"
EXTENSION_CATEGORIES = {"插班", "探校"}
ADJACENT_TYPES = {"海外科研", "在线科研", "国内科研", "思维训练"}


def standardize_category(source_category: str | None, source_type: str | None, title: str | None) -> tuple[str, str]:
    text = f"{source_category or ''} {source_type or ''} {title or ''}"
    rules = [
        (r"有学分", ("大学夏校", "有学分大学夏校")),
        (r"无学分|pre-college|大学营", ("大学夏校", "无学分大学夏校")),
        (r"在线", ("线上项目", "线上夏校")),
        (r"低龄|中学营|Middle School", ("低龄夏校", "低龄/中学营")),
        (r"艺术|设计|戏剧", ("主题营", "艺术设计营")),
        (r"数学", ("主题营", "数学营")),
        (r"科技|AI|IT", ("主题营", "科技/AI营")),
        (r"语言|ESL|英语", ("主题营", "语言提升营")),
        (r"辩论|演讲|领导力", ("主题营", "辩论/演讲/领导力营")),
        (r"户外|体育|Outdoor", ("主题营", "户外体育营")),
        (r"探校", ("探校项目", "探校")),
        (r"插班", ("插班项目", "插班")),
        (r"科研", ("科研型夏校", "科研项目")),
        (r"亲子", ("低龄夏校", "亲子营")),
        (r"天才|精英", ("高选择性项目", source_type or "精英/天才营")),
    ]
    for pattern, result in rules:
        if re.search(pattern, text, re.I):
            return result
    if source_category == PRIMARY_SUMMER_CATEGORY:
        return "夏校项目", source_type or "其他夏校"
    return "相邻项目", source_type or source_category or "待归类"


def infer_library_scope(source_category: str | None, source_type: str | None) -> str:
    if source_category == PRIMARY_SUMMER_CATEGORY:
        return "primary_summer"
    if source_category == "插班" or source_type == "插班":
        return "extension_join_class"
    if source_category == "探校" or source_type == "探校":
        return "extension_campus_visit"
    if source_type in ADJACENT_TYPES:
        return "adjacent_enrichment"
    return "summer_related"


def infer_delivery_mode(source_type: str | None, title: str | None, description: str | None) -> str:
    text = f"{source_type or ''} {title or ''} {description or ''}"
    if re.search(r"在线|线上|online|remote", text, re.I):
        return "online"
    if re.search(r"混合|hybrid", text, re.I):
        return "hybrid"
    return "offline"


def infer_residential(value: Any, source_type: str | None, title: str | None, description: str | None) -> str:
    if value is True or str(value).lower() == "true":
        return "residential"
    if value is False or str(value).lower() == "false":
        return "day_or_unknown"
    text = f"{source_type or ''} {title or ''} {description or ''}"
    if re.search(r"住宿|residential|boarding", text, re.I):
        return "residential"
    if re.search(r"走读|day camp", text, re.I):
        return "day"
    if re.search(r"在线|线上|online", text, re.I):
        return "online"
    return "unknown"


def infer_credit(value: Any, source_type: str | None, title: str | None, description: str | None) -> str:
    if value is True or str(value).lower() == "true":
        return "credit"
    if value is False or str(value).lower() == "false":
        return "non_credit_or_unknown"
    text = f"{source_type or ''} {title or ''} {description or ''}"
    # 负向规则必须先于正向规则："non-credit" 包含子串 "credit"。
    if re.search(r"无学分|non[-_ ]?credit", text, re.I):
        return "non_credit"
    if re.search(r"有学分|credit", text, re.I):
        return "credit"
    return "unknown"

