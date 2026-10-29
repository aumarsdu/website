"""Schema invariants, storage round-trip, adapter contracts, claim classification."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
import unittest.mock
from dataclasses import replace
from pathlib import Path

from research_facts.adapters import build_adapter, load_profile_file
from research_facts.adapters.csv_table import CsvTableAdapter, TableProfile, detect_profile
from research_facts.adapters.base import AdapterOutput, make_document
from research_facts.adapters.web_json import SOURCE_PROFILES
from research_facts.claims import classify_text, keep_factual_only
from research_facts.config import FIELD_NAMES, Settings
from research_facts.errors import InputError, SchemaValidationError
from research_facts.merge import build_records
from research_facts.schema import (
    ProjectFactRecord,
    FieldClaim,
    FieldState,
    Identity,
    Locator,
    ProjectFactRecord,
    dedupe_claims,
)
from research_facts.storage import content_digest, read_jsonl, write_jsonl
from research_facts.utils import json_path_get, redact, find_sensitive_keys

from .context import (
    HANDBOOK_JSONL,
    POSTER_JSONL,
    PROFILE_FILE,
    WEB_JSONL,
    build_settings,
    silence_logs,
)


def make_claim(field: str = "instructor", text: str = "张三", document_id: str = "d1") -> FieldClaim:
    return FieldClaim(
        field=field,
        raw_text=text,
        locator=Locator(kind="json_path", document_id=document_id, pointer="$.x"),
        extractor="json_path:$.x",
        extraction_method="json_path",
        extraction_confidence="high",
    )


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------


class TestSchemaInvariants(unittest.TestCase):
    def test_empty_statement_is_not_a_claim(self) -> None:
        with self.assertRaises(SchemaValidationError):
            make_claim(text="   ")

    def test_invalid_vocabulary_is_rejected(self) -> None:
        with self.assertRaises(SchemaValidationError):
            FieldClaim(
                field="instructor",
                raw_text="x",
                locator=Locator("json_path", "d", "$.x"),
                extractor="e",
                extraction_method="json_path",
                extraction_confidence="very-high",
            )
        with self.assertRaises(SchemaValidationError):
            FieldClaim(
                field="instructor",
                raw_text="x",
                locator=Locator("json_path", "d", "$.x"),
                extractor="e",
                extraction_method="json_path",
                extraction_confidence="high",
                evidence_kind="promotional",
            )

    def test_record_rejects_a_value_on_an_unusable_field(self) -> None:
        record = ProjectFactRecord(
            record_key="p:external_id:1",
            identity=Identity(provider="p", external_id="1", basis="external_id"),
            document_ids=["d1"],
            fields={
                "instructor": FieldState(
                    field="instructor",
                    status="conflict",
                    selected_normalized_value="张三",
                )
            },
        )
        with self.assertRaises(SchemaValidationError):
            record.validate()

    def test_record_rejects_a_missing_field_that_has_claims(self) -> None:
        record = ProjectFactRecord(
            record_key="p:external_id:1",
            identity=Identity(provider="p", external_id="1", basis="external_id"),
            fields={
                "instructor": FieldState(
                    field="instructor", status="missing", claims=[make_claim()]
                )
            },
        )
        with self.assertRaises(SchemaValidationError):
            record.validate()

    def test_record_requires_a_provider(self) -> None:
        with self.assertRaises(SchemaValidationError):
            ProjectFactRecord(record_key="k", identity=Identity(provider="")).validate()

    def test_round_trip_preserves_every_claim(self) -> None:
        record = ProjectFactRecord(
            record_key="p:external_id:1",
            identity=Identity(provider="p", external_id="1", basis="external_id"),
            document_ids=["d1"],
            fields={
                name: FieldState(field=name, status="missing")
                for name in FIELD_NAMES
            }
            | {
                "instructor": FieldState(
                    field="instructor",
                    status="resolved",
                    claims=[make_claim()],
                    selected_claim=make_claim(),
                    selected_raw_text="张三",
                    selected_normalized_value="张三",
                )
            },
        )
        restored = ProjectFactRecord.from_dict(json.loads(json.dumps(record.to_dict())))
        self.assertEqual(restored.record_key, record.record_key)
        self.assertEqual(len(restored.fields), len(FIELD_NAMES))
        self.assertEqual(restored.fields["instructor"].selected_normalized_value, "张三")
        self.assertEqual(
            restored.fields["instructor"].claims[0].locator.pointer, "$.x"
        )
        self.assertEqual(content_digest([record.to_dict()]), content_digest([restored.to_dict()]))


class TestDeduplication(unittest.TestCase):
    def test_identical_claim_from_the_same_place_is_dropped_once(self) -> None:
        claims = dedupe_claims([make_claim(), make_claim(), make_claim(text="李四")])
        self.assertEqual(len(claims), 2)

    def test_same_text_from_two_documents_is_two_claims(self) -> None:
        claims = dedupe_claims([make_claim(document_id="doc-a"), make_claim(document_id="doc-b")])
        self.assertEqual(len(claims), 2)

    def test_claim_order_does_not_change_the_deduped_result(self) -> None:
        claims = [make_claim(text="A", document_id="d1"), make_claim(text="B", document_id="d2")]
        self.assertEqual(
            [claim.raw_text for claim in dedupe_claims(claims)],
            [claim.raw_text for claim in dedupe_claims(list(reversed(claims)))],
        )


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


class TestStorage(unittest.TestCase):
    def test_jsonl_round_trip_and_digest(self) -> None:
        rows = [{"b": 1, "a": "中文"}, {"a": "x"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.jsonl"
            self.assertEqual(write_jsonl(path, rows), 2)
            self.assertEqual(list(read_jsonl(path)), rows)
        self.assertEqual(content_digest(rows), content_digest(list(rows)))

    def test_digest_changes_when_content_changes(self) -> None:
        self.assertNotEqual(
            content_digest([{"a": 1}]), content_digest([{"a": 2}])
        )

    def test_blank_lines_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.jsonl"
            path.write_text('{"a":1}\n\n{"a":2}\n', encoding="utf-8")
            self.assertEqual(len(list(read_jsonl(path))), 2)

    def test_missing_file_raises_a_classified_error(self) -> None:
        with self.assertRaises(InputError):
            list(read_jsonl(Path("/nonexistent/nope.jsonl")))

    def test_invalid_json_reports_the_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text('{"a":1}\nnot json\n', encoding="utf-8")
            with self.assertRaises(InputError) as ctx:
                list(read_jsonl(path))
            self.assertIn(":2", str(ctx.exception))

    def test_write_is_atomic_and_leaves_no_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.jsonl"
            write_jsonl(path, [{"a": 1}])
            self.assertFalse(path.with_suffix(".jsonl.tmp").exists())


class TestRedaction(unittest.TestCase):
    def test_secret_like_keys_are_masked(self) -> None:
        payload = {"token": "abc", "nested": {"api_key": "k"}, "name": "keep"}
        self.assertEqual(redact(payload), {"token": "[REDACTED]", "nested": {"api_key": "[REDACTED]"}, "name": "keep"})
        self.assertEqual(find_sensitive_keys(payload), ["api_key", "token"])


class TestJsonPath(unittest.TestCase):
    def test_supported_forms(self) -> None:
        payload = {"a": {"b": [{"c": "found"}]}, "name": "x"}
        self.assertEqual(json_path_get(payload, "$.a.b[0].c"), "found")
        self.assertEqual(json_path_get(payload, "$..c"), "found")
        self.assertEqual(json_path_get(payload, "$.a.b[9].c"), None)
        self.assertEqual(json_path_get(payload, "$.missing.path"), None)
        self.assertEqual(json_path_get(payload, "not-a-path"), None)

    def test_key_matching_ignores_case_and_underscores(self) -> None:
        self.assertEqual(json_path_get({"Start_Date": "2027-01-08"}, "$.startdate"), "2027-01-08")


# --------------------------------------------------------------------------
# Adapters
# --------------------------------------------------------------------------


class TestAdapters(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings()

    def test_source_kind_must_be_explicit_for_jsonl(self) -> None:
        with self.assertRaises(InputError):
            build_adapter(POSTER_JSONL)

    def test_explicit_kinds_resolve(self) -> None:
        self.assertEqual(build_adapter(POSTER_JSONL, source_kind="poster_ocr").source_kind, "poster_ocr")
        self.assertEqual(build_adapter(HANDBOOK_JSONL, source_kind="handbook_pdf").source_kind, "handbook_pdf")
        self.assertEqual(build_adapter(WEB_JSONL, source_kind="web_json").source_kind, "web_json")

    def test_unknown_kind_is_rejected(self) -> None:
        with self.assertRaises(InputError):
            build_adapter(WEB_JSONL, source_kind="carrier_pigeon")

    def test_poster_blocks_are_grouped_into_rows(self) -> None:
        outputs = build_adapter(POSTER_JSONL, source_kind="poster_ocr").load(POSTER_JSONL, self.settings)
        self.assertEqual(len(outputs), 2)
        first = outputs[0]
        self.assertEqual(first.document.external_id, "RS-2027-0142")
        self.assertEqual(first.document.source_authority, "supplier_marketing")
        locators = [claim.locator for claim in first.claims]
        self.assertTrue(all(locator.kind == "text_row" for locator in locators))
        start_date = next(c for c in first.claims if c.field == "start_date")
        self.assertEqual(start_date.raw_text, "2027/01/08")

    def test_handbook_pages_keep_line_locators(self) -> None:
        outputs = build_adapter(HANDBOOK_JSONL, source_kind="handbook_pdf").load(HANDBOOK_JSONL, self.settings)
        self.assertEqual(len(outputs), 3)
        self.assertEqual(outputs[0].document.meta["page_count"], 2)
        self.assertTrue(all(c.locator.kind == "text_line" for c in outputs[0].claims))
        self.assertTrue(all(c.locator.pointer.startswith("p") for c in outputs[0].claims))

    def test_web_profile_paths_control_what_is_extracted(self) -> None:
        adapter = build_adapter(WEB_JSONL, source_kind="web_json", profile="demo")
        self.assertIn("demo", SOURCE_PROFILES)
        outputs = adapter.load(WEB_JSONL, self.settings)
        first = outputs[0]
        self.assertEqual(first.document.external_id, "RS-2027-0142")
        self.assertEqual(first.document.source_kind, "web_json")
        self.assertIn("providerNote", first.unmapped_source_keys)

    def test_zhongke_profile_leaves_unconfirmed_fields_missing(self) -> None:
        # 中科 records do not carry a start date in the normalized output. The
        # profile must not invent one from another file.
        payload = {"id": "x", "title": "课题", "teacher": "某老师", "raw": {}}
        profile = SOURCE_PROFILES["zhongke"]
        self.assertEqual(set(profile.fields), {"project_title", "instructor"})

    def test_profile_file_registers_and_outranks_builtins(self) -> None:
        from research_facts.adapters.web_json import detection_order

        profile = load_profile_file(PROFILE_FILE)
        self.assertEqual(profile.name, "demo")
        self.assertEqual(profile.provider, "demo-partner")
        after = [profile.name for profile in detection_order()]
        self.assertEqual(after[0], "demo", "a supplied field table must be tried first")
        self.assertIn("sou_domestic", after)

    def test_document_requires_an_id_and_a_known_authority(self) -> None:
        with self.assertRaises(ValueError):
            make_document(document_id="", source_kind="web_json", provider="p", origin="o")
        with self.assertRaises(ValueError):
            make_document(
                document_id="d", source_kind="web_json", provider="p", origin="o", source_authority="rumour"
            )

    def test_grouping_merges_documents_that_share_an_external_id(self) -> None:
        def document(doc_id: str, external_id: str, title: str, text: str) -> AdapterOutput:
            return AdapterOutput(
                document=make_document(
                    document_id=doc_id,
                    source_kind="web_json",
                    provider="p",
                    origin=str(WEB_JSONL),
                    external_id=external_id,
                    title_hint=title,
                ),
                claims=[
                    FieldClaim(
                        field="instructor",
                        raw_text=text,
                        locator=Locator("json_path", doc_id, "$.teacher"),
                        extractor="json_path:$.teacher",
                        extraction_method="json_path",
                        extraction_confidence="high",
                    )
                ],
            )

        outputs = [
            document("web-1", "T-1", "课题一", "张三"),
            document("poster-1", "T-1", "课题一简称", "张三"),
        ]
        records, stats = build_records(outputs, self.settings)
        self.assertEqual(stats["records"], 1)
        self.assertEqual(len(records[0].document_ids), 2)
        self.assertEqual(records[0].fields["instructor"].status, "resolved")

    def test_strict_identity_keeps_unlinked_documents_apart(self) -> None:
        settings = Settings(strict_identity=True)
        outputs = [
            AdapterOutput(
                document=make_document(
                    document_id="a", source_kind="web_json", provider="p",
                    origin=str(WEB_JSONL), title_hint="课题一",
                ),
                claims=[],
            ),
            AdapterOutput(
                document=make_document(
                    document_id="b", source_kind="web_json", provider="p",
                    origin=str(WEB_JSONL), title_hint="课题一",
                ),
                claims=[],
            ),
        ]
        records, stats = build_records(outputs, settings)
        self.assertEqual(stats["records"], 2)


# --------------------------------------------------------------------------
# Marketing claims
# --------------------------------------------------------------------------


class TestClaimClassification(unittest.TestCase):
    def test_plain_statements_are_factual(self) -> None:
        for text in ("2027年1月8日", "8周", "共126课时", "项目结业证书", "示例大学"):
            self.assertEqual(classify_text(text).kind, "factual", text)

    def test_guarantees_are_prohibited(self) -> None:
        for text in ("保录QS前30", "保证发表EI会议论文", "100%保录", "稳进名校", "包过"):
            verdict = classify_text(text)
            self.assertEqual(verdict.kind, "prohibited_claim", text)
            self.assertFalse(verdict.has_factual_content, text)
            self.assertEqual(verdict.claim_type, "prohibited")
            self.assertTrue(verdict.required_disclaimer)

    def test_conditional_promises_are_flagged_but_keep_factual_content(self) -> None:
        text = "项目报告\n导师推荐信\nEI/CPCI/Scopus检索国际会议发表指导"
        verdict = classify_text(text)
        self.assertEqual(verdict.kind, "conditional_claim")
        self.assertTrue(verdict.has_factual_content)
        self.assertEqual(verdict.claim_type, "conditional")

    def test_percent_promises_are_caught(self) -> None:
        self.assertEqual(classify_text("提升 80% 录取率").kind, "prohibited_claim")

    def test_keep_factual_only_drops_the_promise(self) -> None:
        text = "仿真数据集与研究报告\n导师推荐信\n100%保录QS前50"
        kept, withheld = keep_factual_only(text)
        self.assertEqual(kept, "仿真数据集与研究报告")
        self.assertEqual(len(withheld), 2)
        self.assertTrue(all(item["kind"] != "factual" for item in withheld))

    def test_empty_text_is_not_a_fact(self) -> None:
        verdict = classify_text("")
        self.assertEqual(verdict.kind, "factual")
        self.assertFalse(verdict.has_factual_content)


class TestAcademicVocabularyIsNotMarketing(unittest.TestCase):
    """Regression set taken from a real 255-record partner export.

    Each string below was wrongly flagged by an earlier, looser phrase table.
    A marketing detector that fires on research vocabulary hides the real
    promises, so these must stay plain.
    """

    PLAIN = (
        "计算机科学专题：从“数据孤岛”到“知识涌现”——基于检索增强生成（RAG）架构的知识增强、幻觉抑制与可解释性系统设计研究",
        "动物学专题：全球变迁下的动物生存模式解析 基于动物学前沿视角洞察极端环境、人类活动对动物群落的冲击",
        "数字媒体与传播课题：解开“热搜”“爆款视频”与风险信息的传播密码——以短视频平台差异化与传播策略分析为例",
        "【全球在研】中国人民大学&比利时鲁汶大学导师 金融经济方向——医疗卫生改革下健康福利的金融经济测度与政策研究",
        "密集项目：管理学课题：创新管理与爆款策略——基于行为分析和大数据预测的营销决策与战略管理研究",
        "教育经济与公共管理：“孔乙己长衫”背后的个体与社会反思——经济转型期的教育政策、社会福利与个体自我审视",
        "人工智能（AI）｜深度学习｜计算机视觉｜医学人工智能｜多模态人工智能方向",
    )

    def test_academic_terms_are_classified_as_factual(self) -> None:
        for text in self.PLAIN:
            verdict = classify_text(text)
            self.assertEqual(verdict.kind, "factual", f"{text[:24]}… -> {verdict.phrases}")

    def test_real_promises_are_still_detected(self) -> None:
        still_flagged = (
            "优秀学员获得主导师推荐信（8封网推）",
            "EI/CPCI/Scopus检索国际会议全文投递与发表指导",
            "CNKI检索的英文普刊全文投递与发表",
            "冲击QS前30",
            "零基础也能做",
            "保录QS前30",
            "100%保录",
        )
        for text in still_flagged:
            self.assertTrue(classify_text(text).is_promotional, text)


class TestNameFieldsAreNeverNulledByMarketing(unittest.TestCase):
    """A name is a name: marketing wording must not delete a title."""

    def _claim(self, field: str, text: str):
        from research_facts.extract import make_claim

        return make_claim(
            field=field,
            raw_text=text,
            locator=Locator(kind="json_path", document_id="d1", pointer="$.x"),
            extractor="json_path:$.x",
            method="json_path",
            base_confidence="high",
        )

    def test_marketing_title_still_yields_a_value(self) -> None:
        claim = self._claim("project_title", "保录QS前30的名校冲刺科研项目")
        self.assertIsNotNone(claim)
        self.assertTrue(claim.is_promotional, "the marker must still be recorded")
        self.assertTrue(claim.has_factual_content, "but a name is still a name")

    def test_promotional_output_is_still_nulled(self) -> None:
        claim = self._claim("output_description", "保录QS前30\n保证发表EI论文")
        self.assertIsNotNone(claim)
        self.assertFalse(claim.has_factual_content)

    def test_public_projection_drops_a_field_that_is_purely_marketing(self) -> None:
        from research_facts.merge import build_records
        from research_facts.projections import build_public_rows

        records, _ = build_records(
            [
                AdapterOutput(
                    document=make_document(
                        document_id="d1",
                        source_kind="web_json",
                        provider="p",
                        origin=str(WEB_JSONL),
                        external_id="T-9",
                    ),
                    claims=[
                        FieldClaim(
                            field="duration",
                            raw_text="100%保录QS前30",
                            locator=Locator("json_path", "d1", "$.raw.cycle"),
                            extractor="json_path:$.raw.cycle",
                            extraction_method="json_path",
                            extraction_confidence="high",
                        )
                    ],
                )
            ],
            Settings(),
        )
        rows, summary = build_public_rows(records)
        self.assertNotIn("duration", rows[0]["display"])
        self.assertEqual(rows[0]["dropped_purely_promotional_fields"], ["duration"])
        self.assertIn(
            "no_purely_promotional_field_in_display",
            [gate["gate"] for gate in rows[0]["gates"]],
        )
        self.assertEqual(summary["fields_dropped_as_purely_promotional"], {"duration": 1})


class TestPipelineSettings(unittest.TestCase):
    def setUp(self) -> None:
        silence_logs()

    def test_max_records_truncates_each_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = ingest_result(build_settings(Path(tmp), max_records=1))
        poster_input = next(
            item for item in result.manifest["inputs"] if item["adapter"] == "poster_ocr"
        )
        self.assertEqual(poster_input["documents"], 1)
        self.assertEqual(poster_input["truncated_documents"], 1)

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "facts"
            result = ingest_result(build_settings(output_dir, dry_run=True))
            self.assertTrue(result.records)
            self.assertFalse(output_dir.exists(), "dry-run must not create the output directory")

    def test_one_malformed_line_does_not_discard_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.jsonl"
            broken.write_text(
                '{"id": "T-1", "name": "课题一", "raw": {"teacherName": "张三"}}\n'
                "[1, 2, 3]\n"  # not a JSON object
                '{"id": "T-2", "name": "课题二", "raw": {"teacherName": "李四"}}\n',
                encoding="utf-8",
            )
            settings = build_settings(Path(tmp) / "facts")
            settings.inputs = [f"{broken}:web_json"]
            result = ingest_result(settings)
        self.assertEqual(result.errors, {"parse_error": 1})
        self.assertEqual(len(result.records), 2, "the two good lines must survive")

    def test_a_missing_input_is_counted_as_an_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = build_settings(Path(tmp) / "facts")
            settings.inputs = [f"{Path(tmp) / 'nope.jsonl'}:web_json"]
            result = ingest_result(settings)
        self.assertEqual(result.errors, {"input_error": 1})
        self.assertEqual(result.records, [])

    def test_source_kind_suffix_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = build_settings(Path(tmp) / "facts")
            settings.inputs = [str(WEB_JSONL)]
            result = ingest_result(settings)
        self.assertEqual(result.errors, {"input_error": 1})


class TestCommandLine(unittest.TestCase):
    """Every subcommand must run, not just import."""

    def setUp(self) -> None:
        silence_logs()
        # main() calls configure_logging, which would attach a stderr handler
        # and print every event into the middle of the test report.
        patcher = unittest.mock.patch("research_facts.cli.configure_logging")
        patcher.start()
        self.addCleanup(patcher.stop)
        self._tmp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self._tmp.name) / "facts"

    def tearDown(self) -> None:
        silence_logs()
        self._tmp.cleanup()

    def test_ingest_dry_run_prints_a_preview(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as out:
            code = main(
                [
                    "ingest",
                    "--dry-run",
                    "--output-dir",
                    str(self.output_dir),
                    "--profile-file",
                    str(PROFILE_FILE),
                    "--input",
                    f"{WEB_JSONL}:web_json",
                    "--input",
                    f"{POSTER_JSONL}:poster_ocr",
                    "--input",
                    f"{HANDBOOK_JSONL}:handbook_pdf",
                ]
            )
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["preview"]["records"], 4)
        self.assertEqual([item["label"] for item in payload["expected_fields"]][0], "课题名")
        self.assertEqual(len(payload["inputs"]), 3)
        self.assertFalse(self.output_dir.exists(), "dry-run must not write")

    def test_ingest_then_report_validate_and_field(self) -> None:
        from research_facts.cli import main

        common = [
            "--output-dir",
            str(self.output_dir),
            "--profile-file",
            str(PROFILE_FILE),
            "--input",
            f"{WEB_JSONL}:web_json",
            "--input",
            f"{POSTER_JSONL}:poster_ocr",
            "--input",
            f"{HANDBOOK_JSONL}:handbook_pdf",
        ]
        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as ingest_out:
            self.assertEqual(main(["ingest", *common]), 0)
        self.assertIn("内容摘要", ingest_out.getvalue())

        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as report_out:
            self.assertEqual(main(["report", "--output-dir", str(self.output_dir)]), 0)
        self.assertIn("冲突报告", report_out.getvalue())

        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as validate_out:
            self.assertEqual(main(["validate", "--output-dir", str(self.output_dir)]), 0)
        self.assertIn("全部记录符合规范字段结构", validate_out.getvalue())

        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as field_out:
            code = main(
                [
                    "field",
                    "--output-dir",
                    str(self.output_dir),
                    "--record",
                    "demo-partner:external_id:RS_2027_0142",
                    "--field",
                    "duration",
                ]
            )
        self.assertEqual(code, 0)
        text = field_out.getvalue()
        self.assertIn("状态      : conflict", text)
        self.assertIn("$.raw.cycle", text)

    def test_profiles_lists_the_builtin_field_tables(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as out:
            self.assertEqual(main(["profiles"]), 0)
        body = out.getvalue().split("适配器:")[0]
        names = {item["name"] for item in json.loads(body)}
        self.assertTrue({"sou_domestic", "zhongke", "generic"} <= names)

    def test_unknown_profile_is_rejected_before_any_work(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stderr", new=io.StringIO()) as err:
            code = main(["ingest", "--profile", "does-not-exist", "--input", str(WEB_JSONL)])
        self.assertEqual(code, 2)
        self.assertIn("未知 profile", err.getvalue())

    def test_field_command_reports_an_unknown_record(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stdout", new=io.StringIO()):
            main(
                [
                    "ingest",
                    "--output-dir",
                    str(self.output_dir),
                    "--profile-file",
                    str(PROFILE_FILE),
                    "--input",
                    f"{WEB_JSONL}:web_json",
                ]
            )
        with unittest.mock.patch("sys.stderr", new=io.StringIO()) as err:
            code = main(
                [
                    "field",
                    "--output-dir",
                    str(self.output_dir),
                    "--record",
                    "nope",
                    "--field",
                    "duration",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("未找到记录", err.getvalue())


    def test_review_then_export_makes_a_field_public(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stdout", new=io.StringIO()):
            main(
                [
                    "ingest",
                    "--output-dir",
                    str(self.output_dir),
                    "--profile-file",
                    str(PROFILE_FILE),
                    "--input",
                    f"{WEB_JSONL}:web_json",
                ]
            )
        # The web-only fixture has no conflict, so approving both high-risk
        # fields should clear every evaluable gate.
        record = "demo-partner:external_id:RS_2027_0311"
        for field in ("instructor", "output_description"):
            with unittest.mock.patch("sys.stdout", new=io.StringIO()) as out:
                code = main(
                    [
                        "review",
                        "--output-dir",
                        str(self.output_dir),
                        "--record",
                        record,
                        "--field",
                        field,
                        "--approve",
                        "--reviewer",
                        "tester",
                        "--note",
                        "已核对",
                    ]
                )
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("指纹", out.getvalue())

        review_file = self.output_dir / "reviews.json"
        self.assertTrue(review_file.exists())
        payload = json.loads(review_file.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["decisions"]), 2)
        self.assertEqual({item["reviewer"] for item in payload["decisions"]}, {"tester"})

        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as out:
            self.assertEqual(
                main(["review", "--output-dir", str(self.output_dir), "--list"]), 0
            )
        self.assertIn("approved", out.getvalue())

        # Re-ingest applies the decisions to the public projection.
        with unittest.mock.patch("sys.stdout", new=io.StringIO()):
            main(
                [
                    "ingest",
                    "--output-dir",
                    str(self.output_dir),
                    "--profile-file",
                    str(PROFILE_FILE),
                    "--input",
                    f"{WEB_JSONL}:web_json",
                ]
            )
        rows = [
            json.loads(line)
            for line in (self.output_dir / "facts.public.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        row = next(item for item in rows if item["record_key"] == record)
        self.assertEqual(row["review_queue"], [])
        self.assertEqual(row["display"]["instructor"]["verification_status"], "reviewed")
        self.assertTrue(row["publishable"], [g for g in row["gates"] if not g["passed"] and g["evaluated"]])

        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as out:
            self.assertEqual(
                main(
                    [
                        "export",
                        "--output-dir",
                        str(self.output_dir),
                        "--record",
                        record,
                        "--public",
                    ]
                ),
                0,
            )
        text = out.getvalue()
        self.assertIn("可对外：是", text)
        self.assertNotIn("待人工审核", text)

    def test_review_refuses_fields_with_nothing_to_approve(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stdout", new=io.StringIO()):
            main(
                [
                    "ingest",
                    "--output-dir",
                    str(self.output_dir),
                    "--profile-file",
                    str(PROFILE_FILE),
                    "--input",
                    f"{HANDBOOK_JSONL}:handbook_pdf",
                ]
            )
        # The synthetic handbook-only record has no instructor at all.
        with unittest.mock.patch("sys.stderr", new=io.StringIO()) as err:
            code = main(
                [
                    "review",
                    "--output-dir",
                    str(self.output_dir),
                    "--record",
                    "demo-partner:title",
                    "--field",
                    "instructor",
                    "--approve",
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("没有可审核的取值", err.getvalue())
        self.assertFalse((self.output_dir / "reviews.json").exists())

    def test_review_requires_a_decision_flag(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stdout", new=io.StringIO()):
            main(
                [
                    "ingest",
                    "--output-dir",
                    str(self.output_dir),
                    "--profile-file",
                    str(PROFILE_FILE),
                    "--input",
                    f"{WEB_JSONL}:web_json",
                ]
            )
        with unittest.mock.patch("sys.stderr", new=io.StringIO()) as err:
            code = main(
                [
                    "review",
                    "--output-dir",
                    str(self.output_dir),
                    "--record",
                    "demo-partner:external_id:RS_2027_0311",
                    "--field",
                    "instructor",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("--approve", err.getvalue())

    def test_export_writes_a_file_and_json(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stdout", new=io.StringIO()):
            main(
                [
                    "ingest",
                    "--output-dir",
                    str(self.output_dir),
                    "--profile-file",
                    str(PROFILE_FILE),
                    "--input",
                    f"{WEB_JSONL}:web_json",
                ]
            )
        target = Path(self._tmp.name) / "cards.md"
        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as out:
            code = main(["export", "--output-dir", str(self.output_dir), "--out", str(target)])
        self.assertEqual(code, 0)
        text = target.read_text(encoding="utf-8")
        self.assertIn("内部导出", text)
        self.assertIn("证据来源", text)

        with unittest.mock.patch("sys.stdout", new=io.StringIO()) as out:
            self.assertEqual(
                main(["export", "--output-dir", str(self.output_dir), "--format", "json"]), 0
            )
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["mode"], "internal")
        self.assertEqual(len(payload["records"]), 3)

    def test_export_reports_an_unknown_record(self) -> None:
        from research_facts.cli import main

        with unittest.mock.patch("sys.stdout", new=io.StringIO()):
            main(
                [
                    "ingest",
                    "--output-dir",
                    str(self.output_dir),
                    "--profile-file",
                    str(PROFILE_FILE),
                    "--input",
                    f"{WEB_JSONL}:web_json",
                ]
            )
        with unittest.mock.patch("sys.stderr", new=io.StringIO()) as err:
            code = main(
                ["export", "--output-dir", str(self.output_dir), "--record", "nope"]
            )
        self.assertEqual(code, 2)
        self.assertIn("未找到记录", err.getvalue())


def ingest_result(settings: Settings):
    from research_facts.pipeline import ingest

    return ingest(settings)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestTypedValueGate(unittest.TestCase):
    """A value that cannot be the field's type is refused, not accepted."""

    def test_refuses_a_header_cell_as_a_typed_value(self) -> None:
        from research_facts.extract import make_claim
        from research_facts.schema import RejectedCandidate

        rejected: list[RejectedCandidate] = []
        claim = make_claim(
            field="duration",
            raw_text="开班人数",
            locator=Locator("text_row", "d1", "row3"),
            extractor="label:项目周期",
            method="label",
            base_confidence="medium",
            rejected=rejected,
        )
        self.assertIsNone(claim)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].reason, "value_does_not_fit_field_type")
        self.assertEqual(rejected[0].candidate_text, "开班人数")

    def test_a_real_value_still_passes(self) -> None:
        from research_facts.extract import make_claim
        from research_facts.schema import RejectedCandidate

        rejected: list[RejectedCandidate] = []
        claim = make_claim(
            field="start_date",
            raw_text="2026年09月19日",
            locator=Locator("text_row", "d1", "row3"),
            extractor="label:开课时间",
            method="label",
            base_confidence="medium",
            rejected=rejected,
        )
        self.assertIsNotNone(claim)
        self.assertEqual(claim.normalized_value, "2026-09-19")
        self.assertEqual(rejected, [])

    def test_untyped_fields_are_not_gated(self) -> None:
        from research_facts.extract import make_claim

        claim = make_claim(
            field="instructor",
            raw_text="示例导师甲",
            locator=Locator("text_row", "d1", "row3"),
            extractor="label:授课教授",
            method="label",
            base_confidence="medium",
        )
        self.assertIsNotNone(claim)

    def test_rejections_are_reported_not_dropped(self) -> None:
        from research_facts.pipeline import ingest

        with tempfile.TemporaryDirectory() as tmp:
            result = ingest_result(build_settings(Path(tmp)))
        rows = result.rejected
        self.assertIsInstance(rows, list)
        # The synthetic fixture has no header-cell rows, so it should be clean.
        self.assertEqual(rows, [])

    def test_rejected_report_is_sorted_and_serialisable(self) -> None:
        from research_facts.reports import build_rejected_report

        rows = build_rejected_report([])
        self.assertEqual(rows, [])
        json.dumps(rows)


class TestCsvTableAdapter(unittest.TestCase):
    """A schedule table is an independent source, not a page payload.

    Real data proved the point: HIREP's table grain is
    ``(课题ID, 产品包ID)`` -- three product packages per topic, three different
    start dates. Keying on 课题ID alone produced 322 false conflicts, so the
    profile declares a composite key.
    """

    def setUp(self) -> None:
        self.settings = Settings()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.csv_path = self.dir / "schedule.csv"
        self.addCleanup(self.tmp.cleanup)

    def _write(self, rows: list[dict], fields: list[str]) -> None:
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _profile(self, **overrides):
        payload = {
            "kind": "csv",
            "name": "t",
            "provider": "p",
            "id_column": "课题ID",
            "title_column": "课题名称",
            "fields": {"project_title": ["课题名称"], "start_date": ["开课日期"]},
            "basis_columns": {"start_date": ["开课日期依据"]},
        }
        payload.update(overrides)
        return TableProfile.from_dict(payload)

    def test_one_row_becomes_one_document(self) -> None:
        self._write(
            [{"课题ID": "A1", "课题名称": "课题一", "开课日期": "2027-03-02", "开课日期依据": "公开列表"}],
            ["课题ID", "课题名称", "开课日期", "开课日期依据"],
        )
        outputs = CsvTableAdapter(self._profile()).load(self.csv_path, self.settings)
        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0].document.external_id, "A1")
        self.assertEqual(outputs[0].document.source_kind, "table_csv")
        fields = {claim.field: claim for claim in outputs[0].claims}
        self.assertEqual(fields["project_title"].raw_text, "课题一")
        self.assertEqual(fields["start_date"].normalized_value, "2027-03-02")

    def test_basis_column_becomes_evidence_not_a_value(self) -> None:
        self._write(
            [{"课题ID": "A1", "课题名称": "课题一", "开课日期": "2027-03-02", "开课日期依据": "firstCourseBeginTime"}],
            ["课题ID", "课题名称", "开课日期", "开课日期依据"],
        )
        outputs = CsvTableAdapter(self._profile()).load(self.csv_path, self.settings)
        claim = next(c for c in outputs[0].claims if c.field == "start_date")
        self.assertIn("basis=firstCourseBeginTime", claim.locator.detail)
        self.assertNotIn("firstCourseBeginTime", claim.raw_text)
        self.assertNotIn("firstCourseBeginTime", claim.normalized_value or "")

    def test_composite_key_separates_offerings(self) -> None:
        self._write(
            [
                {"课题ID": "A1", "产品包ID": "P1", "课题名称": "课题一", "开课日期": "2026-09-07"},
                {"课题ID": "A1", "产品包ID": "P2", "课题名称": "课题一", "开课日期": "2026-10-17"},
            ],
            ["课题ID", "产品包ID", "课题名称", "开课日期"],
        )
        profile = self._profile(id_columns=["产品包ID"])
        outputs = CsvTableAdapter(profile).load(self.csv_path, self.settings)
        self.assertEqual([o.document.external_id for o in outputs], ["A1#P1", "A1#P2"])
        records, stats = build_records(outputs, self.settings)
        self.assertEqual(stats["records"], 2, "different cohorts are different records")

    def test_column_matching_tolerates_spacing_and_bom(self) -> None:
        self._write([{"课题 ID": "A1", "课题 名称": "课题一", "开课 日期": "2027-03-02"}],
                    ["课题 ID", "课题 名称", "开课 日期"])
        profile = TableProfile.from_dict(
            {"kind": "csv", "name": "t", "provider": "p", "id_column": "课题ID",
             "title_column": "课题名称", "fields": {"start_date": ["开课日期"]}}
        )
        outputs = CsvTableAdapter(profile).load(self.csv_path, self.settings)
        self.assertEqual(len(outputs[0].claims), 1)
        self.assertEqual(outputs[0].claims[0].normalized_value, "2027-03-02")

    def test_a_non_date_value_is_refused_not_written(self) -> None:
        self._write([{"课题ID": "A1", "课题名称": "课题一", "开课日期": "待定"}],
                    ["课题ID", "课题名称", "开课日期"])
        outputs = CsvTableAdapter(self._profile()).load(self.csv_path, self.settings)
        self.assertNotIn("start_date", {c.field for c in outputs[0].claims})
        self.assertTrue(outputs[0].rejected)
        self.assertEqual(outputs[0].rejected[0].reason, "value_does_not_fit_field_type")

    def test_profile_is_matched_against_the_real_header(self) -> None:
        self._write([{"课题ID": "A1", "课题名称": "课题一", "开课日期": "2027-03-02"}],
                    ["课题ID", "课题名称", "开课日期"])
        self.assertIsNotNone(detect_profile(self.csv_path, {"t": self._profile()}))
        self._write([{"课程号": "A1", "标题": "课题一"}], ["课程号", "标题"])
        self.assertIsNone(detect_profile(self.csv_path, {"t": self._profile()}),
                          "a table that shares no column must not be claimed")

    def test_a_table_and_a_page_conflict_rather_than_overwrite(self) -> None:
        self._write([{"课题ID": "A1", "课题名称": "课题一", "开课日期": "2027-03-02"}],
                    ["课题ID", "课题名称", "开课日期"])
        csv_outputs = CsvTableAdapter(self._profile()).load(self.csv_path, self.settings)
        web_outputs = [
            AdapterOutput(
                document=make_document(
                    document_id="p#A1", source_kind="web_json", provider="p",
                    origin="mem", external_id="A1",
                ),
                claims=[FieldClaim(
                    field="start_date", raw_text="2027-03-16",
                    locator=Locator("json_path", "p#A1", "$.startDate"),
                    extractor="json_path:$.startDate", extraction_method="json_path",
                    extraction_confidence="high",
                )],
            )
        ]
        records, _ = build_records([*csv_outputs, *web_outputs], self.settings)
        self.assertEqual(len(records), 1, "same provider + id groups across sources")
        state = records[0].fields["start_date"]
        self.assertEqual(state.status, "conflict")
        self.assertIsNone(state.selected_normalized_value)
        self.assertEqual(len(state.claims), 2)


class TestDuplicateCandidates(unittest.TestCase):
    """Design doc 4.7: candidates only, never an automatic merge."""

    def _record(self, key: str, provider: str, external_id: str, title: str, teacher: str = "张三"):
        from research_facts.schema import FieldState, Identity

        fields = {name: FieldState(field=name, status="missing") for name in FIELD_NAMES}
        fields["project_title"] = FieldState(
            field="project_title", status="resolved",
            selected_raw_text=title, selected_normalized_value=title,
        )
        if teacher:
            fields["instructor"] = FieldState(
                field="instructor", status="resolved",
                selected_raw_text=teacher, selected_normalized_value=teacher,
            )
        return ProjectFactRecord(
            record_key=key,
            identity=Identity(provider=provider, external_id=external_id, basis="external_id"),
            fields=fields,
        )

    def test_a_cross_provider_match_becomes_a_candidate(self) -> None:
        from research_facts.dedup import find_candidates

        records = [
            self._record("a:1", "alpha", "1", "城市噪声地图与公共卫生研究"),
            self._record("b:1", "beta", "9", "城市噪声地图与公共卫生研究"),
        ]
        found = find_candidates(records)
        self.assertEqual(len(found), 1)
        # title 0.35 + instructor 0.25; different providers add nothing.
        self.assertAlmostEqual(found[0].score, 0.60, places=2)
        self.assertFalse(found[0].signals["same_provider"])
        self.assertEqual(found[0].left, "a:1")
        self.assertEqual(found[0].right, "b:1")

    def test_candidates_are_never_merged(self) -> None:
        from research_facts.dedup import build_duplicate_report

        records = [
            self._record("a:1", "alpha", "1", "同一课题名称", "同一位导师"),
            self._record("b:1", "beta", "2", "同一课题名称", "同一位导师"),
        ]
        report = build_duplicate_report(records)
        self.assertEqual(report["candidate_count"], 1)
        self.assertTrue(all(not c["merged"] for c in report["candidates"]))
        self.assertEqual(report["candidates"][0]["resolution"], "manual_review_required")

    def test_pairs_are_reported_in_canonical_order_only_once(self) -> None:
        from research_facts.dedup import find_candidates

        records = [
            self._record("z:1", "alpha", "1", "重复的课题标题"),
            self._record("a:1", "beta", "2", "重复的课题标题"),
        ]
        found = find_candidates(records)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0].left, found[0].right), ("a:1", "z:1"))

    def test_unrelated_titles_are_not_candidates(self) -> None:
        from research_facts.dedup import find_candidates

        records = [
            self._record("a:1", "alpha", "1", "遥感无人机与灾害应急"),
            self._record("b:1", "beta", "2", "中世纪欧洲贸易史"),
        ]
        self.assertEqual(find_candidates(records), [])

    def test_a_record_without_a_title_is_never_a_candidate(self) -> None:
        from research_facts.dedup import find_candidates

        records = [
            self._record("a:1", "alpha", "1", ""),
            self._record("b:1", "beta", "2", "某个课题"),
        ]
        self.assertEqual(find_candidates(records), [])

    def test_the_report_states_which_signals_are_unavailable(self) -> None:
        from research_facts.dedup import build_duplicate_report

        report = build_duplicate_report([self._record("a:1", "alpha", "1", "课题")])
        self.assertIn("institution_similarity", report["unavailable_signals"])
        self.assertIn("same_taxonomy", report["unavailable_signals"])
        self.assertLess(report["max_reachable_score"], 1.0)
        self.assertIn("不会自动合并", report["limits"])

    def test_same_provider_and_same_id_scores_highest(self) -> None:
        from research_facts.dedup import find_candidates

        records = [
            self._record("a:1", "alpha", "7", "完全相同的课题名称", "同一位导师"),
            self._record("a:2", "alpha", "7", "完全相同的课题名称", "同一位导师"),
        ]
        found = find_candidates(records)
        self.assertAlmostEqual(found[0].score, 0.95, places=2)


class TestIdentityMerge(unittest.TestCase):
    """A merge destroys an identity, so it is only ever a written decision."""

    def setUp(self) -> None:
        from research_facts.adapters import build_adapter

        self.settings = Settings()
        self.outputs = []
        for path, kind in (
            (WEB_JSONL, "web_json"),
            (POSTER_JSONL, "poster_ocr"),
            (HANDBOOK_JSONL, "handbook_pdf"),
        ):
            self.outputs.extend(build_adapter(path, source_kind=kind).load(path, self.settings))

    def _decision(self, left: str, right: str, reviewer: str = "tester"):
        from research_facts.merging import MergeDecision, MergeRegistry, fingerprint_of_claims

        base, _ = build_records(self.outputs, self.settings)
        by_key = {record.record_key: record for record in base}
        claims = [
            claim
            for key in (left, right)
            for state in by_key[key].fields.values()
            for claim in state.claims
        ]
        registry = MergeRegistry()
        registry.add(
            MergeDecision(
                left=left,
                right=right,
                fingerprint=fingerprint_of_claims(claims),
                reviewer=reviewer,
                note="测试",
            )
        )
        return registry

    def _twin_outputs(self):
        """Two documents that would stay separate but say exactly the same thing."""
        from research_facts.adapters.base import AdapterOutput, make_document

        def output(doc_id: str, external_id: str) -> AdapterOutput:
            claims = [
                FieldClaim(
                    field="project_title",
                    raw_text="城市噪声地图与公共卫生",
                    locator=Locator("json_path", doc_id, "$.name"),
                    extractor="json_path:$.name",
                    extraction_method="json_path",
                    extraction_confidence="high",
                    normalized_value="城市噪声地图与公共卫生",
                    normalization={"compare_key": "城市噪声地图与公共卫生"},
                ),
                FieldClaim(
                    field="start_date",
                    raw_text="2027-03-02",
                    locator=Locator("json_path", doc_id, "$.start"),
                    extractor="json_path:$.start",
                    extraction_method="json_path",
                    extraction_confidence="high",
                    normalized_value="2027-03-02",
                    normalization={"compare_key": "20270302"},
                ),
            ]
            return AdapterOutput(
                document=make_document(
                    document_id=doc_id,
                    source_kind="web_json",
                    provider="p",
                    origin="mem",
                    external_id=external_id,
                ),
                claims=claims,
            )

        return [output("p#A", "A"), output("p#B", "B")]

    def test_a_merged_pair_becomes_one_record_with_both_documents(self) -> None:
        from research_facts.merging import MergeDecision, MergeRegistry, fingerprint_of_claims

        outputs = self._twin_outputs()
        separate, _ = build_records(outputs, self.settings)
        self.assertEqual(len(separate), 2, "two ids are two records before the decision")

        claims = [claim for output in outputs for claim in output.claims]
        registry = MergeRegistry()
        registry.add(
            MergeDecision(
                left=separate[0].record_key,
                right=separate[1].record_key,
                fingerprint=fingerprint_of_claims(claims),
                reviewer="tester",
                note="两个 id 内容完全相同",
            )
        )
        merged, stats = build_records(outputs, self.settings, None, registry)
        self.assertEqual(len(registry.applied), 1)
        self.assertEqual(len(merged), 1)
        self.assertEqual(sorted(merged[0].document_ids), ["p#A", "p#B"])
        self.assertEqual(stats["merged_records"], 1)
        self.assertEqual(merged[0].fields["start_date"].selected_normalized_value, "2027-03-02")
        self.assertTrue(
            any(issue.get("type") == "identity_merged" for issue in merged[0].issues)
        )

    def test_merged_sides_that_disagree_stay_a_conflict(self) -> None:
        # Deciding two records are the same entity says nothing about whether
        # their facts agree. The disagreement must survive the merge.
        from research_facts.merging import MergeDecision, MergeRegistry, fingerprint_of_claims

        outputs = self._twin_outputs()
        outputs[1].claims[1] = replace(
            outputs[1].claims[1],
            raw_text="2027-04-10",
            normalized_value="2027-04-10",
            normalization={"compare_key": "20270410"},
        )
        separate, _ = build_records(outputs, self.settings)
        claims = [claim for output in outputs for claim in output.claims]
        registry = MergeRegistry()
        registry.add(
            MergeDecision(
                left=separate[0].record_key,
                right=separate[1].record_key,
                fingerprint=fingerprint_of_claims(claims),
                reviewer="tester",
            )
        )
        merged, _ = build_records(outputs, self.settings, None, registry)
        self.assertEqual(len(registry.applied), 1)
        state = merged[0].fields["start_date"]
        self.assertEqual(state.status, "conflict")
        self.assertIsNone(state.selected_normalized_value)
        self.assertEqual(len(state.claims), 2)

    def test_an_unnamed_proposal_does_not_apply(self) -> None:
        from research_facts.merging import MergeRegistry

        base, _ = build_records(self.outputs, self.settings)
        first = base[0].record_key
        registry = self._decision(first, base[1].record_key, reviewer="")
        records, _ = build_records(self.outputs, self.settings, None, registry)
        self.assertEqual(len(records), len(base))
        self.assertEqual(registry.skipped[0]["reason"], "awaiting_reviewer")

    def test_a_stale_decision_does_not_apply(self) -> None:
        from research_facts.merging import MergeDecision, MergeRegistry

        base, _ = build_records(self.outputs, self.settings)
        registry = MergeRegistry()
        registry.add(
            MergeDecision(
                left=base[0].record_key,
                right=base[1].record_key,
                fingerprint="an-old-fingerprint",
                reviewer="tester",
            )
        )
        records, _ = build_records(self.outputs, self.settings, None, registry)
        self.assertEqual(len(records), len(base))
        self.assertEqual(registry.skipped[0]["reason"], "evidence_changed_since_decision")

    def test_a_decision_for_a_missing_side_is_skipped(self) -> None:
        from research_facts.merging import MergeDecision, MergeRegistry

        base, _ = build_records(self.outputs, self.settings)
        registry = MergeRegistry()
        registry.add(
            MergeDecision(
                left=base[0].record_key,
                right="p:external_id:not-here",
                fingerprint="fp",
                reviewer="tester",
            )
        )
        records, _ = build_records(self.outputs, self.settings, None, registry)
        self.assertEqual(len(records), len(base))
        self.assertEqual(registry.skipped[0]["reason"], "one_side_absent")

    def test_a_merge_needs_two_different_identities(self) -> None:
        from research_facts.merging import MergeDecision

        with self.assertRaises(Exception):
            MergeDecision(left="a", right="a", fingerprint="fp")
        with self.assertRaises(Exception):
            MergeDecision(left="a", right="b", fingerprint="")


class TestMergeabilityClassification(unittest.TestCase):
    """Agreement on the comparable fields is the gate for a merge proposal."""

    def _pair(self):
        from research_facts.dedup import build_duplicate_report

        return build_duplicate_report

    def test_candidates_report_says_how_many_are_mergeable(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        from research_facts.dedup import build_duplicate_report
        from research_facts.pipeline import ingest

        with tempfile.TemporaryDirectory() as tmp:
            result = ingest(
                build_settings(
                    Path(tmp),
                    inputs=[
                        f"{WEB_JSONL}:web_json",
                        f"{POSTER_JSONL}:poster_ocr",
                        f"{HANDBOOK_JSONL}:handbook_pdf",
                    ],
                )
            )
        report = build_duplicate_report(result.records)
        self.assertIn("mergeable_count", report)
        self.assertEqual(
            report["mergeable_count"] + report["diverging_count"],
            report["candidate_count"],
        )
        for candidate in report["candidates"]:
            if candidate["diverging_fields"]:
                self.assertFalse(candidate["is_mergeable"])
                self.assertIn("start_date", candidate["diverging_fields"])


class TestCohortGroups(unittest.TestCase):
    """Same topic across runs: grouped for visibility, never merged."""

    def _records(self, dates):
        from research_facts.schema import FieldState, Identity

        out = []
        for index, date in enumerate(dates):
            fields = {name: FieldState(field=name, status="missing") for name in FIELD_NAMES}
            fields["project_title"] = FieldState(
                field="project_title", status="resolved",
                selected_raw_text="城市噪声地图与公共卫生", selected_normalized_value="城市噪声地图与公共卫生",
            )
            fields["start_date"] = FieldState(
                field="start_date", status="resolved",
                selected_raw_text=date, selected_normalized_value=date,
            )
            out.append(
                ProjectFactRecord(
                    record_key=f"p:external_id:T{index}",
                    identity=Identity(provider="p", external_id=f"T{index}", basis="external_id"),
                    fields=fields,
                )
            )
        return out

    def test_runs_of_one_topic_are_grouped(self) -> None:
        from research_facts.dedup import build_cohort_report

        report = build_cohort_report(self._records(["2026-11-06", "2027-01-15", "2027-02-26"]))
        self.assertEqual(report["topic_groups"], 1)
        group = report["groups"][0]
        self.assertEqual(group["run_count"], 3)
        self.assertEqual(group["distinct_dates"], 3)
        self.assertEqual(group["resolution"], "keep_separate")
        self.assertEqual(
            [run["start_date"] for run in group["runs"]],
            ["2026-11-06", "2027-01-15", "2027-02-26"],
        )

    def test_a_single_run_is_not_a_group(self) -> None:
        from research_facts.dedup import build_cohort_report

        self.assertEqual(build_cohort_report(self._records(["2027-03-02"]))["topic_groups"], 0)

    def test_the_same_title_in_two_providers_stays_separate(self) -> None:
        from research_facts.dedup import build_cohort_report
        from research_facts.schema import FieldState, Identity

        records = self._records(["2027-01-01"])
        twin = records[0]
        other = ProjectFactRecord(
            record_key="q:external_id:T0",
            identity=Identity(provider="q", external_id="T0", basis="external_id"),
            fields={name: FieldState(field=name, status="missing") for name in FIELD_NAMES}
            | {
                "project_title": FieldState(
                    field="project_title", status="resolved",
                    selected_raw_text="城市噪声地图与公共卫生",
                    selected_normalized_value="城市噪声地图与公共卫生",
                )
            },
        )
        self.assertEqual(build_cohort_report([*records, other])["topic_groups"], 0)

    def test_records_without_a_title_are_ignored(self) -> None:
        from research_facts.dedup import build_cohort_report
        from research_facts.schema import FieldState, Identity

        blanks = [
            ProjectFactRecord(
                record_key=f"p:external_id:B{index}",
                identity=Identity(provider="p", external_id=f"B{index}", basis="external_id"),
                fields={name: FieldState(field=name, status="missing") for name in FIELD_NAMES},
            )
            for index in range(3)
        ]
        self.assertEqual(build_cohort_report(blanks)["topic_groups"], 0)


class TestWiringCheck(unittest.TestCase):
    def test_a_mapped_source_is_reported_as_mappable(self) -> None:
        from research_facts.wiring import build_wiring_report

        outputs, records = [], []
        with tempfile.TemporaryDirectory() as tmp:
            from research_facts.pipeline import ingest

            result = ingest(build_settings(Path(tmp), max_records=3))
            outputs = result.__dict__.get("_outputs") or []
        # Reuse the pipeline's own result to build the report.
        with tempfile.TemporaryDirectory() as tmp:
            from research_facts.adapters import build_adapter
            from research_facts.config import Settings

            settings = Settings()
            loaded = []
            for path, kind in (
                (WEB_JSONL, "web_json"),
                (POSTER_JSONL, "poster_ocr"),
                (HANDBOOK_JSONL, "handbook_pdf"),
            ):
                loaded.extend(build_adapter(path, source_kind=kind).load(path, settings))
            from research_facts.merge import build_records

            recs, _ = build_records(loaded, settings)
        report = build_wiring_report(loaded, recs, [])
        self.assertTrue(report["verdict"].startswith("mappable"))
        self.assertEqual(report["records"], 4)
        self.assertIn("project_title", report["field_coverage"])
        self.assertIn("unmapped_source_keys", report)

    def test_an_unreadable_source_says_so(self) -> None:
        from research_facts.wiring import build_wiring_report

        report = build_wiring_report([], [], [], {"input_error": 1})
        self.assertEqual(report["verdict"], "unusable：输入无法读取，先修输入")

    def test_an_empty_mapping_is_called_unmappable(self) -> None:
        from research_facts.wiring import build_wiring_report
        from research_facts.schema import FieldState, ProjectFactRecord

        blank = ProjectFactRecord(
            record_key="p:external_id:X",
            identity=Identity(provider="p", external_id="X", basis="external_id"),
            fields={name: FieldState(field=name, status="missing") for name in FIELD_NAMES},
        )
        report = build_wiring_report([], [blank], [])
        self.assertTrue(report["verdict"].startswith("unmappable"))
        self.assertEqual(len(report["fields_that_stay_empty"]), 6)

    def test_a_partially_mapped_source_is_called_out(self) -> None:
        from research_facts.wiring import build_wiring_report
        from research_facts.schema import FieldState, Identity, ProjectFactRecord

        fields = {name: FieldState(field=name, status="missing") for name in FIELD_NAMES}
        fields["project_title"] = FieldState(
            field="project_title", status="resolved",
            selected_raw_text="课题", selected_normalized_value="课题",
        )
        record = ProjectFactRecord(
            record_key="p:external_id:X",
            identity=Identity(provider="p", external_id="X", basis="external_id"),
            fields=fields,
        )
        report = build_wiring_report([], [record], [])
        self.assertTrue(report["verdict"].startswith("partially_mappable"))


class TestUnmappedColumnPunchList(unittest.TestCase):
    """A fifteen-column sheet mapped on three must say what the other twelve are."""

    def _csv(self, tmp: Path, header: list[str], row: dict) -> Path:
        import csv as _csv

        path = tmp / "s.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = _csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()
            writer.writerow(row)
        return path

    def test_csv_reports_unconsumed_columns(self) -> None:
        from research_facts.adapters.csv_table import CsvTableAdapter, TableProfile

        with tempfile.TemporaryDirectory() as tmp:
            header = ["课题ID", "课题名称", "开课日期", "首课时间", "授课教授", "开班人数"]
            path = self._csv(
                Path(tmp), header,
                {"课题ID": "A", "课题名称": "课题一", "开课日期": "2027-03-02",
                 "首课时间": "2027-03-02", "授课教授": "张三", "开班人数": "30"},
            )
            profile = TableProfile.from_dict(
                {"kind": "csv", "name": "t", "provider": "p",
                 "id_column": "课题ID", "title_column": "课题名称",
                 "fields": {"project_title": ["课题名称"], "instructor": ["授课教授"],
                            "start_date": ["开课日期"]}}
            )
            outputs = CsvTableAdapter(profile).load(path, Settings())
        self.assertEqual(
            sorted(outputs[0].unmapped_source_keys), ["开班人数", "首课时间"]
        )

    def test_a_column_that_looks_like_a_field_is_asked_about(self) -> None:
        from research_facts.wiring import build_wiring_report
        from research_facts.adapters.base import AdapterOutput, make_document
        from research_facts.merge import build_records

        outputs = [
            AdapterOutput(
                document=make_document(
                    document_id="p#A", source_kind="table_csv", provider="p",
                    origin="mem", external_id="A",
                ),
                claims=[],
                unmapped_source_keys=["首课时间", "开班人数", "产品包ID"],
            )
        ]
        records, _ = build_records(outputs, Settings())
        report = build_wiring_report(outputs, records, [])
        hinted = {item["column"] for item in report["unmapped_that_look_like_fields"]}
        self.assertIn("首课时间", hinted, "a date column left unmapped must be raised")
        self.assertNotIn("开班人数", hinted, "a count column is not a field we collect")
        self.assertNotIn("产品包ID", hinted)

    def test_hints_name_the_field_they_resemble(self) -> None:
        from research_facts.adapters.csv_table import looks_like_fields

        self.assertIn("start_date", looks_like_fields("首课时间"))
        self.assertIn("instructor", looks_like_fields("授课教授"))
        self.assertIn("project_title", looks_like_fields("课题名称"))
        self.assertEqual(looks_like_fields("产品包ID"), [])

    def test_semantics_reach_the_evidence(self) -> None:
        from research_facts.adapters.csv_table import CsvTableAdapter, TableProfile

        with tempfile.TemporaryDirectory() as tmp:
            header = ["课题ID", "开课日期"]
            path = self._csv(
                Path(tmp), header,
                {"课题ID": "A", "开课日期": "2027-03-02"},
            )
            profile = TableProfile.from_dict(
                {"kind": "csv", "name": "t", "provider": "p", "id_column": "课题ID",
                 "fields": {"start_date": ["开课日期"]},
                 "semantics": {"start_date": "取自 firstCourseBeginTime"}}
            )
            outputs = CsvTableAdapter(profile).load(path, Settings())
        claim = outputs[0].claims[0]
        self.assertIn("semantics=取自 firstCourseBeginTime", claim.locator.detail)
        self.assertNotIn("firstCourseBeginTime", claim.raw_text)


class TestCohortContextInOutputs(unittest.TestCase):
    def test_the_fact_card_names_the_cohorts(self) -> None:
        from research_facts.dedup import cohort_index

        records, _ = build_records(
            [
                AdapterOutput(
                    document=make_document(
                        document_id=f"p#T{i}", source_kind="web_json", provider="p",
                        origin="mem", external_id=f"T{i}",
                    ),
                    claims=[
                        FieldClaim(
                            field="project_title", raw_text="同一课题",
                            locator=Locator("json_path", f"p#T{i}", "$.name"),
                            extractor="json_path:$.name", extraction_method="json_path",
                            extraction_confidence="high", normalized_value="同一课题",
                            normalization={"compare_key": "同一课题"},
                        ),
                        FieldClaim(
                            field="start_date", raw_text=date,
                            locator=Locator("json_path", f"p#T{i}", "$.start"),
                            extractor="json_path:$.start", extraction_method="json_path",
                            extraction_confidence="high", normalized_value=date,
                            normalization={"compare_key": date.replace("-", "")},
                        ),
                    ],
                )
                for i, date in enumerate(("2026-11-06", "2027-01-15", "2027-02-26"))
            ],
            Settings(),
        )
        from research_facts.dedup import build_cohort_report

        report = build_cohort_report(records)
        index = cohort_index(report)
        from research_facts.exporter import render_markdown

        card = render_markdown(records[0], None, index[records[0].record_key])
        self.assertIn("3 期", card)
        self.assertIn("2026-11-06", card)
        self.assertIn("写稿时务必指明期次", card)

    def test_a_single_run_gets_no_cohort_note(self) -> None:
        from research_facts.exporter import render_markdown
        from research_facts.schema import Identity, ProjectFactRecord

        record = ProjectFactRecord(
            record_key="p:external_id:S",
            identity=Identity(provider="p", external_id="S", basis="external_id"),
            fields={
                name: FieldState(field=name, status="missing") for name in FIELD_NAMES
            }
            | {
                "project_title": FieldState(
                    field="project_title", status="resolved",
                    selected_raw_text="单期课题", selected_normalized_value="单期课题",
                )
            },
        )
        self.assertNotIn("期次", render_markdown(record, None, {"p:external_id:S": {"size": 1}}))


class TestRelatedGroupsAreAdvisoryOnly(unittest.TestCase):
    """Two titles at 0.96 similarity must be linked, never merged."""

    def _record(self, key: str, title: str, date: str) -> ProjectFactRecord:
        return ProjectFactRecord(
            record_key=key,
            identity=Identity(provider="p", external_id=key.split(":")[-1], basis="external_id"),
            fields={
                name: FieldState(field=name, status="missing") for name in FIELD_NAMES
            }
            | {
                "project_title": FieldState(
                    field="project_title", status="resolved",
                    selected_raw_text=title, selected_normalized_value=title,
                ),
                "start_date": FieldState(
                    field="start_date", status="resolved",
                    selected_raw_text=date, selected_normalized_value=date,
                ),
            },
        )

    def test_near_identical_titles_are_linked_but_not_merged(self) -> None:
        from research_facts.dedup import build_cohort_report

        records = [
            self._record("p:external_id:A", "商业管理：红海与蓝海--商业模式画布解析", "2026-01-01"),
            self._record("p:external_id:B", "商业管理：红海与蓝海——商业模式画布解析", "2027-01-01"),
            self._record("p:external_id:C", "商业管理：红海与蓝海--商业模式画布解析", "2026-06-01"),
            self._record("p:external_id:D", "商业管理：红海与蓝海——商业模式画布解析", "2027-06-01"),
        ]
        report = build_cohort_report(records)
        self.assertEqual(report["topic_groups"], 2, "exact keys stay separate")
        self.assertEqual(len(report["related_groups"]), 1)
        link = report["related_groups"][0]
        self.assertGreaterEqual(link["similarity"], 0.90)
        self.assertFalse(link["merged"])
        self.assertIn("未合并", link["note"])
        # The decisive assertion: four records in, four records out.
        self.assertEqual(len(records), 4)
        self.assertEqual({run["record_key"] for g in report["groups"] for run in g["runs"]},
                         {item.record_key for item in records})

    def test_same_date_siblings_are_listed_for_the_merge_gate(self) -> None:
        from research_facts.dedup import build_cohort_report

        records = [
            self._record("p:external_id:A", "同一课题", "2026-01-01"),
            self._record("p:external_id:B", "同一课题", "2026-01-01"),
            self._record("p:external_id:C", "同一课题", "2027-01-01"),
        ]
        report = build_cohort_report(records)
        self.assertEqual(len(report["same_date_sibling_groups"]), 1)
        group = report["same_date_sibling_groups"][0]
        self.assertEqual(group["run_count"], 3)
        self.assertEqual(group["distinct_dates"], 2)
        self.assertEqual(len(group["record_keys"]), 3)

    def test_the_report_carries_a_drift_signature(self) -> None:
        from research_facts.dedup import build_cohort_report

        records = [self._record("p:external_id:A", "课题甲", "2026-01-01")]
        first = build_cohort_report(records)["subject_signature"]
        again = build_cohort_report(records)["subject_signature"]
        changed = build_cohort_report(
            [self._record("p:external_id:A", "课题乙", "2026-01-01")]
        )["subject_signature"]
        self.assertEqual(first, again)
        self.assertNotEqual(first, changed)
