"""T12 backup/restore drill cases on the real candidate PostgreSQL cluster."""

import json
import tempfile
import unittest
from pathlib import Path

import backup_restore
import pg_candidate
from contract import canonical_json
from stage_validator import validate_and_seal

SIDE = Path(__file__).resolve().parent


class BackupRestoreTests(unittest.TestCase):
    db: str

    @classmethod
    def setUpClass(cls) -> None:
        pg_candidate.init_cluster()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.db = "t12_" + self.id().split(".")[-1]
        pg_candidate.drop_database(self.db)
        pg_candidate.create_database(self.db)
        self.addCleanup(pg_candidate.drop_database, self.db)
        import run_migrations

        self.assertEqual(
            run_migrations.run(self.db, SIDE / "migrations", __import__("sys").stdout),
            run_migrations.EXIT_OK,
        )

    def seed(self, rows: int = 3) -> None:
        staging = self.work / "seed" / "staging"
        staging.mkdir(parents=True)
        data_rows = [
            {
                "id": f"JS-{i}",
                "title": f"种子项目{i}",
                "crawled_at": f"2026-06-0{i + 1}T00:00:00Z",
            }
            for i in range(1, rows + 1)
        ]
        with open(staging / "records.jsonl", "w", encoding="utf-8") as out:
            out.writelines(canonical_json(row) + "\n" for row in data_rows)
        import hashlib

        data = (staging / "records.jsonl").read_bytes()
        manifest = {
            "contract_version": "1",
            "batch_id": "batch-t12-seed",
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
                    "row_count": len(data_rows),
                    "format": "jsonl",
                    "role": "fact",
                }
            ],
        }
        (staging / "manifest.json").write_text(
            canonical_json(manifest) + "\n", encoding="utf-8"
        )
        sealed = self.work / "seed" / "sealed"
        self.assertTrue(validate_and_seal(staging, sealed)["sealed"])
        import importer

        self.assertEqual(
            importer.import_sealed(staging, sealed, self.db)["status"], "committed"
        )

    def snapshot_counts(self) -> dict:
        counts = {}
        for table in backup_restore.COUNT_TABLES:
            counts[table] = int(
                pg_candidate.psql(
                    self.db, f"SELECT count(*) FROM {table};"
                ).stdout.strip()
            )
        overrides = json.loads(
            pg_candidate.psql(
                self.db,
                "SELECT coalesce(jsonb_agg(jsonb_build_object('entity_kind', "
                "entity_kind, 'entity_id', entity_id, 'field_name', field_name, "
                "'new_value', new_value, 'author', author) ORDER BY override_id), "
                "'[]'::jsonb) FROM manual_overrides WHERE reverted_by IS NULL;",
            ).stdout.strip()
        )
        counts["manual_overrides_active_list"] = overrides
        return counts

    def test_valid_restore_reconciles(self) -> None:
        self.seed()
        pg_candidate.psql(
            self.db,
            "INSERT INTO manual_overrides (entity_kind, entity_id, field_name, "
            "new_value, basis_version, reason, author) VALUES "
            "('source_record', 1, 'title', '人工标题', 'h1', '修正', 'owner');",
        )
        backup_dir = self.work / "backup"
        meta = backup_restore.create_backup(self.db, backup_dir)
        self.assertEqual(meta["counts"]["source_records"], 3)
        self.assertEqual(len(meta["manual_overrides_active"]), 1)
        restored = backup_restore.restore_backup(backup_dir, self.db + "_restored")
        self.addCleanup(pg_candidate.drop_database, self.db + "_restored")
        self.assertTrue(restored["counts_reconciled"], restored)
        self.assertLess(restored["rto_seconds"], 3600)
        overrides = json.loads(
            pg_candidate.psql(
                self.db + "_restored",
                "SELECT coalesce(jsonb_agg(new_value ORDER BY override_id), '[]'::jsonb) "
                "FROM manual_overrides;",
            ).stdout.strip()
        )
        self.assertEqual(overrides, ["人工标题"])

    def test_corrupted_dump_rejected(self) -> None:
        self.seed()
        backup_dir = self.work / "backup"
        backup_restore.create_backup(self.db, backup_dir)
        dump = backup_dir / "database.dump"
        dump.write_bytes(dump.read_bytes()[:64] + b"corrupted tail")
        with self.assertRaisesRegex(backup_restore.BackupError, "dump_corrupted"):
            backup_restore.restore_backup(backup_dir, self.db + "_bad")

    def test_missing_asset_reported(self) -> None:
        asset_root = self.work / "assets"
        (asset_root / "posters").mkdir(parents=True)
        (asset_root / "posters" / "a.png").write_bytes(b"png-a-bytes")
        self.seed()
        backup_dir = self.work / "backup"
        backup_restore.create_backup(self.db, backup_dir, asset_roots=[asset_root])
        (asset_root / "posters" / "a.png").unlink()
        restored = backup_restore.restore_backup(backup_dir, self.db + "_restored")
        self.addCleanup(pg_candidate.drop_database, self.db + "_restored")
        issues = [m for m in restored["mismatches"] if m.get("issue")]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue"], "missing")

    def test_post_backup_rows_not_counted_as_snapshot_loss(self) -> None:
        self.seed()
        backup_dir = self.work / "backup"
        meta = backup_restore.create_backup(self.db, backup_dir)
        baseline = meta["counts"]["observations"]

        # a NEW sealed batch after the backup: live DB grows, snapshot unchanged
        staging = self.work / "post" / "staging"
        staging.mkdir(parents=True)
        new_rows = [
            {
                "id": "JS-POST",
                "title": "备份后新增",
                "crawled_at": "2026-09-26T00:00:00Z",
            }
        ]
        with open(staging / "records.jsonl", "w", encoding="utf-8") as out:
            out.writelines(canonical_json(row) + chr(10) for row in new_rows)
        import hashlib

        data = (staging / "records.jsonl").read_bytes()
        manifest = {
            "contract_version": "1",
            "batch_id": "batch-t12-post",
            "source_code": "jisi_future_sou_tools",
            "capture_mode": "full",
            "captured_at": "2026-09-26T00:00:00Z",
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
                    "row_count": 1,
                    "format": "jsonl",
                    "role": "fact",
                }
            ],
        }
        (staging / "manifest.json").write_text(
            canonical_json(manifest) + chr(10), encoding="utf-8"
        )
        sealed_post = self.work / "post" / "sealed"
        self.assertTrue(validate_and_seal(staging, sealed_post)["sealed"])
        import importer

        self.assertEqual(
            importer.import_sealed(staging, sealed_post, self.db)["status"],
            "committed",
        )
        restored = backup_restore.restore_backup(backup_dir, self.db + "_restored")
        self.assertTrue(restored["counts_reconciled"])
        self.assertEqual(restored["mismatches"], [])
        restored_total = int(
            pg_candidate.psql(
                self.db + "_restored", "SELECT count(*) FROM observations;"
            ).stdout.strip()
        )
        self.assertEqual(restored_total, baseline)
        live_total = int(
            pg_candidate.psql(
                self.db, "SELECT count(*) FROM observations;"
            ).stdout.strip()
        )
        self.assertEqual(live_total, baseline + 1)

    def query(self, sql: str) -> str:
        return pg_candidate.psql(self.db, sql).stdout.strip()

    def test_switch_drill_and_rollback(self) -> None:
        self.seed()
        backup_dir = self.work / "backup"
        backup_restore.create_backup(self.db, backup_dir)
        outcome = backup_restore.switch_drill(
            backup_dir, self.db, self.db + "_switched"
        )
        self.addCleanup(pg_candidate.drop_database, self.db + "_switched")
        self.assertTrue(outcome["switch_to_restored"])
        self.assertTrue(outcome["fallback_to_original"])
        failed_steps = [s for s in outcome["steps"] if s["step"] == "failed_switch"]
        self.assertTrue(failed_steps[0]["failed_as_expected"])


if __name__ == "__main__":
    unittest.main()
