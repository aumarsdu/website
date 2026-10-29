"""CSV schedule tables as an independent source.

Some partners publish a topic list plus its start dates as a spreadsheet export
rather than in the page payload: HIREP ships ``开课时间（日期）`` with the
source field named in ``开课时间依据字段``; Zhongke ships ``开课日期`` with
``开课日期依据``. Both carry the 口径 -- which field the date was read from --
and that belongs in the evidence, not in a field value.

Why this is a separate source kind
----------------------------------
A date that lives in a spreadsheet is a *different statement* from a date on a
web page, even when they agree. Merging them silently would hide a disagreement
behind a last-write-wins rule. So a table row is loaded as its own document and
joins the ordinary conflict machinery: if the page and the table disagree, that
is reported as a conflict with both locators, and a human adjudicates it.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from ..config import Settings
from ..errors import InputError
from ..extract import make_claim
from ..schema import FieldClaim, Locator, RejectedCandidate
from ..utils import clean_text
from .base import AdapterOutput, make_document

# csv's default field limit is small; partner columns carry long URLs and notes.
csv.field_size_limit(10**9)


def _norm_column(name: Any) -> str:
    """Match columns forgivingly: BOM, spaces, underscores, case, full width."""
    text = str(name or "").replace("﻿", "").strip()
    return "".join(ch for ch in text if not ch.isspace() and ch != "_").casefold()


@dataclass(frozen=True)
class TableProfile:
    """How one schedule table maps onto the canonical fields."""

    name: str
    provider: str
    fields: dict[str, tuple[str, ...]]
    id_column: str | None = None
    # A schedule row is often one *offering*, not one topic. HIREP lists three
    # product packages per topic with three different start dates, so keying on
    # 课题ID alone invents hundreds of false conflicts. Listing both columns
    # makes the identity (课题ID, 产品包ID).
    id_columns: tuple[str, ...] = ()
    title_column: str | None = None
    # field -> columns naming where that field's value came from.
    basis_columns: dict[str, tuple[str, ...]] = None  # type: ignore[assignment]
    # field -> what that value means in the source's own words. A date read from
    # "首课时间" is not the same fact as one read from "开课日期", and the
    # difference is invisible in the value alone, so it is declared here.
    semantics: dict[str, str] = None  # type: ignore[assignment]
    source_authority: str = "supplier_official"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.basis_columns is None:
            object.__setattr__(self, "basis_columns", {})
        if self.semantics is None:
            object.__setattr__(self, "semantics", {})

    def consumed_columns(self) -> set[str]:
        """Every column this profile reads, ids and titles included."""
        columns = {_norm_column(item) for item in declared_columns(self) if item}
        return columns

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TableProfile":
        if not isinstance(payload, dict):
            raise InputError("profile file must be a JSON object")
        name = clean_text(str(payload.get("name", "")))
        if not name:
            raise InputError("profile needs a 'name'")
        raw_fields = payload.get("fields") or {}
        if not isinstance(raw_fields, dict):
            raise InputError("'fields' must be an object of field -> columns")
        fields = {
            str(field): tuple(str(item) for item in columns if str(item))
            for field, columns in raw_fields.items()
            if isinstance(columns, (list, tuple))
        }
        raw_ids = payload.get("id_columns") or ()
        id_columns = tuple(str(item) for item in raw_ids if str(item))
        raw_semantics = payload.get("semantics") or {}
        semantics = {
            str(field): clean_text(str(text))
            for field, text in raw_semantics.items()
            if clean_text(str(text))
        } if isinstance(raw_semantics, dict) else {}
        raw_basis = payload.get("basis_columns") or {}
        basis = {
            str(field): tuple(str(item) for item in columns if str(item))
            for field, columns in raw_basis.items()
            if isinstance(columns, (list, tuple))
        }
        return cls(
            name=name,
            provider=clean_text(str(payload.get("provider", ""))) or name,
            fields=fields,
            id_column=payload.get("id_column"),
            id_columns=id_columns,
            title_column=payload.get("title_column"),
            basis_columns=basis,
            semantics=semantics,
            source_authority=clean_text(str(payload.get("source_authority", "supplier_official"))),
            notes=clean_text(str(payload.get("notes", ""))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "source_authority": self.source_authority,
            "id_column": self.id_column,
            "id_columns": list(self.id_columns),
            "title_column": self.title_column,
            "fields": {field: list(columns) for field, columns in self.fields.items()},
            "basis_columns": {field: list(columns) for field, columns in self.basis_columns.items()},
            "semantics": dict(self.semantics),
            "notes": self.notes,
        }


class CsvTableAdapter:
    """One CSV row becomes one source document."""

    name = "table_csv"
    source_kind = "table_csv"
    accepts = ("*.csv",)

    def __init__(self, profile: TableProfile) -> None:
        self.profile = profile
        self.on_error: Any = None

    def load(self, path: Path, settings: Settings) -> list[AdapterOutput]:
        path = Path(path)
        if not path.exists():
            raise InputError(f"input file not found: {path}")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = reader.fieldnames or []

        index = {_norm_column(name): name for name in fieldnames}
        missing = [
            column
            for columns in self.profile.fields.values()
            for column in columns
            if _norm_column(column) not in index
        ]
        if missing and self.on_error is not None:
            self.on_error(0, InputError(f"{path}: 列不存在 {sorted(set(missing))}"))

        def cell(row: dict[str, Any], column: str | None) -> str:
            if not column:
                return ""
            actual = index.get(_norm_column(column))
            return clean_text(row.get(actual, "")) if actual else ""

        # Columns nobody reads are the field table's punch list. Without this a
        # fifteen-column sheet mapped on three columns reports "nothing missing".
        consumed = self.profile.consumed_columns()
        unmapped_all = [name for name in fieldnames if _norm_column(name) not in consumed]

        outputs: list[AdapterOutput] = []
        for line_number, row in enumerate(rows, start=2):
            id_parts = [
                cell(row, column)
                for column in (*((self.profile.id_column,) if self.profile.id_column else ()),
                               *self.profile.id_columns)
            ]
            title = cell(row, self.profile.title_column)
            # A composite key keeps one row = one offering. Joining with "#"
            # matches the record_key shape used elsewhere.
            external_id = "#".join(part for part in id_parts if part)
            if not external_id and not title:
                continue
            document_id = f"{self.profile.provider}#csv-{external_id or title}"[:120]
            claims: list[FieldClaim] = []
            rejected: list[RejectedCandidate] = []

            for field, columns in self.profile.fields.items():
                value = ""
                used_column = None
                for column in columns:
                    value = cell(row, column)
                    if value:
                        used_column = column
                        break
                if not value:
                    continue
                basis = ""
                for column in self.profile.basis_columns.get(field, ()):  # type: ignore[arg-type]
                    basis = cell(row, column)
                    if basis:
                        break
                detail = f"table={self.profile.name} column={used_column}"
                if basis:
                    detail += f" basis={basis}"
                semantics = self.profile.semantics.get(field)
                if semantics:
                    detail += f" semantics={semantics}"
                claim = make_claim(
                    field=field,
                    raw_text=value,
                    locator=Locator(
                        kind="csv_cell",
                        document_id=document_id,
                        pointer=f"row{line_number}.{used_column}",
                        detail=detail,
                        excerpt=value[:160],
                    ),
                    extractor=f"csv_column:{used_column}",
                    method="csv_column",
                    base_confidence="high",
                    rejected=rejected,
                )
                if claim is not None:
                    claims.append(claim)

            document = make_document(
                document_id=document_id,
                source_kind=self.source_kind,
                provider=self.profile.provider,
                origin=str(path),
                external_id=external_id or None,
                title_hint=title or None,
                source_authority=self.profile.source_authority,
                meta={
                    "profile": self.profile.name,
                    "csv_line": line_number,
                    "profile_notes": self.profile.notes,
                },
            )
            outputs.append(
                AdapterOutput(
                    document=document,
                    claims=claims,
                    rejected=rejected,
                    unmapped_source_keys=unmapped_all,
                    stats={"profile": self.profile.name, "columns": len(fieldnames)},
                )
            )

        if settings.max_records is not None:
            outputs = outputs[: settings.max_records]
        return outputs


# Column names that look like a canonical field. This only *asks* whether the
# exclusion was deliberate -- a hint, never a mapping.
FIELD_HINTS: dict[str, tuple[str, ...]] = {
    "start_date": ("时间", "日期", "date", "time"),
    "instructor": ("教授", "老师", "导师", "teacher", "professor"),
    "duration": ("周期", "时长", "课时", "周", "学期"),
    "suitable_audience": ("适合", "面向", "对象", "专业", "年级", "audience"),
    "output_description": ("成果", "产出", "交付", "报告", "证书", "deliverable"),
    "project_title": ("名称", "标题", "title", "name"),
}


def looks_like_fields(column: str) -> list[str]:
    """Which canonical fields a column name resembles. Advisory only."""
    lowered = str(column or "").casefold()
    if not lowered:
        return []
    return [
        field
        for field, needles in FIELD_HINTS.items()
        if any(needle.casefold() in lowered for needle in needles)
    ]


def declared_columns(profile: TableProfile) -> list[str]:
    """Every column this profile claims to read, ids and titles included."""
    columns: list[str] = []
    for extra in (profile.id_column, *profile.id_columns, profile.title_column):
        if extra:
            columns.append(extra)
    for group in (profile.fields, profile.basis_columns):
        for items in group.values():
            columns.extend(items)
    return [item for item in columns if item]


def score_profile(path: Path, profile: TableProfile) -> int:
    """How many of a profile's declared columns exist in this CSV header."""
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle), [])
    except OSError:
        return -1
    present = {_norm_column(name) for name in header}
    return sum(1 for column in declared_columns(profile) if _norm_column(column) in present)


def detect_profile(path: Path, candidates: dict[str, TableProfile]) -> TableProfile | None:
    """Pick the profile that best fits the file, mirroring web profile probes.

    ``--profile`` stays available and always wins; this only removes the need to
    name it when a single table profile is registered, which is the common case.
    """
    best: tuple[int, TableProfile] | None = None
    for profile in sorted(candidates.values(), key=lambda item: item.name):
        score = score_profile(path, profile)
        if score > 0 and (best is None or score > best[0]):
            best = (score, profile)
    return best[1] if best else None



def table_profiles_from_file(path: str | Path) -> list[TableProfile]:
    """Load every ``kind: csv`` profile in a profile file."""
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items: Sequence[Any]
    if isinstance(payload, dict):
        items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        raise InputError(f"{path}: profile file must be an object or a list")
    return [
        TableProfile.from_dict(item)
        for item in items
        if isinstance(item, dict) and clean_text(str(item.get("kind", ""))).casefold() == "csv"
    ]
