"""R2 full-corpus search golden cases: integrity, equality, pagination
determinism on multi-payload records, per-call latency and frozen-artifact
protection."""

from __future__ import annotations

import hashlib
import json
import time
import unittest
from pathlib import Path

import pg_candidate
from search import search

SIDE = Path(__file__).resolve().parent
GOLDEN = json.loads(
    (SIDE / "fixtures" / "t11_golden_full.json").read_text(encoding="utf-8")
)
PILOT_GOLDEN = SIDE / "fixtures" / "t11_golden.json"
DB = "candidate_full_1"


def _collect(db: str, params: dict) -> tuple[list[str], int]:
    params = dict(params)
    params["page_size"] = 100
    params["page"] = 1
    got: list[str] = []
    total = None
    while True:
        result = search(db, params)
        total = result["total"]
        got.extend(card["identity_key"] for card in result["cards"])
        if len(got) >= total or not result["cards"]:
            break
        params["page"] += 1
    return got, total


class SearchFullGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pg_candidate.init_cluster()
        if not pg_candidate.database_exists(DB):
            raise unittest.SkipTest("full corpus database missing")

    def test_golden_loads_with_20_queries(self) -> None:
        self.assertEqual(len(GOLDEN["queries"]), 20)
        ids = [q["id"] for q in GOLDEN["queries"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_query_structure_contract(self) -> None:
        for query in GOLDEN["queries"]:
            self.assertIn("params", query, query["id"])
            self.assertIn("expected_identities", query, query["id"])
            self.assertIn("expected_total", query, query["id"])
            self.assertEqual(
                query["expected_total"], len(query["expected_identities"]), query["id"]
            )
            self.assertEqual(
                len(query["expected_identities"]),
                len(set(query["expected_identities"])),
                query["id"],
            )
            self.assertEqual(
                query["expected_identities"],
                sorted(query["expected_identities"]),
                query["id"],
            )

    def test_corpus_metadata_matches_live_db(self) -> None:
        records = int(
            pg_candidate.psql(DB, "SELECT count(*) FROM source_records;").stdout.strip()
        )
        observations = int(
            pg_candidate.psql(DB, "SELECT count(*) FROM observations;").stdout.strip()
        )
        self.assertEqual(GOLDEN["corpus"]["database"], DB)
        self.assertEqual(GOLDEN["corpus"]["records"], records)
        self.assertEqual(GOLDEN["corpus"]["observations"], observations)

    def test_golden_queries_exact_equality(self) -> None:
        for query in GOLDEN["queries"]:
            got, total = _collect(DB, query["params"])
            self.assertEqual(
                sorted(set(got)), sorted(query["expected_identities"]), query["id"]
            )
            self.assertEqual(total, query["expected_total"], query["id"])

    def test_pagination_no_duplicates_or_gaps_multi_payload(self) -> None:
        """Regression for the DISTINCT-granularity defect exposed by the
        full corpus: q09 (jisi_future_domestic) contains multi-payload
        records; pages must partition identities exactly."""
        query = next(q for q in GOLDEN["queries"] if q["id"] == "q09_source_domestic")
        multi_payload = int(
            pg_candidate.psql(
                DB,
                "SELECT count(*) FROM (SELECT o.source_record_id FROM observations o "
                "JOIN source_records r ON r.source_record_id = o.source_record_id "
                "JOIN sources s ON s.source_id = r.source_id "
                "WHERE s.source_code = 'jisi_future_domestic' "
                "GROUP BY o.source_record_id HAVING count(*) > 1) d;",
            ).stdout.strip()
        )
        self.assertGreater(
            multi_payload, 0, "precondition: multi-payload records must exist"
        )
        seen: list[str] = []
        page = 1
        while True:
            result = search(
                DB, {"source": "jisi_future_domestic", "page": page, "page_size": 97}
            )
            page_ids = [c["identity_key"] for c in result["cards"]]
            self.assertEqual(
                len(page_ids),
                len(set(page_ids)),
                f"page {page} has duplicate identities",
            )
            seen.extend(page_ids)
            if not result["cards"] or len(seen) >= result["total"]:
                break
            page += 1
        self.assertEqual(
            sorted(seen), sorted(set(seen)), "duplicate identities across pages"
        )
        self.assertEqual(len(seen), query["expected_total"])

    def test_cards_one_per_identity(self) -> None:
        result = search(DB, {"page_size": 100})
        ids = [c["identity_key"] for c in result["cards"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_multi_payload_records_exist_in_full_corpus(self) -> None:
        rows = int(
            pg_candidate.psql(DB, "SELECT count(*) FROM observations;").stdout.strip()
        )
        payloads_per_record = int(
            pg_candidate.psql(
                DB,
                "SELECT count(*) FROM (SELECT source_record_id FROM observations "
                "GROUP BY source_record_id HAVING count(DISTINCT payload_id) > 1) d;",
            ).stdout.strip()
        )
        self.assertGreater(rows, 9000)
        self.assertGreater(payloads_per_record, 0)

    def test_per_call_p95_under_budget(self) -> None:
        durations = []
        for query in GOLDEN["queries"]:
            params = dict(query["params"])
            params["page_size"] = 100
            params["page"] = 1
            start = time.perf_counter()
            search(DB, params)
            durations.append(time.perf_counter() - start)
        p95 = sorted(durations)[max(0, int(len(durations) * 0.95) - 1)]
        self.assertLess(p95, 1.0, f"per-call p95 {p95:.4f}s exceeds 1s budget")

    def test_pilot_golden_frozen_untouched(self) -> None:
        ledger = json.loads(
            (SIDE / "candidate_hashes.json").read_text(encoding="utf-8")
        )
        expected = ledger.get("fixtures/t11_golden.json")
        self.assertIsNotNone(expected, "pilot golden must stay ledger-registered")
        self.assertEqual(
            hashlib.sha256(PILOT_GOLDEN.read_bytes()).hexdigest(),
            expected,
            "pilot golden changed; frozen artifacts must stay byte-identical",
        )


if __name__ == "__main__":
    unittest.main()
