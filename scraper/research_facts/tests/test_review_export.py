"""Human review decisions and the fact-card export.

The properties that matter here:

1. An approval unlocks field eligibility, nothing else. A ``prohibited_claim``
   sentence stays out of customer-facing copy even after a human signs off.
2. An approval is bound to the evidence that was reviewed. If the underlying
   text changes, the decision goes stale and the field returns to the queue.
3. A field that cannot be reviewed (missing, conflict, promotional-only) cannot
   be approved at all.
4. The exported card shows every claim and names every gap, so a writer never
   has to guess which value was used and which were rejected.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_facts.config import FIELD_NAMES, Settings
from research_facts.merge import build_records
from research_facts.exporter import CARD_FIELDS, build_export, render_markdown, render_public_markdown
from research_facts.projections import build_public_rows
from research_facts.review import ReviewRegistry, evidence_fingerprint
from research_facts.schema import FieldState

from .context import HANDBOOK_JSONL, POSTER_JSONL, WEB_JSONL, PipelineTestCase


class TestFingerprint(unittest.TestCase):
    def _state(self, text: str = "示例导师甲") -> FieldState:
        return FieldState(field="instructor", status="resolved", selected_raw_text=text)

    def test_same_evidence_gives_the_same_fingerprint(self) -> None:
        self.assertEqual(evidence_fingerprint(self._state()), evidence_fingerprint(self._state()))

    def test_changed_text_changes_the_fingerprint(self) -> None:
        self.assertNotEqual(
            evidence_fingerprint(self._state()), evidence_fingerprint(self._state("示例导师戊"))
        )

    def test_empty_fingerprint_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            ReviewRegistry().set("k", "instructor", "approved", "")

    def test_unknown_verdict_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            ReviewRegistry().set("k", "instructor", "maybe", "fp")


class TestRegistry(PipelineTestCase):
    def test_status_transitions(self) -> None:
        registry = ReviewRegistry()
        key = "rec"
        self.assertEqual(registry.status_for(key, "instructor", "fp"), "pending")
        registry.set(key, "instructor", "approved", "fp")
        self.assertEqual(registry.status_for(key, "instructor", "fp"), "approved")
        # Evidence moved on: the same decision no longer applies.
        self.assertEqual(registry.status_for(key, "instructor", "other"), "stale")
        registry.set(key, "instructor", "rejected", "other")
        self.assertEqual(registry.status_for(key, "instructor", "other"), "rejected")
        self.assertTrue(registry.reset(key, "instructor"))
        self.assertEqual(registry.status_for(key, "instructor", "other"), "pending")
        self.assertFalse(registry.reset(key, "instructor"))

    def test_save_and_load_round_trip_is_sorted(self) -> None:
        registry = ReviewRegistry()
        registry.set("b", "instructor", "approved", "fp2")
        registry.set("a", "duration", "rejected", "fp1")
        with tempfile.TemporaryDirectory() as tmp:
            path = registry.save(Path(tmp) / "reviews.json")
            reloaded = ReviewRegistry.load(path)
        self.assertEqual(len(reloaded.decisions), 2)
        keys = [f"{item['record_key']}/{item['field']}" for item in reloaded.rows()]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(reloaded.get("a", "duration").decision, "rejected")
        self.assertEqual(
            reloaded.counts(), {"approved": 1, "rejected": 1, "adjudicated": 0}
        )

    def test_loading_a_missing_file_is_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(len(ReviewRegistry.load(Path(tmp) / "nope.json").decisions), 0)

    def test_loading_broken_json_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(Exception):
                ReviewRegistry.load(path)


class TestApprovalUnlocksButDoesNotBypass(PipelineTestCase):
    """The two properties that keep the review from becoming a loophole."""

    def test_approved_field_enters_the_display(self) -> None:
        record = self.record("RS_2027_0311")
        registry = ReviewRegistry()
        for name in ("instructor", "output_description"):
            registry.set(
                record.record_key,
                name,
                "approved",
                evidence_fingerprint(record.fields[name]),
                reviewer="tester",
            )
        row = next(item for item in build_public_rows(self.result.records, registry)[0]
                   if "0311" in item["record_key"])
        self.assertIn("instructor", row["display"])
        self.assertEqual(row["display"]["instructor"]["verification_status"], "reviewed")
        self.assertEqual(row["display"]["instructor"]["review"]["reviewer"], "tester")
        self.assertEqual(row["review_queue"], [])

    def test_approval_does_not_release_a_promotional_sentence(self) -> None:
        record = self.record("RS_2027_0311")
        registry = ReviewRegistry()
        for name in ("instructor", "output_description"):
            registry.set(
                record.record_key, name, "approved", evidence_fingerprint(record.fields[name])
            )
        row = next(item for item in build_public_rows(self.result.records, registry)[0]
                   if "0311" in item["record_key"])
        published = row["display"]["output_description"]["text"]
        self.assertNotIn("100%保录", published)
        self.assertNotIn("保录", published)
        self.assertGreaterEqual(row["display"]["output_description"]["marketing_segments_withheld"], 1)
        # The reviewer still sees what was withheld.
        state = record.fields["output_description"]
        self.assertIn("100%保录", state.selected_raw_text)

    def test_changed_evidence_makes_the_approval_stale(self) -> None:
        record = self.record("RS_2027_0311")
        registry = ReviewRegistry()
        state = record.fields["instructor"]
        registry.set(record.record_key, "instructor", "approved", evidence_fingerprint(state))
        # Simulate a re-crawl that changed who teaches the topic.
        state.selected_raw_text = "示例导师戊"
        row = next(item for item in build_public_rows(self.result.records, registry)[0]
                   if "0311" in item["record_key"])
        queued = next(item for item in row["review_queue"] if item["field"] == "instructor")
        self.assertEqual(queued["review_status"], "stale")
        self.assertEqual(queued["reason"], "evidence_changed_since_approval")
        self.assertNotIn("instructor", row["display"])
        self.assertFalse(row["publishable"])

    def test_rejected_field_stays_out_and_is_labelled(self) -> None:
        record = self.record("RS_2027_0311")
        registry = ReviewRegistry()
        registry.set(
            record.record_key,
            "instructor",
            "rejected",
            evidence_fingerprint(record.fields["instructor"]),
            note="官网信息对不上",
        )
        row = next(item for item in build_public_rows(self.result.records, registry)[0]
                   if "0311" in item["record_key"])
        queued = next(item for item in row["review_queue"] if item["field"] == "instructor")
        self.assertEqual(queued["reason"], "review_rejected")
        self.assertNotIn("instructor", row["display"])

    def test_summary_counts_match_the_queue(self) -> None:
        _, summary = build_public_rows(self.result.records, ReviewRegistry())
        self.assertEqual(summary["approved_fields"], 0)
        self.assertEqual(summary["stale_approvals"], 0)
        self.assertEqual(summary["rejected_fields"], 0)
        self.assertEqual(summary["review_queue_items"], 3)


class TestExportFactCard(PipelineTestCase):
    def test_card_covers_every_canonical_field(self) -> None:
        card = render_markdown(self.record("RS_2027_0142"))
        for name in CARD_FIELDS:
            self.assertIn(name, card, name)
        self.assertEqual(set(CARD_FIELDS), set(FIELD_NAMES))

    def test_card_shows_the_value_and_its_provenance(self) -> None:
        card = render_markdown(self.record("RS_2027_0142"))
        self.assertIn("**2027-01-08**", card)
        self.assertIn("$.raw.schoolBegins", card)
        self.assertIn("p1#b3", card)
        self.assertIn("证据来源", card)

    def test_conflict_is_named_and_both_sides_are_printed(self) -> None:
        card = render_markdown(self.record("RS_2027_0142"))
        self.assertIn("状态：`conflict`", card)
        self.assertIn("各方说法（均未采用）", card)
        self.assertIn("4周在线小组科研+2周论文指导", card)
        self.assertIn("8周（含2周论文指导）", card)
        self.assertIn("未采用任何一方", card)

    def test_missing_field_is_printed_as_a_gap_not_as_a_value(self) -> None:
        card = render_markdown(self.record("RS_2027_0207"))
        self.assertIn("取值：**来源未给出**", card)
        self.assertIn("未做任何推断补写", card)

    def test_promotional_only_field_is_flagged_in_the_card(self) -> None:
        card = render_markdown(self.record("RS_2027_0207"))
        self.assertIn("该字段只有宣传表述", card)
        self.assertIn("promotional_only", card)

    def test_marketing_evidence_carries_a_warning_marker(self) -> None:
        card = render_markdown(self.record("RS_2027_0311"))
        self.assertIn("⚠️", card)
        self.assertIn("不可作为已证实事实转述", card)

    def test_card_reports_the_review_state_of_high_risk_fields(self) -> None:
        card = render_markdown(self.record("RS_2027_0311"))
        self.assertIn("人工审核：**待审核**", card)
        registry = ReviewRegistry()
        record = self.record("RS_2027_0311")
        registry.set(
            record.record_key,
            "instructor",
            "approved",
            evidence_fingerprint(record.fields["instructor"]),
            reviewer="tester",
        )
        self.assertIn("人工审核：**已过审**", render_markdown(record, registry))

    def test_card_mentions_an_unstable_identity(self) -> None:
        card = render_markdown(self.record("滨海湿地"))
        self.assertIn("归组含猜测", card)

    def test_public_card_lists_gates_and_review_queue(self) -> None:
        rows, _ = build_public_rows(self.result.records, ReviewRegistry())
        text = render_public_markdown(next(row for row in rows if "0311" in row["record_key"]))
        self.assertIn("待人工审核", text)
        self.assertIn("未通过的门禁", text)
        self.assertIn("required_display_title", text)
        self.assertIn("unverified", text)

    def test_build_export_shape(self) -> None:
        internal = build_export(self.result.records)
        self.assertEqual(internal["mode"], "internal")
        self.assertEqual(len(internal["records"]), len(self.result.records))
        self.assertTrue(internal["records"][0]["markdown"].startswith("#"))
        json.dumps(internal["summary"])  # must stay JSON-serializable

        public = build_export(self.result.records, public=True)
        self.assertEqual(public["mode"], "public")
        self.assertIn("publishable", public["records"][0])

    def test_export_only_one_record(self) -> None:
        payload = build_export([self.record("RS_2027_0207")])
        self.assertEqual(len(payload["records"]), 1)
        self.assertIn("RS_2027_0207", payload["records"][0]["record_key"])

    def test_export_is_deterministic(self) -> None:
        first = build_export(self.result.records)["records"][0]["markdown"]
        second = build_export(self.result.records)["records"][0]["markdown"]
        self.assertEqual(first, second)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestConflictAdjudication(PipelineTestCase):
    """A human may pick a side of a conflict -- and only a side."""

    def _duration(self):
        record = self.record("RS_2027_0142")
        return record, record.fields["duration"]

    def _adjudicate(self, record, state, chosen: str, reviewer: str = "tester"):
        registry = ReviewRegistry()
        registry.set(
            record.record_key,
            "duration",
            "adjudicated",
            evidence_fingerprint(state),
            reviewer=reviewer,
            note="人工核对",
            chosen_value=chosen,
        )
        records, _ = build_records(self._outputs(), Settings(), registry)
        return next(item for item in records if item.record_key == record.record_key)

    def _outputs(self):
        from research_facts.adapters import build_adapter
        from research_facts.config import Settings as S

        settings = S()
        outputs = []
        for path, kind in (
            (WEB_JSONL, "web_json"),
            (POSTER_JSONL, "poster_ocr"),
            (HANDBOOK_JSONL, "handbook_pdf"),
        ):
            outputs.extend(build_adapter(path, source_kind=kind).load(path, settings))
        return outputs

    def test_a_conflict_has_no_value_before_adjudication(self) -> None:
        _, state = self._duration()
        self.assertEqual(state.status, "conflict")
        self.assertIsNone(state.selected_normalized_value)
        self.assertIsNone(state.resolution)

    def test_adjudication_resolves_and_records_the_reason(self) -> None:
        record, state = self._duration()
        resolved = self._adjudicate(record, state, "8周").fields["duration"]
        self.assertEqual(resolved.status, "resolved")
        self.assertEqual(resolved.resolution, "human_adjudication")
        self.assertEqual(resolved.selected_normalized_value, "8周")
        self.assertIn("tester", resolved.note)
        self.assertIn("人工核对", resolved.note)

    def test_no_evidence_is_deleted_by_adjudication(self) -> None:
        record, state = self._duration()
        resolved = self._adjudicate(record, state, "8周").fields["duration"]
        self.assertEqual(len(resolved.claims), len(state.claims))
        self.assertEqual(sorted(resolved.conflict_values), sorted(state.conflict_values))

    def test_a_value_no_source_stated_cannot_win(self) -> None:
        record, state = self._duration()
        resolved = self._adjudicate(record, state, "10周（综合推断）").fields["duration"]
        self.assertEqual(resolved.status, "conflict", "a made-up value must be ignored")
        self.assertIsNone(resolved.selected_normalized_value)

    def test_promotional_side_cannot_be_chosen(self) -> None:
        # output_description for RS-2027-0207 is promotional-only, and for
        # RS-2027-0142 every side is a plain statement, so use the poster's
        # purely-promotional value on a purpose-built state.
        from research_facts.merge import _build_field_state
        from research_facts.schema import FieldClaim, Locator

        def claim(text: str, kind: str) -> FieldClaim:
            return FieldClaim(
                field="output_description",
                raw_text=text,
                locator=Locator("json_path", "d1", "$.out"),
                extractor="json_path:$.out",
                extraction_method="json_path",
                extraction_confidence="high",
                evidence_kind=kind,
                has_factual_content=(kind == "factual"),
            )

        state = _build_field_state(
            "output_description", [claim("项目报告", "factual"), claim("保录QS前30", "prohibited_claim")]
        )
        self.assertEqual(state.status, "conflict")
        registry = ReviewRegistry()
        registry.set(
            "rec", "output_description", "adjudicated", evidence_fingerprint(state),
            reviewer="tester", chosen_value="保录QS前30",
        )
        # Re-run through the same entry point the pipeline uses.
        from research_facts.merge import _apply_adjudication

        applied = _apply_adjudication(state, "rec", registry)
        self.assertFalse(applied, "a purely promotional side must be refused")
        self.assertEqual(state.status, "conflict")
        self.assertIn("宣传", state.note)

    def test_a_stale_adjudication_does_not_apply(self) -> None:
        record, state = self._duration()
        registry = ReviewRegistry()
        registry.set(
            record.record_key, "duration", "adjudicated",
            "a-stale-fingerprint", chosen_value="8周",
        )
        self.assertIsNone(registry.adjudication_for(record.record_key, "duration", evidence_fingerprint(state)))

    def test_an_adjudication_needs_a_chosen_value(self) -> None:
        with self.assertRaises(Exception):
            ReviewRegistry().set("k", "duration", "adjudicated", "fp")

    def test_display_value_and_comparison_key_both_resolve(self) -> None:
        # "4周+2周" is what a reviewer reads; comparison_key drops the plus.
        record, state = self._duration()
        resolved = self._adjudicate(record, state, "4周+2周").fields["duration"]
        self.assertEqual(resolved.selected_normalized_value, "4周+2周")

    def test_stats_report_the_adjudicated_count(self) -> None:
        record, state = self._duration()
        registry = ReviewRegistry()
        registry.set(
            record.record_key, "duration", "adjudicated",
            evidence_fingerprint(state), chosen_value="8周",
        )
        _, stats = build_records(self._outputs(), Settings(), registry)
        self.assertEqual(stats["adjudicated_fields"], 1)
