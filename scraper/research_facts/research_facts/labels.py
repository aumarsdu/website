"""Label tables and line/row scanning for text-based sources.

Extraction from a poster or a handbook is a *labeled text* problem, not a free
text-understanding problem. The rules here are therefore deliberately explicit:

1. A field is only extracted when an explicit label from :data:`LABELS` is
   found. There is no inference, no keyword guessing, and no "second value
   looks like a name" heuristic.
2. A label must be a standalone token. ``(?<![CJK])`` and ``(?![CJKa-zA-Z])``
   guards mean ``周期`` never matches inside ``项目周期`` and ``教授`` never
   matches inside ``副教授``. Compound forms such as ``项目周期`` are listed
   explicitly.
3. ``报名截止`` / ``申请截止`` are deliberately *not* labels for ``start_date``.
   A deadline is a different fact; mapping it would be a wrong answer, not a
   missing one.

Because every label is written out, updating the extractor after a layout change
is a data edit here, not a code change in the adapters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .utils import clean_text

# Characters that must not sit directly next to a label for it to count as a
# standalone token.
_CJK = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_NOT_BEFORE = f"(?<![{_CJK}])"
_NOT_AFTER = f"(?![{_CJK}A-Za-z])"
_DELIMITER = r"[\s]*[:：|｜][\s]*"
# Poster rows often have no separator at all ("周期8周"). The boundary guards do
# the disambiguation work there, so the separator itself may be empty.
_ROW_SEPARATOR = r"[\s:：|｜]*"
_VALUE_TRIM = re.compile(r"^[\s:：|｜\-–—·]+|[\s:：|｜\-–—·,，、]+$")
_SECTION_RE = re.compile(
    r"^(?:第\s*[0-9一二三四五六七八九十]+\s*[章节讲部分]"
    r"|[一二三四五六七八九十\d]+\s*[、.．]"
    r"|【)"
)


@dataclass(frozen=True)
class TextBlock:
    """One unit of text with a stable pointer back into its document."""

    text: str
    pointer: str
    detail: str = ""
    order: int = 0
    bbox: tuple[float, float, float, float] | None = None
    ocr_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:  # type: ignore[name-defined]
        return {
            "text": self.text,
            "pointer": self.pointer,
            "detail": self.detail,
            "order": self.order,
            "bbox": list(self.bbox) if self.bbox else None,
            "ocr_confidence": self.ocr_confidence,
        }


@dataclass(frozen=True)
class LabelHit:
    """One label occurrence and the text that follows it on the same line."""

    field: str
    label: str
    value: str
    start: int
    end: int
    inline_value: bool


# Explicit labels per canonical field, longest first inside each tuple.
LABELS: dict[str, tuple[str, ...]] = {
    "project_title": (
        "科研课题名称",
        "课题名称",
        "项目名称",
        "课程名称",
        "课题主题",
        "研究主题",
        "研究方向",
        "课题名",
        "科研课题",
        "课题",
        "课程",
        "Title",
        "ResearchTopic",
        "CourseTitle",
        "Topic",
    ),
    "instructor": (
        "授课教授姓名",
        "指导老师姓名",
        "指导教师姓名",
        "授课教授",
        "指导老师",
        "指导教师",
        "学术导师",
        "科研导师",
        "主导师",
        "副导师",
        "导师姓名",
        "授课老师",
        "授课教师",
        "导师",
        "副教授",
        "助理教授",
        "讲师",
        "教授",
        "教师",
        "Professor",
        "Supervisor",
        "Advisor",
        "Instructor",
        "Teacher",
    ),
    "start_date": (
        "项目开始日期",
        "首次开课日期",
        "开课日期",
        "开始日期",
        "起始日期",
        "启动日期",
        "上课日期",
        "上课时间",
        "开课时间",
        "开学日期",
        "开课日",
        "StartDate",
        "CourseStart",
        "LaunchDate",
        "Start",
    ),
    "duration": (
        "项目周期安排",
        "研究周期",
        "科研周期",
        "培养周期",
        "实施周期",
        "项目周期",
        "项目时长",
        "研究时长",
        "总周期",
        "持续时间",
        "持续周期",
        "周期安排",
        "周期",
        "时长",
        "Duration",
        "Length",
        "Period",
    ),
    "suitable_audience": (
        "适合人群",
        "适合学生",
        "适合对象",
        "适合学员",
        "适合专业",
        "适合年级",
        "面向人群",
        "面向学生",
        "面向对象",
        "适用人群",
        "适用对象",
        "目标人群",
        "招生对象",
        "申请对象",
        "推荐人群",
        "适合",
        "面向",
        "SuitableFor",
        "TargetAudience",
        "IntendedFor",
        "Eligibility",
    ),
    "output_description": (
        "结项成果",
        "结项要求",
        "最终成果",
        "成果形式",
        "产出形式",
        "项目产出",
        "研究产出",
        "科研产出",
        "成果描述",
        "产出描述",
        "成果交付",
        "交付内容",
        "交付物",
        "论文指导",
        "产出",
        "成果",
        "Deliverables",
        "ExpectedOutput",
        "Outcome",
        "Output",
    ),
}

# Fields whose value may continue on following lines.
MULTI_LINE_FIELDS: tuple[str, ...] = ("suitable_audience", "output_description")

# Labels that are only trustworthy in free text, not in a poster's geometry.
#
# Measured on 195 real supplier posters: the bare academic titles appear as
# *values* ("牛津大学 终身正教授") far more often than as field labels, and
# reading them as labels turned 3 posters' enrollment-status chips into
# "instructor = 招生中". The field labels that do appear on a poster are the
# compound forms -- 授课教授, 指导老师, 指导教师, 导师 -- and those stay.
ROW_MODE_EXCLUDED_LABELS: frozenset[str] = frozenset(
    {"教授", "讲师", "教师", "副教授", "助理教授"}
)

# A poster title is the identity anchor, so a wrong one is worse than none: it
# poisons record keys and every downstream sentence. Row-mode titles therefore
# require the value to look like a title rather than a table header, and a
# value that itself contains a label word is refused ("教授背景 招生状态" is two
# header cells, not a topic name). The cost is deliberate under-extraction --
# a real title containing e.g. "课程" is left missing, which the record shows
# openly via its external_id and poster path. The handbook/web paths are
# unaffected: they match inside text, not across geometry.
_ROW_MODE_HEADERLIKE_FIELDS: frozenset[str] = frozenset({"project_title"})


def _label_pattern(label: str) -> str:
    """Allow whitespace inside a label so ``Course Title`` matches ``CourseTitle``."""
    return r"\s*".join(re.escape(char) for char in label)


def _build_patterns(require_delimiter: bool) -> dict[str, re.Pattern[str]]:
    """Compile one alternation per field, longest label first."""
    compiled: dict[str, re.Pattern[str]] = {}
    for field, labels in LABELS.items():
        ordered = sorted(labels, key=len, reverse=True)
        alternation = "|".join(_label_pattern(label) for label in ordered)
        middle = _DELIMITER if require_delimiter else _ROW_SEPARATOR
        compiled[field] = re.compile(
            rf"{_NOT_BEFORE}(?P<label>{alternation}){_NOT_AFTER}{middle}(?P<value>[^\n]*)$"
        )
    return compiled


LINE_PATTERNS: dict[str, re.Pattern[str]] = _build_patterns(require_delimiter=True)
ROW_PATTERNS: dict[str, re.Pattern[str]] = _build_patterns(require_delimiter=False)

# Every known label, for stopping multi-line continuation.
_ALL_LABELS: tuple[str, ...] = tuple(
    sorted({label for labels in LABELS.values() for label in labels}, key=len, reverse=True)
)
# A label word appearing at the START of a value marks a header cell, not a
# statement: "教授背景 招生状态" is two column headers. Prefix matching is used
# deliberately -- the full boundary guard cannot see "教授" inside "教授背景"
# (correctly, since it is not a standalone token there), but the prefix still
# tells us the cell is a header.
_ALL_LABEL_PREFIX_RE = re.compile(
    r"^(?:" + "|".join(_label_pattern(label) for label in _ALL_LABELS) + r")"
)

_KNOWN_LABEL_RE = re.compile(
    _NOT_BEFORE
    + "(?:"
    + "|".join(_label_pattern(label) for label in _ALL_LABELS)
    + ")"
    + _NOT_AFTER
    + r"[\s]*(?:[:：|｜]|[\s]+)"
)


def _trim_value(value: str) -> str:
    return _VALUE_TRIM.sub("", value or "")


def scan_line(
    text: str, require_delimiter: bool = True, label_must_lead_row: bool = False
) -> list[LabelHit]:
    """Find every labeled value on one line, in reading order.

    More than one label per line is normal on posters, where a row may read
    ``周期 8周 课时 126``. Each label takes the text up to the next label.

    A label with an empty value is still returned (``inline_value=False``) so
    multi-line fields can pick up their continuation. Callers must drop empty
    hits for single-line fields -- an empty statement is not evidence.

    ``label_must_lead_row`` exists because of what real posters turned out to
    look like. A marketing poster carries a metadata grid whose *header* row
    is several short cells -- ``项目模式 | 项目周期 | 开班人数 | 开课日期`` --
    and a header cell is indistinguishable from a label by geometry alone: in
    the real 195-poster run, ``项目周期 | 开班人数`` and ``教授 | 招生中`` were
    read as label/value pairs and produced 49 fabricated claims, while
    ``开课时间 | 2026年09月19日`` was a genuine pair. Both have the same shape.

    What separates them is position: a real label-value pair puts the label in
    the row's first cell, and a header row never does. Requiring that turns
    every observed false positive into a refusal and keeps the true positives.
    It is deliberately fail-safe -- a right-aligned label yields a missing
    field rather than a wrong one.
    """
    if not text or not text.strip():
        return []
    patterns = LINE_PATTERNS if require_delimiter else ROW_PATTERNS
    # start, value_start, field, label, value
    found: list[tuple[int, int, str, str, str]] = []
    for field, pattern in patterns.items():
        for match in pattern.finditer(text):
            value = _trim_value(match.group("value"))
            # The value group is greedy to end of line, so the useful boundary
            # is where the value *starts*, not where the match ends.
            found.append((match.start(), match.start("value"), field, match.group("label"), value))
    found.sort()
    hits: list[LabelHit] = []
    for index, (start, value_start, field, label, value) in enumerate(found):
        # The value is the span between this label and the next label on the line.
        next_start = found[index + 1][0] if index + 1 < len(found) else len(text)
        cleaned = _trim_value(text[value_start:next_start]) or value
        hits.append(
            LabelHit(
                field=field,
                label=label,
                value=cleaned,
                start=start,
                end=value_start,
                inline_value=bool(cleaned),
            )
        )
    if label_must_lead_row:
        hits = [
            hit
            for hit in hits
            if hit.start == 0 and hit.label not in ROW_MODE_EXCLUDED_LABELS
        ]
        hits = [
            hit
            for hit in hits
            if hit.field not in _ROW_MODE_HEADERLIKE_FIELDS
            or not _ALL_LABEL_PREFIX_RE.match(hit.value)
        ]
    return hits


def template_signature(rows: Iterable[TextBlock]) -> tuple[str, ...]:
    """Which labels this layout actually offers, in a stable order.

    A poster that never puts a label in a row's first cell is a different
    template from one that does, and the two need different field tables. The
    signature is stored on the document so a run records which family each
    poster belongs to -- including the family that yields nothing, which is the
    one a human most needs to know about.
    """
    found: set[str] = set()
    for block in rows:
        for hit in scan_line(block.text, require_delimiter=False):
            if hit.start == 0 and hit.label not in ROW_MODE_EXCLUDED_LABELS:
                found.add(hit.label)
    return tuple(sorted(found)) or ("<no-leading-label>",)


def is_stop_line(text: str) -> bool:
    """True when a line ends the current multi-line field."""
    stripped = (text or "").strip()
    if not stripped:
        return True
    if _KNOWN_LABEL_RE.search(stripped):
        return True
    return bool(_SECTION_RE.match(stripped))


def group_rows(
    blocks: Iterable[TextBlock], vertical_tolerance_ratio: float = 0.6
) -> list[list[TextBlock]]:
    """Cluster text blocks into visual rows using bbox vertical overlap.

    Posters put a label in a left column and its value in a right column on the
    same visual row, so the two are separate OCR blocks. Row grouping is what
    turns them back into a readable ``开课日期 2027-01-08`` line.
    """
    items = [block for block in blocks if block.bbox and block.text.strip()]
    if not items:
        return []
    ordered = sorted(items, key=lambda block: (block.bbox[1], block.bbox[0]))  # type: ignore[index]
    rows: list[list[TextBlock]] = []
    for block in ordered:
        top, bottom = block.bbox[1], block.bbox[1] + block.bbox[3]  # type: ignore[index]
        placed = False
        for row in reversed(rows):
            row_top = min(item.bbox[1] for item in row)  # type: ignore[index]
            row_bottom = max(item.bbox[1] + item.bbox[3] for item in row)  # type: ignore[index]
            tolerance = max(1.0, (row_bottom - row_top) * vertical_tolerance_ratio)
            if abs(top - row_top) <= tolerance:
                row.append(block)
                placed = True
                break
        if not placed:
            rows.append([block])
    return [sorted(row, key=lambda block: (block.bbox[0], block.bbox[1])) for row in rows]  # type: ignore[index]


def row_to_text(row: Iterable[TextBlock]) -> str:
    return clean_text(" ".join(block.text for block in row if block.text.strip()))


def row_pointer(row: Iterable[TextBlock]) -> str:
    pointers = [block.pointer for block in row]
    return pointers[0] if len(pointers) == 1 else f"row[{pointers[0]}..{pointers[-1]}]"


def row_detail(row: Iterable[TextBlock]) -> str:
    first = next(iter(row), None)
    return first.detail if first else ""

