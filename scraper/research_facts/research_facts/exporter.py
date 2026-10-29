"""Render fact records into something a person can actually use.

The JSON is built for machines: every claim, every locator, every status. That
is the right shape for a pipeline and the wrong shape for someone drafting a
paragraph or checking a poster caption.

Two renderings are offered:

``markdown`` (default)
    A 事实卡 per project: field, value, status, verbatim text, source, and a
    numbered evidence list. Anything unusable is printed as a named gap instead
    of being quietly dropped, so a writer sees "周期：来源不一致" rather than
    inventing one.

``json``
    The same content, structured, for downstream tools.

``--public`` switches to the customer-facing projection: high-risk fields only
after review, marketing sentences removed, whole promotional fields omitted.
"""

from __future__ import annotations

from typing import Any, Sequence

from .config import FIELD_NAMES, field_label
from .projections import build_public_rows
from .review import ReviewRegistry, evidence_fingerprint
from .schema import ProjectFactRecord

# What a reader must not miss about a field's state.
_STATUS_NOTE: dict[str, str] = {
    "missing": "来源未给出",
    "conflict": "来源之间不一致",
    "promotional_only": "仅供应商宣传表述",
    "resolved_with_promotional": "一致但含宣传表述",
}

_REVIEW_LABEL = {
    "approved": "已过审",
    "rejected": "已否决",
    "stale": "审核已过期（证据已变）",
    "pending": "待审核",
}

# Title first, then the five business fields, in the order a writer needs them.
CARD_FIELDS: tuple[str, ...] = (
    "project_title",
    "instructor",
    "start_date",
    "duration",
    "suitable_audience",
    "output_description",
)


def _source_label(document_id: str) -> str:
    for needle, label in (("poster", "海报"), ("handbook", "手册"), ("#", "网页")):
        if needle in document_id:
            return label
    return "来源"


def _one_line(text: str) -> str:
    return str(text or "").replace("\n", " / ")


def _render_value(state: Any) -> str:
    """The value a reader should quote, plus any caveat attached to it."""
    if state is None or state.status == "missing":
        return "（来源未给出）"
    if state.selected_normalized_value:
        return str(state.selected_normalized_value)
    if state.selected_raw_text:
        return _one_line(state.selected_raw_text)
    return f"（{_STATUS_NOTE.get(state.status, state.status)}）"


def _field_block(
    record: ProjectFactRecord, name: str, reviews: ReviewRegistry
) -> tuple[list[str], list[dict[str, Any]]]:
    """Markdown lines for one field, plus the evidence rows it produced."""
    state = record.fields.get(name)
    lines = [f"### {field_label(name)} `{name}`", ""]
    evidence: list[dict[str, Any]] = []

    if state is None or state.status == "missing":
        lines.append("- 取值：**来源未给出**（未做任何推断补写）")
        lines.append("")
        return lines, evidence

    lines.append(f"- 状态：`{state.status}` · 风险 `{state.risk_level}`")
    lines.append(f"- 取值：**{_render_value(state)}**")
    if state.note:
        lines.append(f"- 说明：{state.note}")

    if state.status == "conflict":
        lines.append("- 各方说法（均未采用）：")
        for key in sorted({claim.compare_value for claim in state.claims}):
            for claim in state.claims:
                if claim.compare_value != key:
                    continue
                lines.append(
                    f"    - {_source_label(claim.locator.document_id)}"
                    f"（{claim.locator.pointer}）：{_one_line(claim.raw_text)}"
                )
        lines.append("")
        lines.append("> **该字段未采用任何一方**，写稿前需人工确认。")
        lines.append("")

    if state.status == "promotional_only":
        lines.append("> **该字段只有宣传表述**，已拒绝作为事实使用。")
        lines.append("")

    lines.append("- 证据：")
    for index, claim in enumerate(state.claims, start=1):
        marker = "" if claim.evidence_kind == "factual" else f" ⚠️ {claim.evidence_kind}"
        lines.append(
            f"    {index}. {_source_label(claim.locator.document_id)}"
            f" `{claim.locator.pointer}` · 可信度 `{claim.extraction_confidence}`{marker}"
        )
        lines.append(f"        原文：{_one_line(claim.raw_text)}")
        evidence.append(
            {
                "field": name,
                "document_id": claim.locator.document_id,
                "pointer": claim.locator.pointer,
                "detail": claim.locator.detail,
                "raw_text": claim.raw_text,
                "extraction_confidence": claim.extraction_confidence,
                "evidence_kind": claim.evidence_kind,
            }
        )
    lines.append("")

    if name in ("instructor", "output_description"):
        fingerprint = evidence_fingerprint(state)
        status = reviews.status_for(record.record_key, name, fingerprint)
        lines.append(f"- 人工审核：**{_REVIEW_LABEL[status]}**（证据指纹 `{fingerprint[:12]}`）")
        lines.append("")
    return lines, evidence


def render_markdown(
    record: ProjectFactRecord,
    reviews: ReviewRegistry | None = None,
    cohort: dict[str, Any] | None = None,
) -> str:
    """Render one project as a 事实卡 with its full evidence list."""
    registry = reviews or ReviewRegistry()
    title_state = record.fields.get("project_title")
    title = _render_value(title_state) if title_state else "（未命名）"

    out: list[str] = [f"# {title}", ""]
    out.append(f"- 记录键：`{record.record_key}`")
    out.append(
        f"- 供应商：{record.identity.provider} · 外部编号：{record.identity.external_id or '无'}"
    )
    out.append(
        f"- 身份依据：`{record.identity.basis}`"
        + ("（归组含猜测，需人工确认）" if record.identity.review_required else "")
    )
    out.append(f"- 来源文档：{len(record.document_ids)} 份")
    for document_id in record.document_ids:
        out.append(f"    - `{document_id}`")
    if cohort and cohort.get("size", 0) > 1:
        # "5 期" and "2 个不同开课日" are both true and mean different things;
        # saying "5 batches: two dates" reads like a contradiction.
        dates = "、".join(cohort.get("dates") or [])
        out.append(
            f"- ⚠ 同一课题共 **{cohort['size']} 期**，开课日期：{dates or '未知'}"
            "　写稿时务必指明期次，否则容易描述错。"
        )
    if record.issues:
        out.append(f"> 数据问题：{'、'.join(issue['type'] for issue in record.issues)}")
    out.append("")

    collected: list[dict[str, Any]] = []
    for name in CARD_FIELDS:
        lines, evidence = _field_block(record, name, registry)
        out.extend(lines)
        collected.extend(evidence)

    out.append("---")
    out.append("")
    out.append("## 证据来源")
    out.append("")
    for index, item in enumerate(collected, start=1):
        out.append(
            f"{index}. `{item['document_id']}` · `{item['pointer']}`"
            f" · 可信度 `{item['extraction_confidence']}` · {item['evidence_kind']}"
        )
        out.append(f"    - 原文：{_one_line(item['raw_text'])}")
        if item["detail"]:
            out.append(f"    - 位置：{item['detail']}")
    out.append("")
    out.append("> 所有取值均为供应商陈述。标注 ⚠️ 的为宣传表述，不可作为已证实事实转述。")
    out.append("")
    return "\n".join(out)


def render_public_markdown(row: dict[str, Any]) -> str:
    """Render the customer-facing projection for one record."""
    title = row["display"].get("project_title", {}).get("text") or "（未命名）"
    out: list[str] = [f"# {title}", ""]
    out.append(f"- 记录键：`{row['record_key']}`")
    out.append(f"- 可对外：{'是' if row['publishable'] else '否（门禁未过，见下）'}")
    cohort = row.get("cohort") or {}
    if cohort.get("size", 0) > 1:
        # Public copy names the count and the current run, not the whole history:
        # a customer-facing page should not imply a single date is the only one.
        out.append(
            f"- 期次：共 {cohort['size']} 期，最近一期 {cohort.get('latest') or '未知'}"
        )
    out.append("")

    out.append("## 对外字段")
    out.append("")
    if row["display"]:
        for name in FIELD_NAMES:
            entry = row["display"].get(name)
            if not entry:
                continue
            out.append(
                f"- **{field_label(name)}**：{entry['text']}　"
                f"`{entry['verification_status']}` · 来源 {'、'.join(entry['evidence_documents'])}"
            )
    else:
        out.append("- （暂无可对外字段）")
    out.append("")

    if row["dropped_purely_promotional_fields"]:
        names = "、".join(field_label(name) for name in row["dropped_purely_promotional_fields"])
        out.append(f"> 整体为宣传表述、已整字段移除：{names}")
        out.append("")
    if row["review_queue"]:
        out.append("## 待人工审核")
        out.append("")
        for item in row["review_queue"]:
            out.append(
                f"- **{item['field_label']}**：{item['draft_text']}"
                f"（`{item['review_status']}` · {item['reason']}）"
            )
        out.append("")
    failed = [gate for gate in row["gates"] if gate["evaluated"] and not gate["passed"]]
    if failed:
        out.append("## 未通过的门禁")
        out.append("")
        for gate in failed:
            out.append(f"- `{gate['gate']}`：{gate['detail']}")
        out.append("")
    out.append(row["notice"])
    out.append("")
    return "\n".join(out)


def build_export(
    records: Sequence[ProjectFactRecord],
    reviews: ReviewRegistry | None = None,
    *,
    public: bool = False,
    cohorts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the export payload for a set of records."""
    registry = reviews or ReviewRegistry()
    cohort_map = cohorts or {}
    if public:
        rows, summary = build_public_rows(records, registry, cohort_map)
        return {
            "mode": "public",
            "summary": summary,
            "records": [
                {
                    "record_key": row["record_key"],
                    "publishable": row["publishable"],
                    "markdown": render_public_markdown(row),
                    "json": row,
                }
                for row in rows
            ],
        }
    return {
        "mode": "internal",
        "summary": {
            "records": len(records),
            "review_decisions": len(registry.decisions),
            "rule": "内部事实卡：含全部证据、冲突双方与宣传标记，供写稿与答疑时核对。",
        },
        "records": [
            {
                "record_key": record.record_key,
                "markdown": render_markdown(record, registry, cohort_map.get(record.record_key)),
                "json": record.to_dict(),
            }
            for record in records
        ],
    }


def export_summary(payload: dict[str, Any]) -> str:
    if payload["mode"] == "public":
        summary = payload["summary"]
        return (
            f"对外导出：{summary['records']} 条，可对外 {summary['publishable']} 条，"
            f"待审 {summary['review_queue_items']} 项，已过审 {summary['approved_fields']} 项，"
            f"已过滤宣传表述 {summary['marketing_segments_filtered']} 处"
        )
    summary = payload["summary"]
    return f"内部导出：{summary['records']} 条事实卡，已含全部证据与冲突说明"


__all__ = [
    "CARD_FIELDS",
    "build_export",
    "export_summary",
    "render_markdown",
    "render_public_markdown",
]
