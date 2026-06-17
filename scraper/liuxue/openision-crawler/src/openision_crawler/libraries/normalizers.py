from __future__ import annotations

from typing import Any


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_fee(raw_fee: Any, tuition_cn: Any) -> tuple[float | None, bool, str | None]:
    amount = parse_float(raw_fee)
    display = text_or_none(tuition_cn)
    if amount is None or amount <= 0:
        return None, False, display
    return amount, True, display


def normalize_admission_year(value: Any) -> tuple[int | None, bool]:
    if value is None:
        return None, False
    text = str(value).strip()
    if not text or text == "0000":
        return None, False
    try:
        year = int(text)
    except ValueError:
        return None, False
    if 2010 <= year <= 2030:
        return year, True
    return None, False


def normalize_school_tag(value: Any) -> str:
    return text_or_none(value) or "未知背景"
