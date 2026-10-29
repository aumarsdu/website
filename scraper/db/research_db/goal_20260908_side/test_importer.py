"""T09 importer cases on the real candidate PostgreSQL cluster."""

import tempfile
import threading
import unittest
from pathlib import Path

import importer
import pg_candidate
from contract import canonical_json
from stage_validator import validate_and_seal

SIDE = Path(__file__).resolve().parent


def sha_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


class ImporterTests(unittest.TestCase):
    db: str

    @classmethod
    def setUpClass(cls) -> None:
        pg_candidate.init_cluster()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.db = "t09_" + self.id().split(".")[-1]
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
            out.writelines(canonical_json(row) + "\n" for row in rows)
        data = (staging / "records.jsonl").read_bytes()
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
                    "sha256": sha_bytes(data),
                    "byte_size": len(data),
                    "row_count": len(rows),
                    "format": "jsonl",
                    "role": "fact",
                }
            ],
        }
        (staging / "manifest.json").write_text(
            canonical_json(manifest) + "\n", encoding="utf-8"
        )
        sealed = self.work / name / "sealed"
        verdict = validate_and_seal(staging, sealed)
        self.assertTrue(verdict["sealed"], verdict)
        return staging, sealed

    @staticmethod
    def row(native: str, title: str, order: str, context: str | None = None) -> dict:
        row = {"id": native, "title": title, "crawled_at": order}
        if context:
            row["context_key"] = context
        return row

    def query(self, sql: str) -> list[str]:
        return [
            line
            for line in pg_candidate.psql(self.db, sql).stdout.splitlines()
            if line.strip()
        ]

    def test_replay_zero_delta(self) -> None:
        staging, sealed = self.make_batch(
            "b1", "batch-t09-1", [self.row("JS-1", "项目A", "2026-06-02T07:52:16Z")]
        )
        first = importer.import_sealed(staging, sealed, self.db)
        self.assertEqual(first["status"], "committed")
        self.assertEqual(first["counts"]["inserted_observations"], 1)
        second = importer.import_sealed(staging, sealed, self.db)
        self.assertEqual(second["status"], "committed")
        self.assertEqual(second["counts"]["inserted_observations"], 0)
        self.assertEqual(second["counts"]["unchanged_observations"], 1)

    def test_ab_a_keeps_three_observations_and_current(self) -> None:
        for name, batch_id, title, order in (
            ("a1", "batch-a1", "项目A", "2026-06-01T00:00:00Z"),
            ("a2", "batch-a2", "项目B", "2026-06-02T00:00:00Z"),
            ("a3", "batch-a3", "项目A", "2026-06-03T00:00:00Z"),
        ):
            staging, sealed = self.make_batch(
                name, batch_id, [self.row("JS-1", title, order)]
            )
            receipt = importer.import_sealed(staging, sealed, self.db)
            self.assertEqual(receipt["status"], "committed")
        observations = self.query("SELECT count(*) FROM observations;")[0]
        self.assertEqual(observations, "3")
        current = self.query(
            "SELECT p.payload_hash, c.status FROM source_record_current c "
            "JOIN observations o ON o.observation_id = c.observation_id "
            "JOIN content_payloads p ON p.payload_id = o.payload_id;"
        )[0]
        payload_a = self.query(
            "SELECT payload_hash FROM content_payloads ORDER BY payload_id LIMIT 1;"
        )[0]
        self.assertEqual(current, payload_a + "|ok")

    def test_six_permutations_converge(self) -> None:
        import itertools

        batches = [
            ("batch-p1", "项目A", "2026-06-01T00:00:00Z"),
            ("batch-p2", "项目B", "2026-06-02T00:00:00Z"),
            ("batch-p3", "项目C", "2026-06-03T00:00:00Z"),
        ]
        finals = set()
        for index, permutation in enumerate(itertools.permutations(range(3))):
            tag = "".join(map(str, permutation))
            for position, batch_index in enumerate(permutation):
                batch_id, title, order = batches[batch_index]
                staging, sealed = self.make_batch(
                    f"perm{tag}_{position}",
                    batch_id,
                    [self.row("JS-9", title, order)],
                )
                receipt = importer.import_sealed(staging, sealed, self.db)
                self.assertEqual(receipt["status"], "committed")
            finals.add(
                tuple(
                    self.query(
                        "SELECT p.payload_hash, c.status FROM source_record_current c "
                        "JOIN observations o ON o.observation_id = c.observation_id "
                        "JOIN content_payloads p ON p.payload_id = o.payload_id "
                        "UNION ALL SELECT 'obs', count(*)::text FROM observations;"
                    )
                )
            )
        self.assertEqual(len(finals), 1)

    def test_same_order_conflict_recorded(self) -> None:
        staging1, sealed1 = self.make_batch(
            "c1",
            "batch-c1",
            [self.row("JS-2", "项目B", "2026-06-05T00:00:00Z")],
        )
        self.assertEqual(
            importer.import_sealed(staging1, sealed1, self.db)["status"], "committed"
        )
        staging2, sealed2 = self.make_batch(
            "c2",
            "batch-c2",
            [self.row("JS-2", "项目C", "2026-06-05T00:00:00Z")],
        )
        self.assertEqual(
            importer.import_sealed(staging2, sealed2, self.db)["status"], "committed"
        )
        conflicts = self.query("SELECT count(*) FROM conflicts;")[0]
        self.assertGreaterEqual(int(conflicts), 1)
        status = self.query("SELECT status FROM source_record_current;")[0]
        self.assertEqual(status, "conflict")

    def test_old_batch_never_regresses_current(self) -> None:
        staging_new, sealed_new = self.make_batch(
            "n1",
            "batch-n1",
            [self.row("JS-3", "项目新", "2026-09-01T00:00:00Z")],
        )
        importer.import_sealed(staging_new, sealed_new, self.db)
        staging_old, sealed_old = self.make_batch(
            "o1",
            "batch-o1",
            [self.row("JS-3", "项目旧", "2026-06-01T00:00:00Z")],
        )
        importer.import_sealed(staging_old, sealed_old, self.db)
        title = self.query(
            "SELECT p.payload_hash FROM source_record_current c "
            "JOIN observations o ON o.observation_id = c.observation_id "
            "JOIN content_payloads p ON p.payload_id = o.payload_id "
            "JOIN observations o2 ON o2.observation_id = c.observation_id "
            "WHERE o.order_key = '2026-09-01T00:00:00Z';"
        )
        self.assertEqual(len(title), 1)

    def test_batch_id_reuse_rejected(self) -> None:
        staging1, sealed1 = self.make_batch(
            "r1", "batch-reuse", [self.row("JS-4", "项目一", "2026-06-01T00:00:00Z")]
        )
        self.assertEqual(
            importer.import_sealed(staging1, sealed1, self.db)["status"], "committed"
        )
        before = importer._committed_counts(self.db, "batch-reuse")
        staging2, sealed2 = self.make_batch(
            "r2", "batch-reuse", [self.row("JS-5", "项目二", "2026-06-02T00:00:00Z")]
        )
        receipt = importer.import_sealed(staging2, sealed2, self.db)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["error"], "identity_conflict")
        after = importer._committed_counts(self.db, "batch-reuse")
        self.assertEqual(before, after)

    def test_multi_context_preserved(self) -> None:
        staging, sealed = self.make_batch(
            "mc",
            "batch-mc",
            [
                self.row("JS-6", "项目多", "2026-06-01T00:00:00Z", context="list"),
                self.row("JS-6", "项目多", "2026-06-01T00:00:00Z", context="detail"),
            ],
        )
        receipt = importer.import_sealed(staging, sealed, self.db)
        self.assertEqual(receipt["status"], "committed")
        self.assertEqual(receipt["counts"]["inserted_observations"], 2)

    def test_tampered_seal_rejected_without_writes(self) -> None:
        staging, sealed = self.make_batch(
            "t1",
            "batch-tamper",
            [self.row("JS-7", "项目T", "2026-06-01T00:00:00Z")],
        )
        before = importer._committed_counts(self.db, "batch-tamper")
        batch = sealed / "batch.jsonl"
        batch.write_text(
            batch.read_text(encoding="utf-8").replace("项目T", "项目篡改"),
            encoding="utf-8",
        )
        receipt = importer.import_sealed(staging, sealed, self.db)
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("input_changed", receipt["error"])
        self.assertEqual(before, importer._committed_counts(self.db, "batch-tamper"))

    def test_size_cap_rejected(self) -> None:
        staging, sealed = self.make_batch(
            "cap",
            "batch-cap",
            [
                self.row(f"JS-C{i}", f"项目{i}", "2026-06-01T00:00:00Z")
                for i in range(3)
            ],
        )
        receipt = importer.import_sealed(staging, sealed, self.db, max_rows=2)
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("batch_too_large", receipt["error"])

    def test_manual_overrides_untouched(self) -> None:
        pg_candidate.psql(
            self.db,
            "INSERT INTO manual_overrides (entity_kind, entity_id, field_name, "
            "new_value, basis_version, reason, author) VALUES "
            "('source_record', 1, 'title', '人工标题', 'v1', '人工修正', 'owner');",
        )
        overrides_before = self.query("SELECT count(*) FROM manual_overrides;")[0]
        staging, sealed = self.make_batch(
            "mo",
            "batch-mo",
            [self.row("JS-8", "项目M", "2026-06-01T00:00:00Z")],
        )
        self.assertEqual(
            importer.import_sealed(staging, sealed, self.db)["status"], "committed"
        )
        self.assertEqual(
            self.query("SELECT count(*) FROM manual_overrides;")[0], overrides_before
        )

    def test_concurrent_same_batch_serialized(self) -> None:
        staging, sealed = self.make_batch(
            "cc",
            "batch-conc",
            [
                self.row(f"JS-K{i}", f"项目K{i}", "2026-06-01T00:00:00Z")
                for i in range(3)
            ],
        )
        receipts: list = []

        def worker() -> None:
            receipts.append(importer.import_sealed(staging, sealed, self.db))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(receipts), 2)
        inserted_sum = 0
        for receipt in receipts:
            self.assertEqual(receipt["status"], "committed", receipt)
            counts = receipt["counts"]
            # receipt honesty: inserted + unchanged == rows_read, no inflation
            self.assertEqual(
                counts["inserted_observations"] + counts["unchanged_observations"],
                counts["rows_read"],
                receipt,
            )
            inserted_sum += counts["inserted_observations"]
        self.assertEqual(inserted_sum, 3)
        total = self.query("SELECT count(*) FROM observations;")[0]
        self.assertEqual(total, "3")

    def test_disconnect_mid_flight_recovers(self) -> None:
        """Unknown commit outcome is resolved by re-query and re-import."""
        import subprocess

        sql = (
            "BEGIN; INSERT INTO source_records (source_id, identity_key) "
            'SELECT source_id, \'{"native_id":"GHOST","source":"x"}\' '
            "FROM sources LIMIT 1; SELECT pg_sleep(30);"
        )
        holder = subprocess.Popen(
            [
                "/opt/homebrew/opt/postgresql@16/bin/psql",
                "-h",
                "127.0.0.1",
                "-p",
                "55441",
                "-U",
                "candidate_t03",
                "-d",
                self.db,
                "-v",
                "ON_ERROR_STOP=1",
                "-X",
                "-q",
                "-tA",
                "-c",
                sql,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        holder.kill()
        holder.wait()
        staging, sealed = self.make_batch(
            "dr",
            "batch-dr",
            [self.row("JS-9", "项目R", "2026-06-01T00:00:00Z")],
        )
        receipt = importer.import_sealed(staging, sealed, self.db)
        self.assertEqual(receipt["status"], "committed")
        ghosts = self.query(
            "SELECT count(*) FROM source_records WHERE identity_key LIKE '%GHOST%';"
        )[0]
        self.assertEqual(ghosts, "0")


if __name__ == "__main__":
    unittest.main()
