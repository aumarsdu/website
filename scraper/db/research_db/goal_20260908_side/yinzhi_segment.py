"""T07 yinzhi public-archive segmentation (unit-based, mirrors golden rule).

The body (after ## 正文内容) splits at navLink closing lines into units.
Each unit's first title-like line is a project listing (quota-marked bold,
CJK plain, or English plain); the unit's remaining non-navigation lines are
the entry content. Consecutive zh+en units pair as one project's two
languages. Navigation lines are excluded from entries and reported.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CATEGORIES = ("理工科项目", "人文社科项目", "商科、艺术、建筑类项目")
QUOTA = re.compile(r"\\\[[^\]]*\\\]")
NAV_CLOSE = re.compile(r"^\]\(navLink:")
NAV_PATTERNS = (
    re.compile(r"^\[$"),
    re.compile(r"^\*{0,2}查看\*{0,2}$"),
    re.compile(r"^\]\(navLink:"),
    re.compile(r"^扫码预约"),
    re.compile(r"^/\s*名额有限"),
    re.compile(r"^!\[\]"),
    re.compile(r"^Pagination"),
)
CJK = re.compile(r"[\u4e00-\u9fff]")


def is_navigation(text: str) -> bool:
    stripped = text.strip()
    return any(pattern.search(stripped) for pattern in NAV_PATTERNS)


def parse_page_context(lines: list[str]) -> dict[str, str]:
    context: dict[str, str] = {}
    if not lines or lines[0].strip() != "---":
        return context
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            context[key.strip()] = value.strip().strip("'")
    return context


def title_like(text: str) -> tuple[bool, str]:
    stripped = text.strip()
    unfolded = stripped.strip("_")
    if unfolded.startswith("**") and QUOTA.search(unfolded) and len(unfolded) > 12:
        return True, "quota"
    if not stripped.startswith(("#", "*", "[")):
        if (
            CJK.search(stripped)
            and 10 <= len(stripped) <= 40
            and not stripped.startswith("!")
        ):
            return True, "cjk_plain"
        if re.match(r"^[A-Z][A-Za-z]", stripped) and 15 <= len(stripped) <= 120:
            return True, "en_plain"
    return False, ""


def segment(lines: list[str]) -> dict[str, Any]:
    page_context = parse_page_context(lines)
    highlights: list[int] = []
    body_start: int | None = None
    for i, text in enumerate(lines, start=1):
        if text.startswith("## "):
            if text.strip() == "## 重点内容":
                highlights.append(i)
            if text.strip() == "## 正文内容":
                body_start = i

    units: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    navigation_excluded: list[dict[str, Any]] = []
    if body_start is not None:
        for i in range(body_start + 1, len(lines) + 1):
            text = lines[i - 1]
            if NAV_CLOSE.match(text.strip()):
                if current:
                    units.append(current)
                current = []
                navigation_excluded.append({"line": i, "text": text.strip()[:40]})
                continue
            if text.strip():
                current.append((i, text))
        if current:
            units.append(current)

    entries: list[dict[str, Any]] = []
    category = ""
    subcategory = ""
    stopped = False
    prev_entry_index: int | None = None
    for unit in units:
        title_record: dict[str, Any] | None = None
        content_lines: list[int] = []
        for anchor, text in unit:
            stripped = text.strip()
            if stopped:
                navigation_excluded.append({"line": anchor, "text": stripped[:40]})
                continue
            if stripped in CATEGORIES:
                category = stripped
                subcategory = ""
                continue
            if stripped == "你将获得":
                category = ""
                subcategory = ""
                stopped = True
                navigation_excluded.append({"line": anchor, "text": stripped[:40]})
                continue
            if is_navigation(text) or stripped.startswith("!"):
                navigation_excluded.append({"line": anchor, "text": stripped[:40]})
                continue
            if title_record is not None:
                content_lines.append(anchor)
                continue
            if (
                category
                and stripped
                and not stripped.startswith(("#", "*", "["))
                and re.fullmatch(r"[A-Z][A-Za-z &/+',-]{2,40}", stripped)
            ):
                subcategory = stripped
                continue
            is_title, kind = title_like(text)
            if not is_title:
                content_lines.append(anchor)
                continue
            match = QUOTA.search(stripped)
            quota_tag = match.group(0) if match else ""
            title = re.sub(r"^[*_\s]+|[*_\s]+$", "", stripped.replace(quota_tag, ""))
            title_record = {
                "anchor_line": anchor,
                "kind": kind,
                "title": title,
                "language": "zh" if CJK.search(title) else "en",
                "category": category,
                "subcategory": subcategory,
                "quota_tag": quota_tag,
                "status": "confirmed",
            }
        if title_record is not None:
            title_record["content_lines"] = content_lines
            if (
                prev_entry_index is not None
                and "pair_anchor" not in entries[prev_entry_index]
                and entries[prev_entry_index]["language"] != title_record["language"]
                and entries[prev_entry_index]["category"] == title_record["category"]
            ):
                prev_anchor = entries[prev_entry_index]["anchor_line"]
                title_record["pair_anchor"] = prev_anchor
                entries[prev_entry_index]["pair_anchor"] = title_record["anchor_line"]
            prev_entry_index = len(entries)
            entries.append(title_record)

    counts = {
        "entries": len(entries),
        "confirmed": sum(1 for e in entries if e["status"] == "confirmed"),
        "pending": sum(1 for e in entries if e["status"] != "confirmed"),
        "navigation_excluded": len(navigation_excluded),
    }
    return {
        "page_context": page_context,
        "highlights_lines": highlights,
        "body_start": body_start,
        "entries": entries,
        "navigation_excluded": navigation_excluded,
        "counts": counts,
    }


def segment_file(path: Path) -> dict[str, Any]:
    return segment(path.read_text(encoding="utf-8").splitlines())
