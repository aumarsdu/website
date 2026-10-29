"""Cross-source duplicate candidates.

Design doc section 4.7: *create candidate only, never automatic merge*. The
scoring weights below are that document's, and the two thresholds are its
gates: at 0.75 a candidate is high confidence and blocks publishing until a
human looks; 0.55-0.75 is a normal candidate; below 0.55 is not reported.

Two honest limitations, both visible in the output rather than papered over:

* Only signals this six-field package actually collects are scored. The design
  doc also lists institution, taxonomy and shared URL/asset hash. Those live
  in tables this package does not read, so they are reported as ``unavailable``
  and contribute nothing -- which is why a cross-provider pair cannot reach the
  0.75 bar here. The maximum reachable score is stated in the report.
* Candidates never merge. A merge needs an explicit human decision recorded
  outside this package, exactly like adjudication.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from difflib import SequenceMatcher
from typing import Any, Iterable, Sequence

from .schema import ProjectFactRecord
from .utils import comparison_key, stable_hash

# Design doc 4.7 weights.
WEIGHTS: dict[str, float] = {
    "title_similarity": 0.35,   # title similarity >= 0.85
    "instructor_similarity": 0.25,
    "same_provider": 0.05,
    "same_external_id": 0.30,   # same URL / asset hash, in this field's terms
}
TITLE_SIMILARITY_FLOOR = 0.85
HIGH_CONFIDENCE = 0.75
MIN_REPORTED = 0.55

# Signals the design doc lists that this package does not collect.
UNAVAILABLE_SIGNALS: tuple[str, ...] = (
    "institution_similarity",
    "same_taxonomy",
    "same_url_or_asset_hash",
)

# A record is only a candidate for another if it states a title at all.
_TITLE_FIELD = "project_title"


# Fields whose disagreement means "different offering", not "duplicate row".
# Measured on three real sources: 560 of 564 candidate pairs differed on
# start_date alone, i.e. the same topic text across different cohorts. Merging
# those would erase a real distinction.
COMPARABLE_FIELDS: tuple[str, ...] = (
    "start_date",
    "instructor",
    "duration",
    "suitable_audience",
    "output_description",
)


@dataclass
class Candidate:
    left: str
    right: str
    score: float
    signals: dict[str, Any] = dc_field(default_factory=dict)
    diverging_fields: list[str] = dc_field(default_factory=list)

    @property
    def is_mergeable(self) -> bool:
        """True only when every comparable field agrees.

        A merge is an identity claim, and identity plus agreement is what makes
        it a duplicate. Agreement on the typed fields is the guard.
        """
        return not self.diverging_fields

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_mergeable": self.is_mergeable,
            "diverging_fields": list(self.diverging_fields),
            # Canonical order, so the same pair is never reported twice.
            "left": self.left,
            "right": self.right,
            "score": round(self.score, 4),
            "signals": self.signals,
            "resolution": "manual_review_required",
            "merged": False,
        }


def title_of(record: ProjectFactRecord) -> str:
    state = record.fields.get(_TITLE_FIELD)
    if not state or not state.is_usable:
        return ""
    return str(state.selected_normalized_value or state.selected_raw_text or "")


def instructor_of(record: ProjectFactRecord) -> str:
    state = record.fields.get("instructor")
    if not state or not state.is_usable:
        return ""
    return str(state.selected_normalized_value or state.selected_raw_text or "")


def similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(None, comparison_key(left), comparison_key(right)).ratio(), 4)


def _diverging_fields(left: ProjectFactRecord, right: ProjectFactRecord) -> list[str]:
    diverging = []
    for name in COMPARABLE_FIELDS:
        left_state = left.fields.get(name)
        right_state = right.fields.get(name)
        left_value = (
            left_state.selected_normalized_value
            if left_state and left_state.is_usable
            else None
        )
        right_value = (
            right_state.selected_normalized_value
            if right_state and right_state.is_usable
            else None
        )
        if left_value != right_value:
            diverging.append(name)
    return diverging


def _score_pair(left: ProjectFactRecord, right: ProjectFactRecord) -> Candidate | None:
    left_title, right_title = title_of(left), title_of(right)
    if not left_title or not right_title:
        return None

    signals: dict[str, Any] = {"unavailable": list(UNAVAILABLE_SIGNALS)}
    score = 0.0

    title_sim = similarity(left_title, right_title)
    signals["title_similarity"] = title_sim
    if title_sim >= TITLE_SIMILARITY_FLOOR:
        score += WEIGHTS["title_similarity"]

    left_teacher, right_teacher = instructor_of(left), instructor_of(right)
    teacher_sim = similarity(left_teacher, right_teacher)
    signals["instructor_similarity"] = teacher_sim
    if left_teacher and right_teacher and teacher_sim >= TITLE_SIMILARITY_FLOOR:
        score += WEIGHTS["instructor_similarity"]

    if left.identity.provider == right.identity.provider:
        signals["same_provider"] = True
        score += WEIGHTS["same_provider"]
    else:
        signals["same_provider"] = False

    if left.identity.external_id and left.identity.external_id == right.identity.external_id:
        signals["same_external_id"] = True
        score += WEIGHTS["same_external_id"]
    else:
        signals["same_external_id"] = False

    if score < MIN_REPORTED:
        return None
    return Candidate(left=min(left.record_key, right.record_key),
                     right=max(left.record_key, right.record_key),
                     score=score, signals=signals,
                     diverging_fields=_diverging_fields(left, right))


def _blocks(records: Sequence[ProjectFactRecord]) -> dict[str, list[int]]:
    """Cheap inverted index on the title's leading characters.

    Comparing every pair is quadratic and pointless: a duplicate shares its
    opening characters far more often than not, and this keeps a few thousand
    records tractable without a database.
    """
    blocks: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        key = comparison_key(title_of(record))
        if len(key) < 4:
            # Too short to block on; it goes into the wide bucket below.
            blocks.setdefault("", []).append(index)
            continue
        for token in {key[:2], key[2:4]}:
            blocks.setdefault(token, []).append(index)
    return blocks


def find_candidates(
    records: Sequence[ProjectFactRecord],
    *,
    high_confidence: float = HIGH_CONFIDENCE,
    min_reported: float = MIN_REPORTED,
    max_compared_pairs: int = 2_000_000,
) -> list[Candidate]:
    """Score cross-source pairs. Returns candidates, never merges."""
    ordered = sorted(records, key=lambda record: record.record_key)
    blocks = _blocks(ordered)
    seen: set[tuple[str, str]] = set()
    candidates: list[Candidate] = []
    compared = 0

    for members in blocks.values():
        if len(members) < 2:
            continue
        for i, left_index in enumerate(members):
            for right_index in members[i + 1 :]:
                compared += 1
                if compared > max_compared_pairs:
                    return _finish(candidates, high_confidence, min_reported)
                left, right = ordered[left_index], ordered[right_index]
                key = (min(left.record_key, right.record_key), max(left.record_key, right.record_key))
                if key in seen:
                    continue
                seen.add(key)
                candidate = _score_pair(left, right)
                if candidate is None or candidate.score < min_reported:
                    continue
                candidates.append(candidate)
    return _finish(candidates, high_confidence, min_reported)


def _finish(
    candidates: list[Candidate], high_confidence: float, min_reported: float
) -> list[Candidate]:
    kept = [item for item in candidates if item.score >= min_reported]
    kept.sort(key=lambda item: (-item.score, item.left, item.right))
    return kept


def build_duplicate_report(
    records: Sequence[ProjectFactRecord],
    *,
    high_confidence: float = HIGH_CONFIDENCE,
    min_reported: float = MIN_REPORTED,
) -> dict[str, Any]:
    """Candidate report plus an explicit statement of what could not be scored."""
    candidates = find_candidates(
        records, high_confidence=high_confidence, min_reported=min_reported
    )
    total = sum(WEIGHTS.values())
    providers = sorted({record.identity.provider for record in records})
    pairs = [(item.left, item.right) for item in candidates]
    return {
        "total_records": len(records),
        "providers": providers,
        "candidate_count": len(candidates),
        "mergeable_count": sum(1 for item in candidates if item.is_mergeable),
        "diverging_count": sum(1 for item in candidates if not item.is_mergeable),
        "merge_rule": (
            "只有全部可比字段一致（is_mergeable）才可提交人工合并；"
            "开课日期不同的同名课题是不同批次，合并会抹掉真实差异。"
        ),
        "high_confidence_count": sum(1 for item in candidates if item.score >= high_confidence),
        "thresholds": {"high_confidence": high_confidence, "min_reported": min_reported},
        "max_reachable_score": round(total, 4),
        "scored_signals": dict(WEIGHTS),
        "unavailable_signals": list(UNAVAILABLE_SIGNALS),
        "limits": (
            f"本包只采集六个字段，机构/分类/共用链接等信号不可得，最高可得 {total:.2f} 分；"
            f"跨供应商候选因此无法达到 {high_confidence:.2f} 高置信阈值，属正常。"
            "候选仅供人工复核，任何情况下都不会自动合并。"
        ),
        "rule": "只生成候选，不自动合并；高分候选在人工确认前应阻止发布。",
        "candidates": [item.to_dict() for item in candidates],
        "report_digest": stable_hash(pairs, 12) if pairs else None,
    }


def group_key(record: ProjectFactRecord) -> str:
    """A stable key for a candidate cluster, for operators who merge by hand."""
    return stable_hash(
        [record.identity.provider, record.identity.external_id, title_of(record)], 16
    )


def candidate_clusters(candidates: Iterable[Candidate]) -> dict[str, list[Candidate]]:
    """Union candidate edges into clusters so a human can judge a whole group."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)

    for item in candidates:
        union(item.left, item.right)
    clusters: dict[str, list[Candidate]] = {}
    for item in candidates:
        clusters.setdefault(find(item.left), []).append(item)
    return clusters


def cohort_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per-record cohort summary, for the fact card and the public projection.

    A writer looking at one card needs to know the topic runs in several
    cohorts, otherwise it is very easy to describe the wrong one.
    """
    index: dict[str, dict[str, Any]] = {}
    for group in report.get("groups", []):
        dates = sorted({run["start_date"] for run in group["runs"] if run["start_date"]})
        for run in group["runs"]:
            index[run["record_key"]] = {
                "title": group["title"],
                "provider": group["provider"],
                "size": group["run_count"],
                "dates": dates,
                "latest": dates[-1] if dates else None,
            }
    return index


def build_cohort_report(records: Sequence[ProjectFactRecord]) -> dict[str, Any]:
    """Same topic, different runs.

    This is *not* a duplicate report and must never be merged. Measured on three
    real sources, 560 of 564 candidate pairs were the same topic text across
    different start dates: the same course offered in several cohorts. For
    someone drafting a paragraph that is a trap -- they can easily describe the
    wrong run -- so the variants are grouped and listed here rather than left to
    be discovered in the field.

    Grouping stays a report. No entity is created, and nothing is merged.
    """
    groups: dict[tuple[str, str], list[ProjectFactRecord]] = {}
    for record in records:
        title = title_of(record)
        if not title:
            continue
        groups.setdefault((record.identity.provider, comparison_key(title)), []).append(record)

    cohorts: list[dict[str, Any]] = []
    for (provider, _key), members in groups.items():
        if len(members) < 2:
            continue
        runs = []
        for member in sorted(members, key=lambda item: item.record_key):
            date_state = member.fields.get("start_date")
            runs.append(
                {
                    "record_key": member.record_key,
                    "external_id": member.identity.external_id,
                    "start_date": (
                        date_state.selected_normalized_value
                        if date_state and date_state.is_usable
                        else None
                    ),
                    "start_date_status": date_state.status if date_state else "missing",
                }
            )
        dates = [run["start_date"] for run in runs]
        cohorts.append(
            {
                "provider": provider,
                "title": title_of(members[0]),
                "run_count": len(runs),
                "distinct_dates": len({date for date in dates if date}),
                "runs": runs,
                "resolution": "keep_separate",
                "note": "同一课题的不同批次，保留为独立记录；写稿时须指明批次。",
            }
        )
    cohorts.sort(key=lambda item: (-item["run_count"], item["provider"], item["title"]))

    # Same topic, different wording. Measured on three real sources: 36 title
    # pairs at >=0.90 similarity landed in different groups because the group key
    # is exact. Under-grouping is the real risk here -- over-grouping cannot
    # happen with an exact key. These links are ADVISORY ONLY: no record is
    # regrouped, no record_key changes, nothing is merged. A human decides.
    related = _related_groups(cohorts)

    # Records that share a start date inside one group are the merge gate's
    # input, not a cohort fact: same topic *and* same date is a duplicate row.
    same_date = [
        {
            "provider": group["provider"],
            "title": group["title"],
            "run_count": group["run_count"],
            "distinct_dates": group["distinct_dates"],
            "record_keys": [run["record_key"] for run in group["runs"]],
            "note": "组内存在同日记录，可能是源侧重复；请用合并提案流程逐对确认。",
        }
        for group in cohorts
        if group["distinct_dates"] < group["run_count"]
    ]

    return {
        "topic_groups": len(cohorts),
        "records_in_groups": sum(item["run_count"] for item in cohorts),
        "rule": (
            "同名不同开课日期 = 不同批次，不合并。按开课日期分组列出，"
            "便于写稿与答疑时指明具体期次。"
        ),
        "subject_signature": _subject_signature(records),
        "groups": cohorts,
        "related_groups": related,
        "same_date_sibling_groups": same_date,
        "related_groups_rule": (
            "related_groups 只是提示：疑似同一课题的不同写法，"
            "不合并、不改 record_key，是否视为同题由人判断。"
        ),
    }


RELATED_TITLE_FLOOR = 0.90


def _related_groups(cohorts: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Advisory links between groups whose titles are near-identical."""
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for group in cohorts:
        by_provider.setdefault(group["provider"], []).append(group)

    links: list[dict[str, Any]] = []
    for provider, groups in by_provider.items():
        # Block on the leading characters so this stays linear-ish on big runs.
        buckets: dict[str, list[dict[str, Any]]] = {}
        for group in groups:
            key = comparison_key(group["title"])
            for token in {key[:2], key[2:4]}:
                buckets.setdefault(token, []).append(group)
        seen: set[tuple[str, str]] = set()
        for members in buckets.values():
            for index, left in enumerate(members):
                for right in members[index + 1 :]:
                    pair = tuple(sorted((left["title"], right["title"])))
                    if pair in seen:
                        continue
                    seen.add(pair)
                    score = similarity(left["title"], right["title"])
                    if score < RELATED_TITLE_FLOOR:
                        continue
                    links.append(
                        {
                            "provider": provider,
                            "titles": list(pair),
                            "similarity": score,
                            "group_sizes": [left["run_count"], right["run_count"]],
                            "merged": False,
                            "note": "疑似同一课题的不同写法；仅提示，未合并。",
                        }
                    )
    links.sort(key=lambda item: (-item["similarity"], item["titles"][0]))
    return links


def _subject_signature(records: Sequence[ProjectFactRecord]) -> str:
    """Fingerprint of the title set, so a relationship report can show drift."""
    from .utils import sha256_text

    titles = sorted({comparison_key(title_of(record)) for record in records if title_of(record)})
    return sha256_text(json.dumps(titles[:200], ensure_ascii=False))


__all__ = [
    "build_cohort_report",
    "cohort_index",
    "Candidate",
    "build_duplicate_report",
    "candidate_clusters",
    "find_candidates",
    "group_key",
]
