"""Generate and freeze the T07 yinzhi segmentation golden (unit-based).

Ground-truth rule (pure document structure, independent of the segmenter):
the body (after ## 正文内容) is split at navLink closing lines into units.
Each unit whose first nonempty line is title-like is a project listing:
  - quota-marked bold title, or
  - CJK title (contains :/，, length 10-40), or
  - English title line (starts uppercase letter, length 15-90)
Non-entry units: category lines, benefits section (你将获得), nav brackets,
QR footer. Consecutive zh+en entry units form a bilingual pair of one project.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SIDE = Path(__file__).resolve().parent
LINES = (
    (SIDE.parent.parent.parent / "引知/data/archive/public/content.md")
    .read_text(encoding="utf-8")
    .splitlines()
)
QUOTA = re.compile(r"\\\[[^\]]*\\\]")
NAV_CLOSE = re.compile(r"^\]\(navLink:")
CATEGORIES = ("理工科项目", "人文社科项目", "商科、艺术、建筑类项目")
CJK = re.compile(r"[\u4e00-\u9fff]")


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


body_start = next(i for i, t in enumerate(LINES, 1) if t.strip() == "## 正文内容")
units: list[list[tuple[int, str]]] = []
current: list[tuple[int, str]] = []
for i in range(body_start + 1, len(LINES) + 1):
    text = LINES[i - 1]
    if NAV_CLOSE.match(text.strip()):
        if current:
            units.append(current)
        current = []
        continue
    if text.strip():
        current.append((i, text))
if current:
    units.append(current)

entries = []
category = ""
subcategory = ""
prev_entry_index: int | None = None
stopped = False
for unit in units:
    if stopped:
        break
    for anchor, text in unit:
        stripped = text.strip()
        if stripped in CATEGORIES:
            category = stripped
            subcategory = ""
            continue
        if stripped == "你将获得":
            # benefits + QR footer zone after this point: no more entries
            category = ""
            subcategory = ""
            stopped = True
            break
        if stripped.startswith(("[", "扫码预约", "!")):
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
            continue
        # the unit's FIRST title-like line is the entry title; remaining
        # lines are instructor/description content and never entries
        m = QUOTA.search(stripped)
        quota_tag = m.group(0) if m else ""
        title = stripped.replace(quota_tag, "") if quota_tag else stripped
        title = re.sub(r"^[*_\s]+|[*_\s]+$", "", title)
        entry = {
            "anchor_line": anchor,
            "kind": kind,
            "title": title,
            "language": "zh" if CJK.search(title) else "en",
            "category": category,
            "subcategory": subcategory,
            "quota_tag": quota_tag,
            "unit_lines": [line for line, _ in unit],
        }
        if (
            prev_entry_index is not None
            and "pair_anchor" not in entries[prev_entry_index]
            and entries[prev_entry_index]["language"] != entry["language"]
            and entries[prev_entry_index]["category"] == entry["category"]
        ):
            prev_anchor = entries[prev_entry_index]["anchor_line"]
            entry["pair_anchor"] = prev_anchor
            entries[prev_entry_index]["pair_anchor"] = entry["anchor_line"]
        prev_entry_index = len(entries)
        entries.append(entry)
        break

golden = {
    "frozen_at": "2026-09-26",
    "source": "引知/data/archive/public/content.md",
    "source_sha256": hashlib.sha256(
        (SIDE.parent.parent.parent / "引知/data/archive/public/content.md").read_bytes()
    ).hexdigest(),
    "total_lines": len(LINES),
    "rule": "unit-based: body split at navLink closers; first-line title-like units are project listings; zh+en consecutive units pair as one project's two languages",
    "categories": {
        "理工科项目": 23,
        "人文社科项目": 367,
        "商科、艺术、建筑类项目": 551,
    },
    "entry_count": len(entries),
    "entries": entries,
}
out = SIDE / "fixtures" / "t07_golden.json"
out.write_text(
    json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
langs = {}
for e in entries:
    langs[e["language"]] = langs.get(e["language"], 0) + 1
pairs = sum(1 for e in entries if "pair_anchor" in e)
print("entries:", len(entries), "langs:", langs, "paired:", pairs)
print("sha256:", hashlib.sha256(out.read_bytes()).hexdigest())
