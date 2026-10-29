"""T06 yanqu OCR field extraction: candidates bound to poster + text-block evidence.

Rules are deterministic and reviewed; every extracted value carries evidence
(poster path, block index, block text, confidence). Low-confidence or
conflicting candidates become pending_review, never silently dropped.
Key fields: title, instructor, start_date, price.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATE_FULL = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
DATE_NO_YEAR = re.compile(
    r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日|(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)"
)
PRICE_MARK = re.compile(r"¥|￥|\d[\d,]{2,}\s*元|学费|课程费用")
ROLE_LABEL = re.compile(r"产学研导师|客座导师|学术导师|项目导师")
NAME_TOKEN = re.compile(r"^([A-Z][.A-Z]{1,7}|[\u4e00-\u9fff]{2,4})$")
DURATION_MARK = re.compile(r"^\d+\s*(周|次)$")
JUNK = re.compile(r"Pagination|@tiktok|^\d{1,4}$|推荐信|实习内推")


def _evidence(blocks: list[dict[str, Any]], index: int) -> dict[str, Any]:
    return {
        "block_index": index,
        "confidence": blocks[index]["confidence"],
        "text": blocks[index]["text"],
    }


def _state(confidence: float, conflicts: int) -> str:
    if conflicts > 1 or confidence < 0.99:
        return "pending_review"
    return "value"


def _find_all(
    pattern: re.Pattern[str], texts: list[str]
) -> list[tuple[int, re.Match[str]]]:
    matches: list[tuple[int, re.Match[str]]] = []
    for index, text in enumerate(texts):
        match = pattern.search(text)
        if match is not None:
            matches.append((index, match))
    return matches


def extract_fields(poster_path: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract key-field candidates with poster+block evidence."""
    texts = [b["text"] for b in blocks]

    # ---- start_date: full date preferred; missing-year flagged for review
    date_candidates = _find_all(DATE_FULL, texts)
    no_year = _find_all(DATE_NO_YEAR, texts)
    start_date: dict[str, Any] = {"state": "not_provided", "evidence": []}
    if date_candidates:
        index, match = date_candidates[0]
        raw = match.group(0)
        start_date = {
            "state": _state(blocks[index]["confidence"], len(date_candidates)),
            "value_raw": raw,
            "value": f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}",
            "precision": "day",
            "evidence": [_evidence(blocks, index)],
            "conflicts": len(date_candidates),
        }
    elif no_year:
        index, match = no_year[0]
        month = match.group(1) if match.group(1) else match.group(3)
        day = match.group(2) if match.group(2) else match.group(4)
        start_date = {
            "state": "pending_review",
            "value_raw": match.group(0),
            "value": f"--{int(month):02d}-{int(day):02d}",
            "precision": "day",
            "missing_year": True,
            "evidence": [_evidence(blocks, index)],
            "conflicts": len(no_year),
        }

    # ---- price: explicit marks only; '价格分布' style prose must not match
    price_candidates = [i for i, t in enumerate(texts) if PRICE_MARK.search(t)]
    price: dict[str, Any] = {"state": "not_provided", "evidence": []}
    if price_candidates:
        index = price_candidates[0]
        price = {
            "state": "pending_review",
            "value_raw": texts[index],
            "evidence": [_evidence(blocks, index)],
            "conflicts": len(price_candidates),
        }

    # ---- instructor: name-like token right after a role-label block
    instructor_candidates: list[int] = []
    for index, text in enumerate(texts):
        if ROLE_LABEL.search(text) and index + 1 < len(blocks):
            nxt = texts[index + 1]
            if NAME_TOKEN.match(nxt) and not JUNK.search(nxt):
                instructor_candidates.append(index + 1)
    instructor: dict[str, Any] = {"state": "not_provided", "evidence": []}
    if instructor_candidates:
        index = instructor_candidates[0]
        instructor = {
            "state": _state(blocks[index]["confidence"], len(instructor_candidates)),
            "value": texts[index],
            "evidence": [_evidence(blocks, index)],
            "conflicts": len(instructor_candidates),
        }

    # ---- title: top-zone lines (before first duration/price mark), category excluded
    title_blocks: list[int] = []
    for index, text in enumerate(texts):
        if index > 0 and (DURATION_MARK.match(text) or PRICE_MARK.search(text)):
            break
        if index > 0:
            title_blocks.append(index)
    title: dict[str, Any] = {"state": "not_provided", "evidence": []}
    title_lines = [texts[i] for i in title_blocks if len(texts[i]) >= 6]
    if title_lines:
        title = {
            "state": "pending_review",
            "value": "".join(title_lines[:3]),
            "evidence": [_evidence(blocks, i) for i in title_blocks[:3]],
        }

    return {
        "poster_path": poster_path,
        "fields": {
            "title": title,
            "instructor": instructor,
            "start_date": start_date,
            "price": price,
        },
    }


def load_csv_rows(csv_path: Path) -> dict[int, dict[str, str]]:
    import csv as _csv

    with open(csv_path, newline="", encoding="utf-8") as handle:
        return {i: row for i, row in enumerate(_csv.DictReader(handle), start=1)}


def extract_poster(
    csv_rows: dict[int, dict[str, str]], csv_row: int, poster_path: str
) -> dict[str, Any]:
    row = csv_rows[csv_row]
    blocks = json.loads(row["text_blocks_json"])
    return extract_fields(poster_path, blocks)
