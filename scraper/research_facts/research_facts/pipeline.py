"""Ingest pipeline: read sources, extract evidence, merge, report, write.

The run is deliberately linear and inspectable:

    read adapters -> merge into records -> index evidence -> build reports
    -> compute content digest -> write outputs

``content_digest`` covers only the fact payload. Re-running the same inputs
reproduces the same digest, which is how the idempotency requirement is checked
without trusting file timestamps.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Sequence

from .adapters import (
    TABLE_PROFILES,
    build_adapter,
    describe_adapters,
    load_profile_file,
)
from .adapters.csv_table import table_profiles_from_file
from .adapters.base import AdapterOutput
from .config import FIELD_NAMES, SOURCE_KINDS, Settings, field_label
from .errors import FactPackageError
from .logging_utils import (
    EV_DOCUMENT,
    EV_ERROR,
    EV_INPUT_READ,
    EV_RUN_END,
    EV_RUN_START,
    get_logger,
    log_event,
)
from .dedup import build_cohort_report, build_duplicate_report, cohort_index
from .merge import build_records
from .merging import MergeRegistry
from .projections import build_public_rows
from .reports import (
    build_conflict_report,
    build_evidence_index,
    build_missing_report,
    build_promotional_report,
    build_quality_summary,
    build_rejected_report,
)
from .review import ReviewRegistry
from .schema import ProjectFactRecord
from .storage import content_digest, write_json, write_jsonl
from .utils import file_digest, now_iso


@dataclass
class IngestResult:
    settings: Settings
    records: list[ProjectFactRecord] = dc_field(default_factory=list)
    documents: list[dict[str, Any]] = dc_field(default_factory=list)
    evidence_index: list[dict[str, Any]] = dc_field(default_factory=list)
    public_rows: list[dict[str, Any]] = dc_field(default_factory=list)
    reports: dict[str, Any] = dc_field(default_factory=dict)
    manifest: dict[str, Any] = dc_field(default_factory=dict)
    errors: dict[str, int] = dc_field(default_factory=dict)
    inputs: list[dict[str, Any]] = dc_field(default_factory=list)
    reviews: ReviewRegistry = dc_field(default_factory=ReviewRegistry)
    merges: MergeRegistry = dc_field(default_factory=MergeRegistry)
    rejected: list[dict[str, Any]] = dc_field(default_factory=list)

    @property
    def digest(self) -> str:
        return str(self.manifest.get("content_digest", ""))

    def fact_rows(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self.records]


def _line_error_reporter(logger, path: str, errors: dict[str, int]):
    """Count a malformed line and keep going instead of losing the whole file."""

    def report(line_number: int, error: Exception) -> None:
        errors["parse_error"] = errors.get("parse_error", 0) + 1
        log_event(
            logger,
            EV_ERROR,
            "line skipped",
            input=path,
            line=line_number,
            category="parse_error",
            detail=str(error),
        )

    return report


def _load_inputs(
    settings: Settings,
) -> tuple[list[AdapterOutput], list[dict[str, Any]], dict[str, int], ReviewRegistry]:
    logger = get_logger()
    outputs: list[AdapterOutput] = []
    inputs_meta: list[dict[str, Any]] = []
    errors: dict[str, int] = {}

    registry = ReviewRegistry()
    review_path = Path(settings.review_file) if settings.review_file else None
    merges = MergeRegistry()
    merge_path = Path(settings.merge_file) if settings.merge_file else None
    if merge_path is not None and merge_path.exists():
        try:
            merges = MergeRegistry.load(merge_path)
            log_event(
                logger, EV_INPUT_READ, "merges loaded",
                merge_file=str(merge_path), decisions=len(merges.decisions),
            )
        except (FactPackageError, OSError, ValueError) as exc:
            errors["input_error"] = errors.get("input_error", 0) + 1
            log_event(logger, EV_ERROR, "merge file failed", input=str(merge_path), detail=str(exc))
            merges = MergeRegistry()
    if review_path is not None and review_path.exists():
        try:
            registry = ReviewRegistry.load(review_path)
            log_event(
                logger,
                EV_INPUT_READ,
                "reviews loaded",
                review_file=str(review_path),
                decisions=len(registry.decisions),
            )
        except (FactPackageError, OSError, ValueError) as exc:
            errors["input_error"] = errors.get("input_error", 0) + 1
            log_event(logger, EV_ERROR, "review file failed", input=str(review_path), detail=str(exc))
            registry = ReviewRegistry()

    for profile_file in settings.profile_files:
        try:
            for table in table_profiles_from_file(profile_file):
                TABLE_PROFILES[table.name] = table
                log_event(
                    logger, EV_INPUT_READ, "table profile loaded",
                    profile=table.name, provider=table.provider,
                )
        except (FactPackageError, OSError, ValueError) as exc:
            errors["input_error"] = errors.get("input_error", 0) + 1
            log_event(logger, EV_ERROR, "table profile failed", input=profile_file, detail=str(exc))
        try:
            profile = load_profile_file(profile_file)
            log_event(logger, EV_INPUT_READ, "profile file loaded", profile=profile.name, provider=profile.provider)
        except (FactPackageError, OSError, ValueError) as exc:
            errors["input_error"] = errors.get("input_error", 0) + 1
            log_event(logger, EV_ERROR, "profile file failed", input=profile_file, detail=str(exc))

    for raw_path in settings.inputs:
        path = Path(raw_path)
        source_kind = None
        # "--path:kind" keeps multi-kind runs on one command line. The list
        # comes from config so a new source kind cannot be half-wired.
        if ":" in path.name and path.name.rsplit(":", 1)[-1] in SOURCE_KINDS:
            path = Path(str(path).rsplit(":", 1)[0])
            source_kind = str(raw_path).rsplit(":", 1)[-1]
        try:
            adapter = build_adapter(path, source_kind=source_kind, profile=settings.profile)
        except FactPackageError as exc:
            errors[exc.category] = errors.get(exc.category, 0) + 1
            log_event(logger, EV_ERROR, "adapter resolution failed", input=str(raw_path), category=exc.category, detail=str(exc))
            continue

        try:
            setattr(adapter, "on_error", _line_error_reporter(logger, str(path), errors))
            loaded = adapter.load(path, settings)
        except FactPackageError as exc:
            errors[exc.category] = errors.get(exc.category, 0) + 1
            log_event(logger, EV_ERROR, "input read failed", input=str(raw_path), category=exc.category, detail=str(exc))
            continue

        truncated = 0
        if settings.max_records is not None and len(loaded) > settings.max_records:
            truncated = len(loaded) - settings.max_records
            loaded = loaded[: settings.max_records]

        outputs.extend(loaded)
        digest = file_digest(path) if path.exists() else ""
        inputs_meta.append(
            {
                "path": str(path),
                "sha256": digest,
                "adapter": adapter.name,
                "source_kind": adapter.source_kind,
                "documents": len(loaded),
                "claims": sum(len(item.claims) for item in loaded),
                "truncated_documents": truncated,
            }
        )
        log_event(
            logger,
            EV_INPUT_READ,
            "input read",
            input=str(path),
            adapter=adapter.name,
            documents=len(loaded),
            claims=sum(len(item.claims) for item in loaded),
        )
        for item in loaded:
            log_event(
                logger,
                EV_DOCUMENT,
                "document loaded",
                document_id=item.document.document_id,
                source_kind=item.document.source_kind,
                claims=len(item.claims),
            )
    return outputs, inputs_meta, errors, registry, merges


def _document_rows(outputs: Sequence[AdapterOutput]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for output in outputs:
        payload = output.document.to_dict()
        payload["meta"] = {
            **payload.get("meta", {}),
            "claim_count": len(output.claims),
            "unmapped_source_keys": list(output.unmapped_source_keys),
            "rejected_count": len(output.rejected),
        }
        rows.append(payload)
    rows.sort(key=lambda row: row["document_id"])
    return rows


def _build_reports(
    records: Sequence[ProjectFactRecord],
    documents: Sequence[dict[str, Any]],
    settings: Settings,
    inputs: Sequence[dict[str, Any]],
    errors: dict[str, int],
    digest: str,
) -> dict[str, Any]:
    return {
        "missing": build_missing_report(records),
        "conflict": build_conflict_report(records),
        "promotional": build_promotional_report(records, documents),
        "quality": build_quality_summary(
            records=records,
            documents=documents,
            settings_payload=settings.describe(),
            inputs=inputs,
            errors=errors,
            content_digest=digest,
        ),
    }


def run_dry_run(settings: Settings) -> dict[str, Any]:
    """Inspect inputs without writing anything."""
    outputs, inputs_meta, errors, registry, merges = _load_inputs(settings)
    records, stats = build_records(outputs, settings, registry, merges)
    documents = _document_rows(outputs)
    return {
        "dry_run": True,
        "settings": settings.describe(),
        "adapters": describe_adapters(),
        "inputs": inputs_meta,
        "expected_fields": [
            {"field": name, "label": field_label(name)} for name in FIELD_NAMES
        ],
        "would_write": {
            "facts": str(settings.facts_path),
            "evidence_index": str(settings.evidence_index_path),
            "documents": str(settings.documents_path),
        "rejected_candidates": str(settings.rejected_path),
            "missing_report": str(settings.missing_report_path),
            "conflict_report": str(settings.conflict_report_path),
            "promotional_report": str(settings.promotional_report_path),
            "quality_summary": str(settings.quality_summary_path),
        "duplicate_candidates": str(settings.duplicates_path),
        "cohort_groups": str(settings.cohorts_path),
            "public_facts": str(settings.public_facts_path),
            "manifest": str(settings.manifest_path),
        },
        "preview": {
            "documents": stats["documents"],
            "records": stats["records"],
            "claims": stats["claims"],
            "groups_by_basis": stats["groups_by_basis"],
        },
        "errors": errors,
        "note": "dry-run 不写入任何文件。",
    }


def ingest(settings: Settings) -> IngestResult:
    logger = get_logger()
    started_at = now_iso()
    log_event(logger, EV_RUN_START, "run start", inputs=len(settings.inputs), output_dir=str(settings.output_dir))

    outputs, inputs_meta, errors, registry, merges = _load_inputs(settings)
    records, stats = build_records(outputs, settings, registry, merges)
    documents = _document_rows(outputs)
    fact_rows = [record.to_dict() for record in records]
    digest = content_digest(fact_rows)

    reports = _build_reports(records, documents, settings, inputs_meta, errors, digest)
    public_rows, public_summary = build_public_rows(records, registry)
    evidence_index = build_evidence_index(records)
    rejected_rows = build_rejected_report(outputs)
    # Design doc 4.7: candidates only. This never merges anything.
    duplicates = build_duplicate_report(records)
    # Same topic, different runs: a report, never a merge. Built before the
    # public projection so the projection can carry cohort context.
    cohorts = build_cohort_report(records)
    cohort_map = cohort_index(cohorts)
    public_rows, public_summary = build_public_rows(records, registry, cohort_map)

    result = IngestResult(
        settings=settings,
        records=records,
        documents=documents,
        evidence_index=evidence_index,
        rejected=rejected_rows,
        public_rows=public_rows,
        reports=reports,
        inputs=inputs_meta,
        errors=errors,
        reviews=registry,
        merges=merges,
    )
    result.manifest = {
        "run_id": uuid.uuid4().hex,
        "started_at": started_at,
        "finished_at": now_iso(),
        "settings": settings.describe(),
        "inputs": inputs_meta,
        "merges": {
            "file": str(merges.path) if merges.path else None,
            "sha256": file_digest(merges.path) if merges.path and merges.path.exists() else None,
            **merges.summary(),
        },
        "cohorts": {
            "topic_groups": cohorts["topic_groups"],
            "records_in_groups": cohorts["records_in_groups"],
        },
        "reviews": {
            "file": str(registry.path) if registry.path else None,
            "sha256": file_digest(registry.path) if registry.path and registry.path.exists() else None,
            "decisions": len(registry.decisions),
            "counts": registry.counts(),
            "applied": {
                "approved_fields": public_summary["approved_fields"],
                "stale_approvals": public_summary["stale_approvals"],
                "rejected_fields": public_summary["rejected_fields"],
            },
        },
        "counts": {
            "documents": len(documents),
            "records": len(records),
            "claims": sum(len(item.claims) for item in outputs),
            "evidence_rows": len(evidence_index),
            "rejected_candidates": len(rejected_rows),
            "adjudicated_fields": stats.get("adjudicated_fields", 0),
            "merged_records": stats.get("merged_records", 0),
            "cohort_groups": cohorts["topic_groups"],
            "duplicate_candidates": duplicates["candidate_count"],
            "high_confidence_duplicates": duplicates["high_confidence_count"],
            "groups_by_basis": stats["groups_by_basis"],
        },
        "content_digest": digest,
        "public_summary": public_summary,
        "errors": errors,
        "outputs": {
            "facts": str(settings.facts_path),
            "evidence_index": str(settings.evidence_index_path),
            "documents": str(settings.documents_path),
        "rejected_candidates": str(settings.rejected_path),
            "missing_report": str(settings.missing_report_path),
            "conflict_report": str(settings.conflict_report_path),
            "promotional_report": str(settings.promotional_report_path),
            "quality_summary": str(settings.quality_summary_path),
        "duplicate_candidates": str(settings.duplicates_path),
        "cohort_groups": str(settings.cohorts_path),
            "public_facts": str(settings.public_facts_path),
        },
    }

    if settings.dry_run:
        log_event(logger, EV_RUN_END, "dry run finished", records=len(records), documents=len(documents))
        return result

    settings.ensure_output_dirs()
    write_jsonl(settings.facts_path, fact_rows)
    write_jsonl(settings.evidence_index_path, evidence_index)
    write_jsonl(settings.documents_path, documents)
    write_jsonl(settings.rejected_path, rejected_rows)
    write_jsonl(settings.public_facts_path, public_rows)
    write_json(settings.missing_report_path, reports["missing"])
    write_json(settings.conflict_report_path, reports["conflict"])
    write_json(settings.promotional_report_path, reports["promotional"])
    write_json(settings.quality_summary_path, reports["quality"])
    write_json(settings.duplicates_path, duplicates)
    write_json(settings.cohorts_path, cohorts)
    write_json(settings.manifest_path, result.manifest)

    log_event(
        logger,
        EV_RUN_END,
        "run finished",
        records=len(records),
        documents=len(documents),
        conflicts=reports["conflict"]["total_conflicts"],
        promotional=reports["promotional"]["total"],
        content_digest=digest,
    )
    return result
