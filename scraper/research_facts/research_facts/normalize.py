"""Value normalization: structure what a source already said, invent nothing.

Three rules hold for every normalizer in this module:

1. The verbatim text is always kept in ``raw_text``. Normalization only adds a
   second representation.
2. A normalizer may reformat, canonicalize a unit, or split a list. It may not
   infer. ``4周在线小组科研+2周论文指导`` becomes ``4周+2周`` -- the stated
   segments are concatenated, never summed into ``6周``.
3. Partial precision is preserved. ``2027年春季`` normalizes to year ``2027``
   with precision ``year`` and a ``term`` hint. It is never turned into a
   specific day.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Any

from .utils import clean_multiline, clean_text, comparison_key, strip_html

# --------------------------------------------------------------------------
# Result container
# --------------------------------------------------------------------------


@dataclass
class NormalizedValue:
    value: str
    rule: str
    precision: str = "exact"
    compare_key: str | None = None
    items: list[str] = dc_field(default_factory=list)
    extra: dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule": self.rule,
            "precision": self.precision,
            "compare_key": self.compare_key or comparison_key(self.value),
        }
        if self.items:
            payload["items"] = list(self.items)
        if self.extra:
            payload.update(self.extra)
        return payload


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_YMD = r"(?P<y>(?:19|20)\d{2})\s*[-/.年]\s*(?P<m>\d{1,2})\s*[-/.月]\s*(?P<d>\d{1,2})\s*日?"
_COMPACT = r"(?<!\d)(?P<y>(?:19|20)\d{2})(?P<m>\d{2})(?P<d>\d{2})(?!\d)"
_RANGE_SEP = r"\s*[-–—~～至到]\s*"
_APPROX_RE = re.compile(r"约|大约|左右|待定|暂定|tentative|tbd|approx", re.IGNORECASE)
_TERM_MAP = {"春": "spring", "夏": "summer", "秋": "autumn", "冬": "winter"}
_TERM_EN = {"spring": "spring", "summer": "summer", "fall": "autumn", "autumn": "autumn", "winter": "winter"}

_YMD_RE = re.compile(_YMD)
_COMPACT_RE = re.compile(_COMPACT)
_TERM_CN_RE = re.compile(r"(?P<y>(?:19|20)\d{2})\s*年?\s*(?P<t>春|夏|秋|冬)(?:季)?")
_TERM_EN_RE = re.compile(
    r"(?P<t>spring|summer|fall|autumn|winter)\s*[,/\s-]*\s*(?P<y>(?:19|20)\d{2})", re.IGNORECASE
)
_YEAR_ONLY_RE = re.compile(r"^(?P<y>(?:19|20)\d{2})\s*年?$")
_YEAR_MONTH_RE = re.compile(r"^(?P<y>(?:19|20)\d{2})\s*年?\s*(?P<m>\d{1,2})\s*月(?!\d)")
_YEAR_LOOSE_RE = re.compile(r"(?<!\d)(?P<y>(?:19|20)\d{2})\s*年?(?!\d)")

_DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _valid_ymd(year: int, month: int, day: int) -> bool:
    if not 1 <= month <= 12:
        return False
    limit = _DAYS_IN_MONTH[month - 1]
    if month == 2 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        limit = 28
    return 1 <= day <= limit


def _iso(year: str, month: str, day: str) -> str | None:
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None
    if not _valid_ymd(int(year), int(month), int(day)):
        return None
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _find_dates(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in _YMD_RE.finditer(text):
        iso = _iso(match.group("y"), match.group("m"), match.group("d"))
        if iso:
            spans.append((match.start(), match.end(), iso))
    for match in _COMPACT_RE.finditer(text):
        iso = _iso(match.group("y"), match.group("m"), match.group("d"))
        if iso:
            spans.append((match.start(), match.end(), iso))
    spans.sort()
    return spans


def normalize_date(raw: str) -> NormalizedValue | None:
    text = clean_text(raw)
    if not text:
        return None
    approximate = bool(_APPROX_RE.search(text))
    precision = "approximate" if approximate else "exact"

    # 1) a range of two stated dates
    spans = _find_dates(text)
    if len(spans) >= 2 and re.fullmatch(rf".*?{spans[0][2]}{_RANGE_SEP}{spans[1][2]}.*?", text):
        return NormalizedValue(
            value=f"{spans[0][2]}/{spans[1][2]}",
            rule="date_range",
            precision="range",
            extra={"start": spans[0][2], "end": spans[1][2]},
        )
    # 2) one stated date anywhere in the text
    if len(spans) == 1:
        start, end, iso = spans[0]
        surrounding = text[:start] + text[end:]
        if _APPROX_RE.search(surrounding) and not approximate:
            precision = "approximate"
        return NormalizedValue(value=iso, rule="iso_date", precision=precision)

    # 3) year + term
    match = _TERM_CN_RE.fullmatch(text)
    if match:
        return NormalizedValue(
            value=match.group("y"),
            rule="year_term",
            precision="term",
            extra={"term": _TERM_MAP[match.group("t")], "term_raw": match.group(0)},
        )
    match = _TERM_EN_RE.search(text)
    if match:
        return NormalizedValue(
            value=match.group("y"),
            rule="year_term",
            precision="term",
            extra={"term": _TERM_EN[match.group("t").lower()], "term_raw": match.group(0)},
        )

    # 4) a bare year or year+month, only when the whole string says so
    match = _YEAR_MONTH_RE.match(text)
    if match:
        month = int(match.group("m"))
        if 1 <= month <= 12:
            return NormalizedValue(
                value=f"{int(match.group('y')):04d}-{month:02d}",
                rule="year_month",
                precision="month",
                extra={"day": "not_stated"},
            )
    match = _YEAR_ONLY_RE.match(text)
    if match:
        return NormalizedValue(value=match.group("y"), rule="year_only", precision="year")
    match = _YEAR_LOOSE_RE.search(text)
    if match and approximate:
        # "2027年左右" -- the year is stated, the day is not.
        return NormalizedValue(
            value=match.group("y"),
            rule="year_only",
            precision="approximate",
            extra={"term_raw": text},
        )
    return None


# --------------------------------------------------------------------------
# Duration
# --------------------------------------------------------------------------

_UNIT_CANON = {
    "周": "周",
    "星期": "周",
    "wk": "周",
    "week": "周",
    "weeks": "周",
    "个月": "个月",
    "月": "个月",
    "month": "个月",
    "months": "个月",
    "课时": "课时",
    "学时": "课时",
    "天": "天",
    "日": "天",
    "学期": "学期",
    "term": "学期",
    "semester": "学期",
}

_NUM_UNIT = r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>周|星期|wk|weeks?|个月|月|months?|课时|学时|天|日|学期|term|semester)"
_UNIT_NAMES = r"周|星期|个月|月|课时|学时|天|日|学期"
# Both "4-6周" and "4周-6周" are common; the unit may appear once or twice.
_RANGE_RE = re.compile(
    rf"(?P<lo>\d+(?:\.\d+)?)\s*(?:(?P<unit1>{_UNIT_NAMES})\s*)?"
    rf"[-–—~～至到]\s*(?P<hi>\d+(?:\.\d+)?)\s*(?P<unit2>{_UNIT_NAMES})",
    re.IGNORECASE,
)
_SEGMENT_RE = re.compile(_NUM_UNIT, re.IGNORECASE)
_SEGMENT_SPLIT_RE = re.compile(r"[+＋\n/／,，、;；]|以及|和|及|与")
_WEEKS_ONLY = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:周|星期|weeks?|wk)\s*(?:以内|左右|上下)?\s*$", re.IGNORECASE)


def _canon_unit(unit: str) -> str:
    return _UNIT_CANON.get(unit.strip().lower(), unit.strip())


def _format_amount(number: str) -> str:
    value = float(number)
    return str(int(value)) if value.is_integer() else str(value)


def normalize_duration(raw: str) -> NormalizedValue | None:
    text = clean_multiline(raw)
    if not text:
        return None

    for range_match in _RANGE_RE.finditer(text):
        first_unit = range_match.group("unit1")
        unit = _canon_unit(first_unit or range_match.group("unit2"))
        if first_unit and _canon_unit(first_unit) != unit:
            # "4个月-6周" is not a coherent range; keep looking.
            continue
        value = f"{_format_amount(range_match.group('lo'))}-{_format_amount(range_match.group('hi'))}{unit}"
        return NormalizedValue(
            value=value,
            rule="duration_range",
            precision="range",
            extra={"unit": unit},
        )

    weeks_only = _WEEKS_ONLY.match(text)
    if weeks_only:
        value = f"{_format_amount(weeks_only.group(1))}周"
        return NormalizedValue(value=value, rule="duration_weeks", precision="exact", extra={"unit": "周"})

    segments: list[dict[str, str]] = []
    for chunk in _SEGMENT_SPLIT_RE.split(text):
        if not chunk.strip():
            continue
        match = _SEGMENT_RE.search(chunk)
        if not match:
            continue
        unit = _canon_unit(match.group("unit"))
        segments.append(
            {
                "amount": _format_amount(match.group("num")),
                "unit": unit,
                "canonical": f"{_format_amount(match.group('num'))}{unit}",
                "text": clean_text(chunk),
            }
        )
    if not segments:
        return None
    if len(segments) == 1:
        canonical = segments[0]["canonical"]
        return NormalizedValue(
            value=canonical,
            rule="duration_single",
            precision="exact",
            items=[canonical],
            extra={"unit": segments[0]["unit"], "segments": segments},
        )
    # Stated segments are concatenated, never summed: 4周 + 2周 stays "4周+2周".
    return NormalizedValue(
        value="+".join(item["canonical"] for item in segments),
        rule="duration_composite",
        precision="composite",
        items=[item["canonical"] for item in segments],
        extra={"segments": segments, "arithmetic": "none"},
    )


# --------------------------------------------------------------------------
# Text fields
# --------------------------------------------------------------------------

_TITLE_PREFIX_RE = re.compile(r"^\s*(?:密集项目|科研项目|项目|课题|专题|研究计划)\s*[:：]\s*")
_BULLET_RE = re.compile(r"^\s*(?:[-*•·—–]|\d+[.、)）]|[（(]\d+[)）]|[①-⑳])\s*")
_AFFILIATION_RE = re.compile(r"[（(]([^（()）]{2,20})[)）]\s*$")


def normalize_title(raw: str) -> NormalizedValue | None:
    text = clean_text(strip_html(raw))
    if not text:
        return None
    stripped = _TITLE_PREFIX_RE.sub("", text)
    return NormalizedValue(
        value=stripped or text,
        rule="title_clean",
        precision="exact",
        compare_key=comparison_key(stripped or text),
        extra={"prefix_removed": stripped != text},
    )


def normalize_instructor(raw: str) -> NormalizedValue | None:
    text = clean_text(strip_html(raw))
    if not text:
        return None
    # A trailing "(北京大学)" is a hint about the person, not part of the name.
    # The value keeps it; the comparison key drops it, so "张三" from a poster and
    # "张三（北京大学）" from the API are recognised as the same person instead of
    # being reported as a conflict.
    affiliation = None
    match = _AFFILIATION_RE.search(text)
    compare_source = text
    if match:
        affiliation = clean_text(match.group(1))
        compare_source = text[: match.start()].strip() or text
    return NormalizedValue(
        value=text,
        rule="name_clean",
        precision="exact",
        compare_key=comparison_key(compare_source),
        extra={"affiliation_hint": affiliation} if affiliation else {},
    )


# "航空/遥感" is one audience split in two; "EI/CPCI/Scopus" is one term, not
# three deliverables. Each field therefore declares its own separators.
_AUDIENCE_SPLIT = re.compile(r"[、,，;；/]+")
_OUTPUT_SPLIT = re.compile(r"[、,，;；]+")


def _split_items(text: str, separators: re.Pattern[str]) -> list[str]:
    items: list[str] = []
    for line in text.split("\n"):
        stripped = _BULLET_RE.sub("", line).strip()
        if not stripped:
            continue
        for part in separators.split(stripped):
            cleaned = clean_text(part)
            if cleaned:
                items.append(cleaned)
    return items


def normalize_audience(raw: str) -> NormalizedValue | None:
    text = clean_multiline(strip_html(raw))
    if not text:
        return None
    items = _split_items(text, _AUDIENCE_SPLIT)
    single_line = clean_text(text.replace("\n", " "))
    return NormalizedValue(
        value=single_line,
        rule="audience_items",
        precision="exact",
        # Order-insensitive comparison so "航空、遥感" and "遥感、航空" agree.
        compare_key="|".join(sorted(comparison_key(item) for item in items)) if items else None,
        items=items,
    )


def normalize_output(raw: str) -> NormalizedValue | None:
    text = clean_multiline(strip_html(raw))
    if not text:
        return None
    items = _split_items(text, _OUTPUT_SPLIT)
    return NormalizedValue(
        value=clean_text(text.replace("\n", "；")),
        rule="output_items",
        precision="exact",
        compare_key="|".join(sorted(comparison_key(item) for item in items)) if items else None,
        items=items,
    )


NORMALIZERS = {
    "project_title": normalize_title,
    "instructor": normalize_instructor,
    "start_date": normalize_date,
    "duration": normalize_duration,
    "suitable_audience": normalize_audience,
    "output_description": normalize_output,
}


def normalize_field(field: str, raw: str) -> NormalizedValue | None:
    """Normalize one value, or return ``None`` when nothing can be derived.

    ``None`` is a normal, expected answer. The verbatim text stays in the claim
    either way; a missing normalization never becomes a missing raw value.
    """
    normalizer = NORMALIZERS.get(field)
    if normalizer is None:
        return None
    try:
        return normalizer(raw)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None
