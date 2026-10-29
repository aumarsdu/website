"""T10 projection cases on the real candidate PostgreSQL cluster."""

import json
import tempfile
import unittest
from pathlib import Path

import importer
import pg_candidate
import projection
from stage_validator import validate_and_seal

SIDE = Path(__file__).resolve().parent


class ProjectionTests(unittest.TestCase):
    db: str

    @classmethod
    def setUpClass(cls) -> None:
        pg_candidate.init_cluster()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.db = "t10_" + self.id().split(".")[-1]
        pg_candidate.drop_database(self.db)
        pg_candidate.create_database(self.db)
        self.addCleanup(pg_candidate.drop_database, self.db)
        import run_migrations

        self.assertEqual(
            run_migrations.run(self.db, SIDE / "migrations", __import__("sys").stdout),
            run_migrations.EXIT_OK,
        )

    def make_batch(
        self, name: str, batch_id: str, rows: list[dict]
    ) -> tuple[Path, Path]:
        staging = self.work / name / "staging"
        staging.mkdir(parents=True)
        with open(staging / "records.jsonl", "w", encoding="utf-8") as out:
            out.writelines(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows
            )
        data = (staging / "records.jsonl").read_bytes()
        import hashlib

        manifest = {
            "contract_version": "1",
            "batch_id": batch_id,
            "source_code": "jisi_future_sou_tools",
            "capture_mode": "full",
            "captured_at": "2026-06-02T07:52:16Z",
            "observed_order": "unknown",
            "coverage": "complete",
            "adapter_version": "t04-v1",
            "mapping_version": "t04-v1",
            "hash_version": "h1",
            "scope": {"entry": "test"},
            "input_files": [
                {
                    "relative_path": "records.jsonl",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "byte_size": len(data),
                    "row_count": len(rows),
                    "format": "jsonl",
                    "role": "fact",
                }
            ],
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        sealed = self.work / name / "sealed"
        self.assertTrue(validate_and_seal(staging, sealed)["sealed"])
        return staging, sealed

    def import_rows(self, name: str, batch_id: str, rows: list[dict]) -> dict:
        staging, sealed = self.make_batch(name, batch_id, rows)
        return importer.import_sealed(staging, sealed, self.db)

    def query(self, sql: str) -> list[str]:
        return [
            line
            for line in pg_candidate.psql(self.db, sql).stdout.splitlines()
            if line.strip()
        ]

    def identity_of(self, native: str) -> str:
        return json.dumps(
            {"native_id": native, "source": "jisi_future_sou_tools"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def test_manual_value_shown_alongside_source(self) -> None:
        self.import_rows(
            "b1",
            "batch-t10-1",
            [
                {
                    "id": "JS-1",
                    "title": "来源标题",
                    "crawled_at": "2026-06-01T00:00:00Z",
                },
            ],
        )
        identity = self.identity_of("JS-1")
        record_id = self.query(
            f"SELECT source_record_id FROM source_records WHERE identity_key = "
            f"'{identity}';"
        )[0]
        projection.apply_override(
            self.db,
            "source_record",
            int(record_id),
            "title",
            "来源标题",
            "人工修正标题",
            "h1",
            "人工复核修正",
            "owner",
        )
        view = projection.project_record(self.db, identity)
        self.assertEqual(view["active_manual_value"], "人工修正标题")
        self.assertEqual(view["shown_value"], "人工修正标题")
        self.assertIsNotNone(view["source_value"])

    def test_withdraw_restores_source_and_keeps_audit(self) -> None:
        self.import_rows(
            "b2",
            "batch-t10-2",
            [
                {
                    "id": "JS-2",
                    "title": "来源标题二",
                    "crawled_at": "2026-06-01T00:00:00Z",
                },
            ],
        )
        identity = self.identity_of("JS-2")
        record_id = int(
            self.query(
                f"SELECT source_record_id FROM source_records WHERE identity_key = "
                f"'{identity}';"
            )[0]
        )
        override_id = projection.apply_override(
            self.db,
            "source_record",
            record_id,
            "title",
            "来源标题二",
            "临时改",
            "h1",
            "试改",
            "owner",
        )
        projection.withdraw_override(self.db, override_id, "owner")
        view = projection.project_record(self.db, identity)
        self.assertIsNone(view["active_manual_value"])
        self.assertEqual(view["shown_value"], "来源标题二")
        audit = self.query(
            "SELECT count(*) FROM manual_overrides WHERE override_id = "
            f"{override_id} OR reverted_by = {override_id};"
        )[0]
        self.assertEqual(audit, "2")

    def test_withdraw_unknown_reference_rejected(self) -> None:
        with self.assertRaisesRegex(projection.ProjectionError, "reference_missing"):
            projection.withdraw_override(self.db, 99999, "owner")

    def test_override_unknown_entity_rejected(self) -> None:
        with self.assertRaisesRegex(projection.ProjectionError, "reference_missing"):
            projection.apply_override(
                self.db,
                "source_record",
                424242,
                "title",
                None,
                "x",
                "h1",
                "r",
                "owner",
            )

    def test_late_arrival_does_not_override_manual(self) -> None:
        self.import_rows(
            "b3",
            "batch-t10-3",
            [
                {"id": "JS-3", "title": "旧来源", "crawled_at": "2026-06-01T00:00:00Z"},
            ],
        )
        identity = self.identity_of("JS-3")
        record_id = int(
            self.query(
                f"SELECT source_record_id FROM source_records WHERE identity_key = "
                f"'{identity}';"
            )[0]
        )
        projection.apply_override(
            self.db,
            "source_record",
            record_id,
            "title",
            "旧来源",
            "人工值",
            "h1",
            "修正",
            "owner",
        )
        self.import_rows(
            "b4",
            "batch-t10-4",
            [
                {"id": "JS-3", "title": "新来源", "crawled_at": "2026-09-01T00:00:00Z"},
            ],
        )
        view = projection.project_record(self.db, identity)
        self.assertEqual(view["active_manual_value"], "人工值")
        self.assertEqual(view["source_value"], "新来源")

    def test_rebuild_consistency_after_mixed_history(self) -> None:
        self.import_rows(
            "c1",
            "batch-t10-c1",
            [
                {"id": "JS-4", "title": "项目甲", "crawled_at": "2026-06-01T00:00:00Z"},
                {"id": "JS-5", "title": "项目乙", "crawled_at": "2026-06-01T00:00:00Z"},
            ],
        )
        self.import_rows(
            "c2",
            "batch-t10-c2",
            [
                {
                    "id": "JS-4",
                    "title": "项目甲改",
                    "crawled_at": "2026-07-01T00:00:00Z",
                },
            ],
        )
        identity = self.identity_of("JS-4")
        record_id = int(
            self.query(
                f"SELECT source_record_id FROM source_records WHERE identity_key = "
                f"'{identity}';"
            )[0]
        )
        override_id = projection.apply_override(
            self.db,
            "source_record",
            record_id,
            "title",
            "项目甲改",
            "甲人工",
            "h1",
            "修正",
            "owner",
        )
        projection.withdraw_override(self.db, override_id, "owner")
        report = projection.rebuild_consistency(self.db)
        self.assertTrue(report["consistent"], report)
        self.assertEqual(report["identities"], 2)

    def test_two_offerings_distinct(self) -> None:
        self.import_rows(
            "d1",
            "batch-t10-d1",
            [
                {"id": "JS-6", "title": "项目丙", "crawled_at": "2026-06-01T00:00:00Z"},
            ],
        )
        self.query(
            "INSERT INTO provider_projects (provider_id, native_project_key) "
            "SELECT provider_id, 'PP-T10' FROM providers LIMIT 1;"
        )
        self.query(
            "INSERT INTO offerings (provider_project_id, offering_key, "
            "start_date_raw, price_amount, price_raw, currency, field_state) "
            "SELECT provider_project_id, 'OFF-7月', '2026-07-01', 100.00, '100', "
            "'CNY', 'value' FROM provider_projects WHERE native_project_key='PP-T10';"
        )
        self.query(
            "INSERT INTO offerings (provider_project_id, offering_key, "
            "start_date_raw, start_precision, price_amount, price_raw, currency, "
            "field_state) SELECT provider_project_id, 'OFF-8月', '2026-08-01', "
            "'day', 200.00, '200', 'CNY', 'value' FROM provider_projects "
            "WHERE native_project_key='PP-T10';"
        )
        rows = self.query(
            "SELECT offering_key, price_amount FROM offerings o "
            "JOIN provider_projects p USING (provider_project_id) "
            "WHERE native_project_key = 'PP-T10' ORDER BY offering_key;"
        )
        self.assertEqual(rows, ["OFF-7月|100.00", "OFF-8月|200.00"])

    def test_unknown_only_gets_unresolved_current(self) -> None:
        self.import_rows(
            "u1",
            "batch-t10-u1",
            [
                {"id": "JS-U", "title": "无日期记录"},
            ],
        )
        identity = self.identity_of("JS-U")
        status = self.query(
            f"SELECT c.status FROM source_record_current c "
            f"JOIN source_records r ON r.source_record_id = c.source_record_id "
            f"WHERE r.identity_key = '{identity}';"
        )[0]
        self.assertEqual(status, "unresolved")
        report = projection.rebuild_consistency(self.db)
        self.assertTrue(report["consistent"], report)

    def test_pointer_drift_detected_by_rebuild(self) -> None:
        self.import_rows(
            "d1",
            "batch-t10-dr1",
            [
                {
                    "id": "JS-D1",
                    "title": "项目早",
                    "crawled_at": "2026-06-01T00:00:00Z",
                },
            ],
        )
        self.import_rows(
            "d2",
            "batch-t10-dr2",
            [
                {
                    "id": "JS-D1",
                    "title": "项目晚",
                    "crawled_at": "2026-09-01T00:00:00Z",
                },
            ],
        )
        identity = self.identity_of("JS-D1")
        # drift the pointer back to the older observation, keep status ok
        self.query(
            f"UPDATE source_record_current c SET observation_id = "
            f"(SELECT min(o.observation_id) FROM observations o "
            f"JOIN source_records r ON r.source_record_id = c.source_record_id "
            f"WHERE r.identity_key = '{identity}');"
        )
        report = projection.rebuild_consistency(self.db)
        self.assertFalse(report["consistent"], report)
        kinds = {m["kind"] for m in report["mismatches"]}
        self.assertIn("pointer_drift", kinds)
        # re-import heals the drifted pointer (idempotent replay recomputes)
        self.import_rows(
            "d2b",
            "batch-t10-dr2b",
            [
                {
                    "id": "JS-D1",
                    "title": "项目晚",
                    "crawled_at": "2026-09-01T00:00:00Z",
                },
            ],
        )
        report = projection.rebuild_consistency(self.db)
        self.assertTrue(report["consistent"], report)

    def test_not_seen_flagged_on_complete_snapshot(self) -> None:
        self.import_rows(
            "s1",
            "batch-t10-s1",
            [
                {"id": "JS-A", "title": "在册", "crawled_at": "2026-06-01T00:00:00Z"},
                {"id": "JS-B", "title": "将缺席", "crawled_at": "2026-06-01T00:00:00Z"},
            ],
        )
        self.import_rows(
            "s2",
            "batch-t10-s2",
            [
                {"id": "JS-A", "title": "在册", "crawled_at": "2026-07-01T00:00:00Z"},
            ],
        )
        flagged = projection.not_seen_report(self.db, "batch-t10-s2")
        self.assertEqual(
            [f["identity_key"] for f in flagged], [self.identity_of("JS-B")]
        )
        # the missing record keeps its observations and current pointer
        b_current = self.query(
            f"SELECT c.status FROM source_record_current c "
            f"JOIN source_records r ON r.source_record_id = c.source_record_id "
            f"WHERE r.identity_key = '{self.identity_of('JS-B')}';"
        )
        self.assertEqual(b_current, ["ok"])

    def test_not_seen_requires_complete_snapshot(self) -> None:
        import hashlib

        staging_s3 = self.work / "s3" / "staging"
        staging_s3.mkdir(parents=True)
        rows_s3 = [
            {"id": "JS-P", "title": "部分", "crawled_at": "2026-06-01T00:00:00Z"}
        ]
        with open(staging_s3 / "records.jsonl", "w", encoding="utf-8") as out:
            out.writelines(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows_s3
            )
        data = (staging_s3 / "records.jsonl").read_bytes()
        manifest = {
            "contract_version": "1",
            "batch_id": "batch-t10-s3",
            "source_code": "jisi_future_sou_tools",
            "capture_mode": "full",
            "captured_at": "2026-06-01T00:00:00Z",
            "observed_order": "unknown",
            "coverage": "partial",
            "adapter_version": "t04-v1",
            "mapping_version": "t04-v1",
            "hash_version": "h1",
            "scope": {"entry": "test"},
            "input_files": [
                {
                    "relative_path": "records.jsonl",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "byte_size": len(data),
                    "row_count": 1,
                    "format": "jsonl",
                    "role": "fact",
                }
            ],
        }
        (staging_s3 / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        sealed_s3 = self.work / "s3" / "sealed"
        self.assertTrue(validate_and_seal(staging_s3, sealed_s3)["sealed"])
        importer.import_sealed(staging_s3, sealed_s3, self.db)
        with self.assertRaisesRegex(
            projection.ProjectionError, "not_a_complete_snapshot"
        ):
            projection.not_seen_report(self.db, "batch-t10-s3")

    def test_quality_queue_lists_items(self) -> None:
        self.import_rows(
            "q1",
            "batch-t10-q1",
            [
                {"id": "JS-Q1", "title": "甲", "crawled_at": "2026-06-01T00:00:00Z"},
                {"id": "JS-Q2", "title": "乙", "crawled_at": "2026-06-01T00:00:00Z"},
            ],
        )
        self.import_rows(
            "q2",
            "batch-t10-q2",
            [
                {"id": "JS-Q1", "title": "甲改", "crawled_at": "2026-06-01T00:00:00Z"},
            ],
        )
        self.import_rows(
            "q3",
            "batch-t10-q3",
            [
                {"id": "JS-Q1", "title": "在册", "crawled_at": "2026-07-01T00:00:00Z"},
            ],
        )
        projection.not_seen_report(self.db, "batch-t10-q3")
        queue = projection.quality_queue(self.db)
        kinds = {item["kind"] for item in queue}
        self.assertIn("conflict", kinds)
        self.assertIn("quality_issue", kinds)
        not_seen = [i for i in queue if "not_seen" in i.get("description", "")]
        self.assertEqual(len(not_seen), 1)


if __name__ == "__main__":
    unittest.main()
