"""T03 migration cases, executed on the isolated candidate PostgreSQL 16 cluster.

The cluster is TCP-loopback only (127.0.0.1:55441); legacy endpoint /tmp:55432
is never touched. Every test runs against a throwaway database.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pg_candidate
import run_migrations
from contract import identity_key

SIDE = Path(__file__).resolve().parent
MIGRATIONS = SIDE / "migrations"
LEGACY_FIXTURE = SIDE / "tests" / "legacy_replica.sql"


def errdup(exc: Exception) -> str:
    return str(exc)


class MigrationTests(unittest.TestCase):
    db: str

    @classmethod
    def setUpClass(cls) -> None:
        pg_candidate.init_cluster()

    def setUp(self) -> None:
        self.db = "t03_" + self.id().split(".")[-1]
        pg_candidate.drop_database(self.db)
        pg_candidate.create_database(self.db)
        self.addCleanup(pg_candidate.drop_database, self.db)

    def run_migrations(self, directory: Path | None = None) -> int:
        return run_migrations.run(
            self.db, directory or MIGRATIONS, __import__("sys").stdout
        )

    def query(self, sql: str) -> list[str]:
        return [
            line
            for line in pg_candidate.psql(self.db, sql).stdout.splitlines()
            if line.strip()
        ]

    def expect_error(self, sql: str, fragment: str) -> None:
        with self.assertRaises(pg_candidate.ClusterError) as ctx:
            pg_candidate.psql(self.db, sql)
        self.assertIn(fragment, str(ctx.exception))

    def seed_model(self) -> None:
        self.run_migrations()
        self.query("INSERT INTO providers (provider_name) VALUES ('集思未来');")
        self.query(
            "INSERT INTO sources (source_code, provider_id, namespace) "
            "VALUES ('jisi_sou_tools', (SELECT provider_id FROM providers "
            "WHERE provider_name='集思未来'), 'sou_tools');"
        )
        src = self.query(
            "SELECT source_id FROM sources WHERE source_code='jisi_sou_tools';"
        )[0]
        self.query(
            "INSERT INTO source_records (source_id, identity_key) VALUES "
            f"({src}, '{identity_key('jisi_sou_tools', 'JS-001')}');"
        )
        self.query(
            "INSERT INTO source_records (source_id, identity_key) VALUES "
            f"({src}, '{identity_key('jisi_sou_tools', 'JS-002')}');"
        )
        self.query(
            "INSERT INTO ingest_batches (batch_id, source_id, manifest_digest, "
            "contract_version, capture_mode, captured_at, observed_order, coverage, "
            "adapter_version, mapping_version, hash_version) VALUES "
            "('b1', " + src + ", 'dig1', '1', 'full', '2026-06-02T07:52:16Z', "
            "null, 'complete', 'a1', 'm1', 'h1'), "
            "('b2', " + src + ", 'dig2', '1', 'full', '2026-07-03T09:55:05Z', "
            "null, 'complete', 'a1', 'm1', 'h1');"
        )
        self.query(
            "INSERT INTO content_payloads (payload_hash, hash_version) VALUES "
            "('pA', 'h1'), ('pB', 'h1');"
        )
        self.query(
            "INSERT INTO observations (source_record_id, payload_id, batch_id, "
            "context_key, order_key, evidence_location) "
            "SELECT r.source_record_id, p.payload_id, 'b1', 'default', "
            "'2026-06-02T07:52:16Z', 'row:1' "
            "FROM source_records r, content_payloads p "
            "WHERE r.identity_key LIKE '%JS-001%' AND p.payload_hash='pA';"
        )
        self.query(
            "INSERT INTO observations (source_record_id, payload_id, batch_id, "
            "context_key, order_key, evidence_location) "
            "SELECT r.source_record_id, p.payload_id, 'b2', 'default', "
            "'2026-07-03T09:55:05Z', 'row:2' "
            "FROM source_records r, content_payloads p "
            "WHERE r.identity_key LIKE '%JS-002%' AND p.payload_hash='pB';"
        )

    def test_empty_database_bootstrap(self) -> None:
        self.assertEqual(self.run_migrations(), run_migrations.EXIT_OK)
        versions = self.query("SELECT version FROM schema_migrations ORDER BY version;")
        self.assertEqual(versions, ["0001", "0002", "0003"])
        status = self.query(
            "SELECT legacy_replica_present FROM legacy_bridge_status WHERE bridge='0002';"
        )
        self.assertEqual(status, ["f"], "bridge must explicitly record empty bootstrap")

    def test_rerun_is_noop(self) -> None:
        self.run_migrations()
        before = self.query(
            "SELECT version, checksum FROM schema_migrations ORDER BY version;"
        )
        self.assertEqual(self.run_migrations(), run_migrations.EXIT_OK)
        after = self.query(
            "SELECT version, checksum FROM schema_migrations ORDER BY version;"
        )
        self.assertEqual(before, after)

    def test_checksum_conflict_rejected(self) -> None:
        self.run_migrations()
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        for sql in sorted(MIGRATIONS.glob("*.sql")):
            shutil.copy(sql, temp / sql.name)
        (temp / "0001_candidate_model.sql").write_text(
            (MIGRATIONS / "0001_candidate_model.sql").read_text(encoding="utf-8")
            + "\n-- tampered\n",
            encoding="utf-8",
        )
        code = run_migrations.run(self.db, temp, __import__("sys").stdout)
        self.assertEqual(code, run_migrations.EXIT_CHECKSUM_CONFLICT)

    def test_legacy_replica_upgrade(self) -> None:
        pg_candidate.psql_file(self.db, LEGACY_FIXTURE)
        self.assertEqual(self.run_migrations(), run_migrations.EXIT_OK)
        counts = self.query(
            "SELECT migrated_counts::text FROM legacy_bridge_status WHERE bridge='0002';"
        )[0]
        data = json.loads(counts)
        self.assertEqual(
            data,
            {
                "providers": 1,
                "providers_merged_by_name": 0,
                "sources": 2,
                "ingest_batches": 2,
                "ingest_batches_unmigrated_null_source": 0,
                "source_records": 3,
                "observations": 4,
                "provider_projects": 2,
                "project_source_links": 3,
                "offerings": 2,
            },
        )
        mapped = self.query(
            "SELECT count(*) FROM legacy_id_map WHERE legacy_table='source_project_records';"
        )[0]
        self.assertEqual(mapped, "3")
        aba = self.query(
            "SELECT count(*) FROM observations o "
            "JOIN legacy_id_map m ON m.new_table='source_records' "
            "AND m.new_id::bigint=o.source_record_id "
            "WHERE m.legacy_id='30000000-0000-0000-0000-000000000001';"
        )[0]
        self.assertEqual(aba, "3", "A→B→A must keep three observations")
        expected_identity = identity_key("jisi_sou_tools", "JS-001")
        match = self.query(
            "SELECT count(*) FROM source_records WHERE identity_key="
            f"'{expected_identity}';"
        )[0]
        self.assertEqual(match, "1", "bridge identity must equal contract encoding")

    def test_duplicate_source_identity_rejected(self) -> None:
        self.seed_model()
        src = self.query(
            "SELECT source_id FROM sources WHERE source_code='jisi_sou_tools';"
        )[0]
        self.expect_error(
            "INSERT INTO source_records (source_id, identity_key) VALUES "
            f"({src}, '{identity_key('jisi_sou_tools', 'JS-001')}');",
            "duplicate key",
        )

    def test_illegal_observation_reference_rejected(self) -> None:
        self.seed_model()
        self.expect_error(
            "INSERT INTO observations (source_record_id, payload_id, batch_id, "
            "evidence_location) VALUES (999999, 1, 'b1', 'row:x');",
            "violates foreign key",
        )

    def test_current_pointer_same_record_only(self) -> None:
        self.seed_model()
        rec1, rec2, obs1, obs2 = self.query(
            "SELECT r1.source_record_id, r2.source_record_id, "
            "o1.observation_id, o2.observation_id "
            "FROM source_records r1, source_records r2, "
            "observations o1, observations o2 "
            "WHERE r1.identity_key LIKE '%JS-001%' AND r2.identity_key LIKE '%JS-002%' "
            "AND o1.source_record_id=r1.source_record_id "
            "AND o2.source_record_id=r2.source_record_id;"
        )[0].split("|")
        self.assertNotEqual(rec1.strip(), rec2.strip())
        self.expect_error(
            "INSERT INTO source_record_current (source_record_id, observation_id) "
            f"VALUES ({rec1.strip()}, {obs2.strip()});",
            "violates foreign key",
        )
        self.query(
            "INSERT INTO source_record_current (source_record_id, observation_id) "
            f"VALUES ({rec1.strip()}, {obs1.strip()});"
        )
        count = self.query("SELECT count(*) FROM source_record_current;")[0]
        self.assertEqual(count, "1")

    def test_batch_immutable(self) -> None:
        self.seed_model()
        self.expect_error(
            "UPDATE ingest_batches SET coverage='partial' WHERE batch_id='b1';",
            "ingest_batches is immutable",
        )
        self.expect_error(
            "DELETE FROM ingest_batches WHERE batch_id='b1';",
            "ingest_batches is immutable",
        )

    def test_offering_field_state_check(self) -> None:
        self.seed_model()
        self.query(
            "INSERT INTO provider_projects (provider_id, native_project_key) "
            "SELECT provider_id, 'PP-1' FROM providers LIMIT 1;"
        )
        self.expect_error(
            "INSERT INTO offerings (provider_project_id, offering_key, field_state) "
            "SELECT provider_project_id, 'OFF-X', 'guessed' FROM provider_projects "
            "WHERE native_project_key='PP-1';",
            "violates check constraint",
        )
        for state in ("value", "explicitly_empty", "not_provided", "extraction_failed"):
            self.query(
                "INSERT INTO offerings (provider_project_id, offering_key, field_state) "
                "SELECT provider_project_id, 'OFF-" + state + "', '" + state + "' "
                "FROM provider_projects WHERE native_project_key='PP-1';"
            )

    def test_migration_interrupt_and_recovery(self) -> None:
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        for sql in sorted(MIGRATIONS.glob("*.sql")):
            shutil.copy(sql, temp / sql.name)
        (temp / "0004_interrupted.sql").write_text(
            "CREATE TABLE partial_artifact (x int);\n"
            "INSERT INTO table_that_does_not_exist VALUES (1);\n",
            encoding="utf-8",
        )
        code = run_migrations.run(self.db, temp, __import__("sys").stdout)
        self.assertEqual(code, run_migrations.EXIT_SQL_ERROR)
        ledger = self.query("SELECT version FROM schema_migrations ORDER BY version;")
        self.assertEqual(ledger, ["0001", "0002", "0003"])
        artifact = self.query("SELECT to_regclass('partial_artifact') IS NOT NULL;")[0]
        self.assertEqual(artifact, "f", "failed migration must roll back completely")
        (temp / "0004_interrupted.sql").unlink()
        self.assertEqual(
            run_migrations.run(self.db, temp, __import__("sys").stdout),
            run_migrations.EXIT_OK,
        )
        final = self.query("SELECT count(*) FROM schema_migrations;")[0]
        self.assertEqual(final, "3")


if __name__ == "__main__":
    unittest.main()
