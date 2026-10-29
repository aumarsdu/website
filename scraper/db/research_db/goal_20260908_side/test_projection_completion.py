"""R3 run-granularity not_seen and R5 candidate-identity queue cases.

Synthetic registry + staging fixtures against a real per-test candidate
database; report functions are read-only by contract and the tests assert
that too.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import contract
import pg_candidate
import projection
from projection import ProjectionError

SIDE = Path(__file__).resolve().parent


def _write_staging(root: Path, source: str, batch: str, ids: list[str]) -> None:
    staging = root / batch / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    rows = [{"id": native, "title": f"t-{native}"} for native in ids]
    (staging / "records.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


class NotSeenRunReportTests(unittest.TestCase):
    db: str
    registry: dict
    staging_root: Path

    @classmethod
    def setUpClass(cls) -> None:
        pg_candidate.init_cluster()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.db = "r3_" + self.id().split(".")[-1][:40]
        pg_candidate.drop_database(self.db)
        pg_candidate.create_database(self.db)
        self.addCleanup(pg_candidate.drop_database, self.db)
        import run_migrations

        self.assertEqual(
            run_migrations.run(self.db, SIDE / "migrations", __import__("sys").stdout),
            run_migrations.EXIT_OK,
        )
        self.staging_root = self.work / "staging_root"
        self.staging_root.mkdir()
        # test_source_a: 0602 refresh {a1,a2}; 0703 refresh {a1,a3,a4};
        # 0724 incremental {a5}. a2 disappears between refreshes; a5 is an
        # incremental-only addition.
        self.inputs = [
            {
                "relative_path": "t/output/full_refresh/20260602/rows.jsonl",
                "unit_count": 2,
            },
            {
                "relative_path": "t/output/full_refresh/20260703/rows.jsonl",
                "unit_count": 3,
            },
            {
                "relative_path": "t/output/incremental/20260724/rows.jsonl",
                "unit_count": 1,
            },
        ]
        _write_staging(
            self.staging_root,
            "test_source_a",
            "test_source_a-001",
            ["a1", "a2", "a1", "a3", "a4", "a5"],
        )
        self.registry = {
            "sources": [
                {
                    "source_code": "test_source_a",
                    "inputs": self.inputs,
                }
            ]
        }
        pg_candidate.psql(
            self.db, "INSERT INTO providers (provider_name) VALUES ('t');"
        )
        pg_candidate.psql(
            self.db,
            "INSERT INTO sources (source_code, provider_id, namespace) "
            "SELECT 'test_source_a', provider_id, 'ns' FROM providers "
            "WHERE provider_name = 't';",
        )
        for native in ("a1", "a2", "a3", "a4", "a5"):
            identity = contract.identity_key("test_source_a", native)
            pg_candidate.psql(
                self.db,
                f"INSERT INTO source_records (source_id, identity_key, "
                f"identity_status) SELECT source_id, "
                f"{projection._dquote(identity)}, 'confirmed' FROM sources "
                f"WHERE source_code = 'test_source_a';",
            )

    def _report(self, **kwargs: object) -> dict:
        return projection.not_seen_run_report(
            self.db,
            "test_source_a",
            registry=self.registry,
            staging_root=self.staging_root,
            **kwargs,  # type: ignore[arg-type]
        )

    def test_incremental_baseline_rejected(self) -> None:
        with self.assertRaises(ProjectionError) as ctx:
            self._report(baseline_input="t/output/incremental/20260724/rows.jsonl")
        self.assertEqual(str(ctx.exception), "incremental_run_not_a_baseline")

    def test_unknown_baseline_rejected(self) -> None:
        with self.assertRaises(ProjectionError) as ctx:
            self._report(baseline_input="t/missing.jsonl")
        self.assertEqual(str(ctx.exception), "unknown_baseline_input")

    def test_unknown_source_rejected(self) -> None:
        with self.assertRaises(ProjectionError) as ctx:
            projection.not_seen_run_report(
                self.db, "no_such_source", registry=self.registry
            )
        self.assertEqual(str(ctx.exception), "unknown_source")

    def test_default_baseline_is_latest_full_refresh(self) -> None:
        report = self._report()
        self.assertEqual(
            report["baseline_input"], "t/output/full_refresh/20260703/rows.jsonl"
        )
        self.assertEqual(report["baseline_run_type"], "full_refresh")

    def test_not_seen_buckets_split_disappearance_and_incremental_add(self) -> None:
        report = self._report()
        disappeared = contract.identity_key("test_source_a", "a2")
        incremental_add = contract.identity_key("test_source_a", "a5")
        self.assertEqual(report["not_seen_count"], 2)
        self.assertEqual(report["not_sighted_after_baseline"], [disappeared])
        self.assertEqual(report["sighted_after_baseline"], [incremental_add])
        self.assertIn("t/output/incremental/20260724/rows.jsonl", report["later_runs"])

    def test_missing_unit_count_rejected(self) -> None:
        broken = {
            "sources": [
                {
                    "source_code": "test_source_a",
                    "inputs": [
                        {"relative_path": "t/output/full_refresh/20260602/rows.jsonl"}
                    ],
                }
            ]
        }
        with self.assertRaises(ProjectionError) as ctx:
            projection.not_seen_run_report(
                self.db,
                "test_source_a",
                registry=broken,
                staging_root=self.staging_root,
            )
        self.assertEqual(str(ctx.exception), "registry_input_missing_unit_count")

    def test_explicit_old_refresh_baseline(self) -> None:
        report = self._report(
            baseline_input="t/output/full_refresh/20260602/rows.jsonl"
        )
        self.assertEqual(report["not_seen_count"], 3)
        self.assertEqual(report["baseline_unit_count"], 2)

    def test_single_input_source_zero_not_seen(self) -> None:
        _write_staging(
            self.staging_root, "test_source_b", "test_source_b-001", ["b1", "b2"]
        )
        registry = {
            "sources": [
                *self.registry["sources"],
                {
                    "source_code": "test_source_b",
                    "inputs": [
                        {
                            "relative_path": "t/output/processed/all.jsonl",
                            "unit_count": 2,
                        }
                    ],
                },
            ]
        }
        pg_candidate.psql(
            self.db,
            "INSERT INTO sources (source_code, provider_id, namespace) "
            "SELECT 'test_source_b', provider_id, 'nsb' FROM providers "
            "WHERE provider_name = 't';",
        )
        for native in ("b1", "b2"):
            pg_candidate.psql(
                self.db,
                f"INSERT INTO source_records (source_id, identity_key, "
                f"identity_status) SELECT source_id, "
                f"{projection._dquote(contract.identity_key('test_source_b', native))}, "
                f"'confirmed' FROM sources WHERE source_code = 'test_source_b';",
            )
        report = projection.not_seen_run_report(
            self.db,
            "test_source_b",
            registry=registry,
            staging_root=self.staging_root,
        )
        self.assertEqual(report["baseline_run_type"], "complete_single_file")
        self.assertEqual(report["not_seen_count"], 0)

    def test_staging_registry_misaligned_rejected(self) -> None:
        broken = {
            "sources": [
                {
                    "source_code": "test_source_a",
                    "inputs": [*self.inputs[:-1]],
                }
            ]
        }
        with self.assertRaises(ProjectionError) as ctx:
            projection.not_seen_run_report(
                self.db,
                "test_source_a",
                registry=broken,
                staging_root=self.staging_root,
            )
        self.assertEqual(str(ctx.exception), "staging_registry_misaligned")

    def test_report_is_readonly(self) -> None:
        before = int(
            pg_candidate.psql(
                self.db, "SELECT count(*) FROM quality_issues;"
            ).stdout.strip()
        )
        self._report()
        after = int(
            pg_candidate.psql(
                self.db, "SELECT count(*) FROM quality_issues;"
            ).stdout.strip()
        )
        self.assertEqual(before, after)
        self.assertTrue(self._report()["readonly"])


class CandidateIdentityQueueTests(unittest.TestCase):
    db: str

    @classmethod
    def setUpClass(cls) -> None:
        pg_candidate.init_cluster()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = "r5_" + self.id().split(".")[-1][:40]
        pg_candidate.drop_database(self.db)
        pg_candidate.create_database(self.db)
        self.addCleanup(pg_candidate.drop_database, self.db)
        import run_migrations

        self.assertEqual(
            run_migrations.run(self.db, SIDE / "migrations", __import__("sys").stdout),
            run_migrations.EXIT_OK,
        )
        pg_candidate.psql(
            self.db, "INSERT INTO providers (provider_name) VALUES ('t');"
        )
        pg_candidate.psql(
            self.db,
            "INSERT INTO sources (source_code, provider_id, namespace) "
            "SELECT 'src_c', provider_id, 'ns' FROM providers "
            "WHERE provider_name = 't';",
        )
        for native, status in (
            ("c1", "candidate"),
            ("c2", "candidate"),
            ("c3", "confirmed"),
        ):
            pg_candidate.psql(
                self.db,
                f"INSERT INTO source_records (source_id, identity_key, "
                f"identity_status) SELECT source_id, "
                f"{projection._dquote(contract.identity_key('src_c', native))}, "
                f"'{status}' FROM sources WHERE source_code = 'src_c';",
            )

    def test_candidate_identities_surface_in_queue(self) -> None:
        queue = projection.quality_queue(self.db)
        candidates = [item for item in queue if item["kind"] == "identity_candidate"]
        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            sorted(item["identity_key"] for item in candidates),
            sorted(contract.identity_key("src_c", native) for native in ("c1", "c2")),
        )

    def test_confirmed_identities_absent_from_queue(self) -> None:
        queue = projection.quality_queue(self.db)
        confirmed = contract.identity_key("src_c", "c3")
        self.assertNotIn(confirmed, [item.get("identity_key") for item in queue])

    def test_candidate_queue_carries_source_and_status(self) -> None:
        queue = projection.quality_queue(self.db)
        item = next(i for i in queue if i["kind"] == "identity_candidate")
        self.assertEqual(item["source_code"], "src_c")
        self.assertEqual(item["current_status"], "absent")

    def test_existing_queue_kinds_unchanged(self) -> None:
        pg_candidate.psql(
            self.db,
            "INSERT INTO quality_issues (entity_kind, entity_id, severity, "
            "description) VALUES ('source_record', 1, 'P2', 'probe');",
        )
        queue = projection.quality_queue(self.db)
        kinds = {item["kind"] for item in queue}
        self.assertIn("quality_issue", kinds)
        self.assertIn("identity_candidate", kinds)


if __name__ == "__main__":
    unittest.main()
