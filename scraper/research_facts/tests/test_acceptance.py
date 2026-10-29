"""The four acceptance criteria, asserted end to end.

1. Unknown fields are not filled in.
2. Conflicting material keeps both sides' evidence.
3. Repeated imports produce identical output.
4. Supplier marketing is not treated as a verified fact.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_facts.config import FIELD_NAMES
from research_facts.pipeline import ingest
from research_facts.schema import VERIFICATION_STATUS

from .context import PipelineTestCase, build_settings, silence_logs


class TestCriterion1UnknownFieldsAreNotFilledIn(PipelineTestCase):
    def test_field_with_no_evidence_is_missing_with_a_null_value(self) -> None:
        record = self.record("RS_2027_0207")
        for name in ("instructor", "suitable_audience"):
            state = record.fields[name]
            self.assertEqual(state.status, "missing", name)
            self.assertIsNone(state.selected_normalized_value, name)
            self.assertIsNone(state.selected_raw_text, name)
            self.assertEqual(state.claims, [], name)

    def test_missing_fields_still_carry_an_explanation(self) -> None:
        record = self.record("RS_2027_0207")
        self.assertIn("未补写", record.fields["instructor"].note)

    def test_no_record_ever_claims_a_value_for_a_missing_field(self) -> None:
        for record in self.result.records:
            for name, state in record.fields.items():
                if state.status == "missing":
                    self.assertIsNone(state.selected_normalized_value, f"{record.record_key}.{name}")

    def test_partial_date_keeps_its_precision_instead_of_a_day(self) -> None:
        record = self.record("滨海湿地")
        state = record.fields["start_date"]
        self.assertEqual(state.selected_raw_text, "2027年9月")
        self.assertEqual(state.selected_normalized_value, "2027-09")
        self.assertEqual(state.claims[0].normalization["day"], "not_stated")

    def test_unmapped_source_keys_are_reported_not_guessed(self) -> None:
        # "providerNote" and "crawled_at" exist in the payload but no profile path
        # claims them, so they must not appear as extracted field values.
        unmapped = {
            key
            for doc in self.result.documents
            if doc["source_kind"] == "web_json"
            for key in doc["meta"].get("unmapped_source_keys", [])
        }
        self.assertIn("providerNote", unmapped)
        for record in self.result.records:
            for state in record.fields.values():
                for claim in state.claims:
                    self.assertNotEqual(claim.normalized_value, "合成数据，非真实供应商")


class TestCriterion2ConflictsKeepBothSides(PipelineTestCase):
    def test_duration_conflict_keeps_every_side(self) -> None:
        record = self.record("RS_2027_0142")
        state = record.fields["duration"]
        self.assertEqual(state.status, "conflict")
        self.assertIsNone(state.selected_normalized_value)
        self.assertEqual(len(state.conflict_values), 2)
        self.assertIn("4周+2周", state.conflict_values)
        self.assertIn("8周", state.conflict_values)

    def test_both_sides_carry_their_own_locator(self) -> None:
        record = self.record("RS_2027_0142")
        state = record.fields["duration"]
        locators = {claim.locator.document_id for claim in state.claims}
        self.assertEqual(
            locators,
            {"demo-partner#RS-2027-0142", "handbook-RS-2027-0142", "poster-RS-2027-0142"},
        )
        for claim in state.claims:
            self.assertTrue(claim.locator.pointer, "a conflict side must point at its source")
            self.assertTrue(claim.raw_text)

    def test_conflict_report_keeps_both_values_and_resolution_is_manual(self) -> None:
        report = self.result.reports["conflict"]
        self.assertGreaterEqual(report["total_conflicts"], 1)
        duration = next(
            item
            for item in report["conflicts"]
            if item["record_key"].endswith("RS_2027_0142") and item["field"] == "duration"
        )
        self.assertEqual(duration["resolution"], "manual_review_required")
        values = {value["value"] for value in duration["values"]}
        self.assertEqual(values, {"4周+2周", "8周"})
        sides = [side for value in duration["values"] for side in value["sides"]]
        self.assertEqual(len(sides), 3)
        self.assertTrue(all(side["locator"] for side in sides))

    def test_near_duplicate_title_is_reported_not_merged(self) -> None:
        # "城市热岛与街谷风环境模拟" vs "城市热岛效应与街谷风环境模拟" differ,
        # and neither contains the other, so this must stay a conflict.
        state = self.record("RS_2027_0311").fields["project_title"]
        self.assertEqual(state.status, "conflict")
        self.assertIsNone(state.selected_normalized_value)

    def test_short_and_full_title_of_the_same_project_is_not_a_conflict(self) -> None:
        state = self.record("RS_2027_0142").fields["project_title"]
        self.assertEqual(state.status, "resolved")
        self.assertEqual(len(state.claims), 3)
        self.assertIn("简称/全称", state.note)


class TestCriterion3RepeatedImportsAreStable(unittest.TestCase):
    def setUp(self) -> None:
        silence_logs()

    def test_two_runs_produce_identical_files_and_digest(self) -> None:
        digests = []
        snapshots = []
        for run in ("run1", "run2"):
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / run
                result = ingest(build_settings(output_dir))
                digests.append(result.digest)
                snapshots.append(
                    {
                        name: (output_dir / name).read_text(encoding="utf-8")
                        for name in (
                            "facts.jsonl",
                            "evidence_index.jsonl",
                            "documents.jsonl",
                            "missing_report.json",
                            "conflict_report.json",
                            "promotional_claims_report.json",
                        )
                    }
                )
        self.assertEqual(digests[0], digests[1], "content_digest must not depend on run time")
        for name in snapshots[0]:
            self.assertEqual(
                snapshots[0][name], snapshots[1][name], f"{name} must be byte-identical between runs"
            )

    def test_record_key_is_stable_and_does_not_depend_on_input_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            forward = ingest(build_settings(Path(tmp) / "a"))
            settings = build_settings(Path(tmp) / "b")
            settings.inputs = list(reversed(settings.inputs))
            backward = ingest(settings)
        self.assertEqual(
            [record.record_key for record in forward.records],
            [record.record_key for record in backward.records],
        )
        self.assertEqual(forward.digest, backward.digest)

    def test_record_key_is_readable_and_derived_from_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = ingest(build_settings(Path(tmp)))
        keys = {record.record_key for record in result.records}
        self.assertIn("demo-partner:external_id:RS_2027_0142", keys)
        # Re-running must not invent a different key for the same project.
        self.assertEqual(len(keys), len(result.records))

    def test_document_without_external_id_is_flagged_as_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = ingest(build_settings(Path(tmp)))
        record = next(item for item in result.records if "滨海湿地" in item.record_key)
        self.assertEqual(record.identity.basis, "title")
        self.assertTrue(record.identity.review_required)
        self.assertIn("identity_not_stable", [issue["type"] for issue in record.issues])


class TestCriterion4MarketingIsNotAVerifiedFact(PipelineTestCase):
    def test_every_claim_is_unverified(self) -> None:
        for record in self.result.records:
            for name in FIELD_NAMES:
                for claim in record.fields[name].claims:
                    self.assertEqual(claim.verification_status, VERIFICATION_STATUS)
                    self.assertEqual(claim.verification_status, "unverified")

    def test_purely_promotional_field_yields_no_value(self) -> None:
        state = self.record("RS_2027_0207").fields["output_description"]
        self.assertEqual(state.status, "promotional_only")
        self.assertIsNone(state.selected_normalized_value)
        self.assertIsNone(state.selected_raw_text)
        self.assertEqual(state.claims[0].evidence_kind, "prohibited_claim")
        self.assertEqual(state.claims[0].deliverable_claim_type, "prohibited")

    def test_purely_promotional_field_is_reported_as_not_usable_not_as_fact(self) -> None:
        report = self.result.reports["missing"]
        blocked = report["not_usable_by_field"]["output_description"]
        self.assertEqual(blocked["by_status"].get("promotional_only"), 1)
        self.assertIn(
            "demo-partner:external_id:RS_2027_0207",
            blocked["record_keys"]["promotional_only"],
        )
        # It is not counted as a plain missing field: something *was* said.
        self.assertNotIn(
            "demo-partner:external_id:RS_2027_0207",
            report["by_field"]["output_description"]["record_keys"],
        )

    def test_mixed_field_is_flagged_but_still_usable_internally(self) -> None:
        state = self.record("RS_2027_0311").fields["output_description"]
        self.assertEqual(state.status, "resolved_with_promotional")
        self.assertTrue(state.has_promotional_evidence)
        self.assertIn("宣传", state.note)
        self.assertIn("100%保录QS前50", state.selected_raw_text)

    def test_public_projection_withholds_high_risk_fields(self) -> None:
        row = next(
            item for item in self.result.public_rows if "RS_2027_0311" in item["record_key"]
        )
        self.assertNotIn("instructor", row["display"])
        self.assertNotIn("output_description", row["display"])
        queued = {item["field"] for item in row["review_queue"]}
        self.assertEqual(queued, {"instructor", "output_description"})

    def test_public_projection_strips_marketing_from_the_review_draft(self) -> None:
        row = next(
            item for item in self.result.public_rows if "RS_2027_0311" in item["record_key"]
        )
        draft = next(item for item in row["review_queue"] if item["field"] == "output_description")
        self.assertNotIn("100%保录", draft["draft_text"])
        self.assertGreaterEqual(draft["marketing_segments_withheld"], 1)
        # The full value is still available to the reviewer.
        self.assertIn("100%保录", draft["draft_value"])

    def test_public_values_carry_attribution_and_unverified_status(self) -> None:
        for row in self.result.public_rows:
            for entry in row["display"].values():
                self.assertEqual(entry["verification_status"], "unverified")
                self.assertEqual(entry["attribution"], "supplier_statement")

    def test_nothing_is_publishable_before_human_review(self) -> None:
        self.assertTrue(all(row["publishable"] is False for row in self.result.public_rows))
        self.assertGreater(
            self.result.manifest["public_summary"]["review_queue_items"], 0
        )

    def test_promotional_report_lists_every_promise_with_a_disclaimer(self) -> None:
        report = self.result.reports["promotional"]
        self.assertGreater(report["total"], 0)
        self.assertTrue(all(item["required_disclaimer"] for item in report["claims"]))
        kinds = set(report["by_kind"])
        self.assertIn("prohibited_claim", kinds)
        self.assertTrue(report["marketing_source_documents"], "posters must be marked as marketing origin")

    def test_promotional_phrase_never_reaches_a_public_display_value(self) -> None:
        for row in self.result.public_rows:
            for entry in row["display"].values():
                self.assertNotIn("保录", entry["text"] or "")
                self.assertNotIn("保证发表", entry["text"] or "")


class TestOutputContract(PipelineTestCase):
    def test_every_record_carries_all_six_canonical_fields(self) -> None:
        for record in self.result.records:
            self.assertEqual(set(record.fields), set(FIELD_NAMES))

    def test_facts_file_is_valid_jsonl_with_required_metadata(self) -> None:
        path = self.result.settings.facts_path
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        self.assertEqual(len(rows), len(self.result.records))
        for row in rows:
            self.assertIn("record_key", row)
            self.assertIn("identity", row)
            for state in row["fields"].values():
                self.assertIn("verification_status", state)
                for claim in state.get("claims", []):
                    self.assertIn("raw_text", claim)
                    self.assertIn("locator", claim)
                    self.assertIn("document_id", claim["locator"])

    def test_evidence_index_has_one_row_per_claim(self) -> None:
        claim_total = sum(
            len(state.claims)
            for record in self.result.records
            for state in record.fields.values()
        )
        self.assertEqual(len(self.result.evidence_index), claim_total)
        row = self.result.evidence_index[0]
        for key in ("record_key", "field", "document_id", "locator", "raw_text_sha256", "extraction_confidence"):
            self.assertIn(key, row)

    def test_evidence_index_is_sorted(self) -> None:
        keys = [
            (row["record_key"], row["field"], row["document_id"], row["locator"])
            for row in self.result.evidence_index
        ]
        self.assertEqual(keys, sorted(keys))

    def test_documents_file_records_source_authority(self) -> None:
        authorities = {doc["source_authority"] for doc in self.result.documents}
        self.assertEqual(authorities, {"supplier_official", "supplier_marketing"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
