"""Identity merges: an explicit human decision to treat two records as one.

A merge is the one operation in this package that destroys an identity, so it
is the one that must never be inferred. There is no auto-merge path at all:
`merge.py` only reads decisions from a file that a human wrote.

Two guards, same philosophy as review:

* **A decision names the evidence it reviewed.** Each merge stores a
  fingerprint over both sides' documents and claim texts. If a re-crawl changes
  either side, the merge goes ``stale`` and stops applying -- an approval to
  collapse two records must not survive a change to what those records say.
* **Staleness is reported, never silently ignored.** The run lists skipped
  merges so a reviewer can see that a decision they wrote is no longer live.

Merging is implemented as *identity union* rather than record rewriting: the
grouping stage puts both sides in one group, and the ordinary field machinery
then does the rest. If the two sides agree, the merged field resolves. If they
disagree, the merged field is still a conflict -- which is correct, because
"same entity, disputed facts" is a real state that a human should see.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .errors import InputError
from .storage import atomic_write_text
from .utils import now_iso, sha256_text

MERGE_FILE = "merges.json"
MERGE_SCHEMA_VERSION = 1


def evidence_fingerprint(documents: Iterable[str], claim_hashes: Iterable[str]) -> str:
    """Fingerprint of everything a merge decision was made against.

    Sets, not lists: a statement repeated twice is still the same statement, so
    whether the grouping stage has de-duplicated claims yet must not change the
    fingerprint. Getting that wrong makes every merge look stale for reasons
    nobody can see.
    """
    return sha256_text(
        json.dumps(
            {"documents": sorted(set(documents)), "claims": sorted(set(claim_hashes))},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def fingerprint_of_claims(claims: Sequence[Any]) -> str:
    """The one way to compute a merge fingerprint.

    Both the decision file and the grouping stage call this. An earlier version
    let each side hash a different field set, which made every merge look stale
    for reasons no human could see -- so the function lives here, not inline.
    """
    return evidence_fingerprint(
        [claim.locator.document_id for claim in claims],
        [sha256_text(claim.raw_text) for claim in claims],
    )


@dataclass(frozen=True)
class MergeDecision:
    """One human decision to treat two identities as one record."""

    left: str
    right: str
    fingerprint: str
    reviewer: str = "unknown"
    merged_at: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.left or not self.right:
            raise InputError("a merge needs both sides")
        if self.left == self.right:
            raise InputError("a merge needs two different identities")
        if not self.fingerprint:
            raise InputError("a merge must record the evidence it was made against")

    def key(self) -> tuple[str, str]:
        return (self.left, self.right)

    def to_dict(self) -> dict[str, Any]:
        return {
            "left": self.left,
            "right": self.right,
            "fingerprint": self.fingerprint,
            "reviewer": self.reviewer,
            "merged_at": self.merged_at or now_iso(),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MergeDecision":
        if not isinstance(payload, dict):
            raise InputError("each merge must be an object")
        return cls(
            left=str(payload.get("left", "")),
            right=str(payload.get("right", "")),
            fingerprint=str(payload.get("fingerprint", "")),
            reviewer=str(payload.get("reviewer", "unknown")),
            merged_at=str(payload.get("merged_at", "")),
            note=str(payload.get("note", "")),
        )


class UnionFind:
    """Canonical ordering, so the same set always produces the same key."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, node: str) -> str:
        self.parent.setdefault(node, node)
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[node] != root:  # path compression
            self.parent[node], node = root, self.parent[node]
        return root

    def union(self, left: str, right: str) -> str:
        root_left, root_right = self.find(left), self.find(right)
        if root_left == root_right:
            return root_left
        winner, loser = sorted((root_left, root_right))
        self.parent[loser] = winner
        return winner

    def members(self, node: str) -> list[str]:
        return sorted(key for key in self.parent if self.find(key) == self.find(node))


@dataclass
class MergeRegistry:
    """Decisions loaded from ``merges.json`` plus the outcome of applying them."""

    decisions: dict[tuple[str, str], MergeDecision] = None  # type: ignore[assignment]
    path: Path | None = None
    applied: list[dict[str, Any]] = None  # type: ignore[assignment]
    skipped: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.decisions is None:
            self.decisions = {}
        if self.applied is None:
            self.applied = []
        if self.skipped is None:
            self.skipped = []

    def add(self, decision: MergeDecision) -> MergeDecision:
        self.decisions[decision.key()] = decision
        return decision

    def resolve(
        self,
        key_of: dict[str, tuple[str, str]],
        side_evidence: dict[tuple[str, str], tuple[list[str], list[str]]],
    ):
        """Return ``(union_find, applied, skipped)`` after checking each decision.

        ``key_of`` maps an identity key to the string used in a decision file.
        ``side_evidence`` supplies the documents and claim hashes each side had
        when the decisions were written, so a stale decision can be detected.
        """
        finder = UnionFind()
        applied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for decision in self.decisions.values():
            if not decision.reviewer.strip():
                # A proposal with no name on it is a draft, not a decision. The
                # proposal tool writes one on purpose so it cannot take effect by
                # accident.
                skipped.append(
                    {
                        "left": decision.left,
                        "right": decision.right,
                        "reason": "awaiting_reviewer",
                        "note": "提案未署名，等待人工确认后才生效。",
                    }
                )
                continue
            pair = (
                key_of.get(decision.left, ("", decision.left)),
                key_of.get(decision.right, ("", decision.right)),
            )
            left_side = side_evidence.get(pair[0])
            right_side = side_evidence.get(pair[1])
            if left_side is None or right_side is None:
                skipped.append(
                    {
                        "left": decision.left,
                        "right": decision.right,
                        "reason": "one_side_absent",
                        "note": "决定中记录的一方在本次运行里不存在，已跳过。",
                    }
                )
                continue
            current = evidence_fingerprint(
                [*left_side[0], *right_side[0]], [*left_side[1], *right_side[1]]
            )
            if current != decision.fingerprint:
                skipped.append(
                    {
                        "left": decision.left,
                        "right": decision.right,
                        "reason": "evidence_changed_since_decision",
                        "note": "证据已变化，合并失效，需重新确认。",
                    }
                )
                continue
            finder.union(pair[0], pair[1])
            applied.append(
                {
                    "left": decision.left,
                    "right": decision.right,
                    "reviewer": decision.reviewer,
                    "merged_at": decision.merged_at,
                    "note": decision.note,
                    "fingerprint": decision.fingerprint,
                }
            )
        return finder, applied, skipped

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": MERGE_SCHEMA_VERSION,
            "rule": "合并是人工决定，且绑定证据指纹；证据变化即失效。本包不会自动合并。",
            "merges": [self.decisions[key].to_dict() for key in sorted(self.decisions)],
        }

    def save(self, path: Path | str | None = None) -> Path:
        target = Path(path or self.path or MERGE_FILE)
        atomic_write_text(target, json.dumps(self.to_payload(), ensure_ascii=False, indent=2) + "\n")
        self.path = target
        return target

    @classmethod
    def load(cls, path: Path | str) -> "MergeRegistry":
        target = Path(path)
        registry = cls(path=target)
        if not target.exists():
            return registry
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InputError(f"{target} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise InputError(f"{target} must be a JSON object")
        for item in payload.get("merges", []):
            decision = MergeDecision.from_dict(item)
            registry.decisions[decision.key()] = decision
        return registry

    def summary(self) -> dict[str, Any]:
        return {
            "decisions": len(self.decisions),
            "applied": len(self.applied),
            "skipped": len(self.skipped),
            "applied_list": self.applied,
            "skipped_list": self.skipped,
        }


__all__ = [
    "MERGE_FILE",
    "fingerprint_of_claims",
    "MergeDecision",
    "MergeRegistry",
    "UnionFind",
    "evidence_fingerprint",
]
