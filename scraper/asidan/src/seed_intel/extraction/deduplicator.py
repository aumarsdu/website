from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from seed_intel.extraction.schema import ProjectRecord


@dataclass
class DuplicateDecision:
    canonical_project_uid: str
    duplicate_project_uid: str
    duplicate_reason: str
    confidence: float


def find_duplicates(records: list[ProjectRecord]) -> list[DuplicateDecision]:
    decisions: list[DuplicateDecision] = []
    for index, current in enumerate(records):
        for prior in records[:index]:
            if current.source_url == prior.source_url:
                decisions.append(DuplicateDecision(prior.project_uid or "", current.project_uid or "", "same_source_url", 1.0))
                break
            if (
                current.project_name
                and prior.project_name
                and current.project_name == prior.project_name
                and current.source_domain == prior.source_domain
                and current.application_deadline == prior.application_deadline
            ):
                decisions.append(DuplicateDecision(prior.project_uid or "", current.project_uid or "", "name_domain_deadline", 0.95))
                break
            ratio = SequenceMatcher(None, current.project_name or "", prior.project_name or "").ratio()
            if ratio > 0.92:
                decisions.append(DuplicateDecision(prior.project_uid or "", current.project_uid or "", "similar_project_name", ratio))
                break
    return decisions


def unique_projects(records: list[ProjectRecord]) -> list[ProjectRecord]:
    duplicate_ids = {item.duplicate_project_uid for item in find_duplicates(records)}
    return [record for record in records if record.project_uid not in duplicate_ids]
