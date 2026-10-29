"""Marketing-claim detection.

Supplier material is written to sell. This module decides whether a sentence
states something plain or promises something, using explicit phrase tables
rather than sentiment scoring, so a reviewer can audit every decision.

The classification is one line per statement and maps onto the design doc's
``project_deliverable_claims.claim_type``:

``prohibited_claim``
    Guarantees. Never usable in sales or public copy.
``conditional_claim``
    Needs stated conditions and a disclaimer (recommendation letters, indexed
    publication, "有机会").
``factual``
    Plain statements: dates, durations, contact hours, certificates.

Nothing here changes a claim's truth value. Every claim stays
``verification_status = "unverified"``; this module only decides what may be
repeated as a stated fact and what must be filtered out of public copy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Any

EVIDENCE_KINDS: tuple[str, ...] = ("factual", "conditional_claim", "prohibited_claim")

_SEGMENT_SPLIT_RE = re.compile(r"[；;\n]+|(?<=[。！？])")

# Guarantees. These are the phrases design doc section 14.4 marks "prohibited".
PROHIBITED_PATTERNS: tuple[tuple[str, str], ...] = (
    ("guaranteed_admission", r"保录|保送|保进|保过|包过|包录|包录取|保offer|保\s*offer"),
    ("guaranteed_publication", r"必发|包发|保证(?:发表|录用|刊登|见刊|接收)|保(?:证)?(?:发表|录用)"),
    ("guaranteed_result", r"稳进|稳录|稳拿|稳过|必录|必中|必过|包(?:你|你)?(?:上|进|过|拿|中)"),
    ("absolute_100", r"100\s*%|百分百|百分之百|全包(?:发|录|过)?|零风险|无风险(?:发表|录取)"),
    ("unconditional", r"无条件(?:录取|录用|发表|通过)|一定能|绝对(?:可以|能|保证)"),
)

# Claims that need conditions and a disclaimer.
#
# These patterns were tightened against a 255-record real partner export. Three
# first-draft entries turned out to be ordinary academic vocabulary and had to
# go: "检索" (retrieval, as in 检索增强生成 / RAG), "福利" (social welfare), and
# "冲击" (shock, as a research subject). "爆款" is a legitimate media-research
# topic too. A marketing table that flags research vocabulary is worse than no
# table at all: it drowns real promises in noise.
#
# When adding a pattern, re-run the partner export and read
# promotional_claims_report.json before trusting it.
CONDITIONAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("recommendation_letter", r"推荐信|强荐|一封推荐|导师推荐信|教授推荐信|内部推荐|名额推荐"),
    ("personal_attention", r"1\s*[vV对]\s*1|一对一|小班|全程一对一|导师亲自"),
    ("group_meeting", r"大组会|小组会|组会|直接汇报|当面指导"),
    (
        "indexed_publication",
        r"\bEI\b|\bCPCI\b|Scopus|Web\s*of\s*Science|SSCI|CSSCI|被检索|检索收录"
        r"|(?:EI|CPCI|Scopus|CNKI)\s*检索"
        r"|检索\s*(?:发表|国际会议|英文普刊|论文|大会)",
    ),
    ("publication", r"发表|投稿|投前辅导|发论文|论文发表|论文产出|产出论文"),
    ("top_venue", r"顶刊|顶会|一区|CCF\s*[A-D]|新刊|高水平期刊|影响因子"),
    (
        "elite_brand",
        r"QS\s*(?:前|Top)|世界前\d+|全球前\d+|世界百强|藤校|名校冲刺"
        r"|(?:冲刺|冲击)\s*(?:顶刊|顶会|名校|藤校|QS|前\d+)",
    ),
    ("scarcity", r"名额(?:有限|仅限|只剩|告急)|招满即止|先到先得"),
    ("guarantee_adjacent", r"有机会|争取|有望|极大(?:提高|提升)"),
    (
        "no_experience",
        r"(?:零|0)\s*基础(?:也)?(?:能|可以|可)|没有基础也|无需基础|无门槛(?:报名|参与)",
    ),
    ("marketing_tone", r"火爆招生|不容错过|强烈推荐|赶紧|抓紧|名额告急|最后[几]天"),
)

# "100% 提升" style numbers attached to a result claim.
_PERCENT_RESULT_RE = re.compile(r"\d{2,3}\s*%\s*[^。；;\n]{0,12}?(?:提升|录取|发表|拿到|进名校)")

_PROHIBITED_COMPILED = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in PROHIBITED_PATTERNS)
_CONDITIONAL_COMPILED = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in CONDITIONAL_PATTERNS)

DISCLAIMERS: dict[str, str] = {
    "prohibited_claim": "该表述为绝对化承诺，不得用于销售话术与对外展示。",
    "conditional_claim": "该表述取决于学生自身条件与导师判断，必须附条件与免责声明，不得承诺结果。",
}

# Evidence kind -> design doc section 14.4 claim_type vocabulary.
DELIVERABLE_CLAIM_TYPE: dict[str, str] = {
    "conditional_claim": "conditional",
    "prohibited_claim": "prohibited",
}


def deliverable_claim_type(kind: str) -> str | None:
    return DELIVERABLE_CLAIM_TYPE.get(kind)


@dataclass
class ClaimVerdict:
    """Classification of one piece of text."""

    kind: str = "factual"
    phrases: list[str] = dc_field(default_factory=list)
    has_factual_content: bool = True

    @property
    def is_promotional(self) -> bool:
        return self.kind != "factual"

    @property
    def claim_type(self) -> str | None:
        """Design doc section 14.4 claim_type, or ``None`` for plain statements."""
        return deliverable_claim_type(self.kind)

    @property
    def required_disclaimer(self) -> str | None:
        return DISCLAIMERS.get(self.kind)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind, "has_factual_content": self.has_factual_content}
        if self.phrases:
            payload["matched_phrases"] = sorted(set(self.phrases))
        if self.required_disclaimer:
            payload["required_disclaimer"] = self.required_disclaimer
        return payload


def _marker_scan(text: str) -> tuple[list[str], list[str]]:
    """Return the (prohibited, conditional) marker names present in text."""
    prohibited = [name for name, pattern in _PROHIBITED_COMPILED if pattern.search(text)]
    if _PERCENT_RESULT_RE.search(text):
        prohibited.append("percent_result_promise")
    conditional = [name for name, pattern in _CONDITIONAL_COMPILED if pattern.search(text)]
    return prohibited, conditional


def _kind_of(segment: str) -> str:
    prohibited, conditional = _marker_scan(segment)
    if prohibited:
        return "prohibited_claim"
    if conditional:
        return "conditional_claim"
    return "factual"


def classify_text(text: str) -> ClaimVerdict:
    """Classify one statement. Worst marker present wins.

    ``has_factual_content`` answers a different question: does the statement
    *also* contain plain sentences? A deliverable list that ends with a
    guaranteed publication is mostly factual with a marketing tail, while a
    field whose every line promises an outcome has no factual content at all
    and must not be used as a fact.
    """
    if not text or not text.strip():
        return ClaimVerdict(kind="factual", has_factual_content=False)

    prohibited, conditional = _marker_scan(text)
    segments = split_segments(text)
    has_factual = any(_kind_of(segment) == "factual" for segment in segments)

    if prohibited:
        return ClaimVerdict(
            kind="prohibited_claim", phrases=prohibited, has_factual_content=has_factual
        )
    if conditional:
        return ClaimVerdict(
            kind="conditional_claim", phrases=conditional, has_factual_content=has_factual
        )
    return ClaimVerdict(kind="factual", phrases=[], has_factual_content=has_factual)


def split_segments(text: str, max_length: int = 220) -> list[str]:
    """Split a statement into the smallest units worth classifying separately.

    Bullet-style outputs are newline separated; a prose sentence is split on
    sentence punctuation so a promotional clause does not taint a factual one.
    """
    if not text:
        return []
    segments: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in _SEGMENT_SPLIT_RE.split(line) if part and part.strip()]
        for part in parts or [line]:
            if len(part) <= max_length:
                segments.append(part)
                continue
            for chunk in re.split(r"(?<=[，,、])", part):
                cleaned = chunk.strip()
                if cleaned:
                    segments.append(cleaned)
    return segments


def classify_segments(text: str) -> list[dict[str, Any]]:
    """Per-segment classification, used by the public-copy filter."""
    result: list[dict[str, Any]] = []
    for segment in split_segments(text):
        verdict = classify_text(segment)
        result.append(
            {
                "text": segment,
                "kind": verdict.kind,
                "phrases": sorted(set(verdict.phrases)),
            }
        )
    return result


def keep_factual_only(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Return the factual part of a statement plus everything that was withheld.

    Used when building customer-facing copy: a bullet promising an indexed
    publication is dropped instead of being repeated as a deliverable.
    """
    kept: list[str] = []
    withheld: list[dict[str, Any]] = []
    for item in classify_segments(text):
        if item["kind"] == "factual":
            kept.append(item["text"])
        else:
            withheld.append(item)
    return ("；".join(kept), withheld)


def is_promotional(text: str) -> bool:
    return classify_text(text).is_promotional
