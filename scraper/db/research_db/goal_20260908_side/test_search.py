"""T11 search cases: golden equality, pagination, recall, p95, rejections."""

import json
import statistics
import time
import unittest
from pathlib import Path

import pg_candidate
from search import SearchError, search

SIDE = Path(__file__).resolve().parent
GOLDEN = json.loads((SIDE / "fixtures" / "t11_golden.json").read_text(encoding="utf-8"))
DB = "candidate_corpus"


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pg_candidate.init_cluster()
        if not pg_candidate.database_exists(DB):
            raise unittest.SkipTest("corpus database missing")

    def test_golden_queries_exact_equality(self) -> None:
        for query in GOLDEN["queries"]:
            params = dict(query["params"])
            params["page_size"] = 100
            params["page"] = 1
            got: list[str] = []
            total = None
            while True:
                result = search(DB, params)
                total = result["total"]
                got.extend(c["identity_key"] for c in result["cards"])
                if len(got) >= total or not result["cards"]:
                    break
                params["page"] += 1
            self.assertEqual(
                sorted(got), sorted(query["expected_identities"]), query["id"]
            )
            self.assertEqual(total, query["expected_total"], query["id"])

    def test_empty_page_reports_accurate_total(self) -> None:
        result = search(DB, {"q": "人工智能", "page": 99, "page_size": 20})
        self.assertEqual(result["cards"], [])
        self.assertEqual(result["total"], 15)

    def test_pagination_no_duplicates_or_gaps(self) -> None:
        seen: list[str] = []
        page = 1
        while True:
            result = search(DB, {"q": "人工智能", "page": page, "page_size": 4})
            seen.extend(c["identity_key"] for c in result["cards"])
            if not result["cards"] or len(seen) >= result["total"]:
                break
            page += 1
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), 15)

    def test_top10_recall(self) -> None:
        """Rank cards by title position against the golden set (Top-10 >=90%)."""
        query = next(q for q in GOLDEN["queries"] if q["id"] == "q01_ai")
        expected = set(query["expected_identities"])
        result = search(DB, {"q": "人工智能", "page_size": 100})
        top10 = [c["identity_key"] for c in result["cards"]][:10]
        relevant = sum(1 for identity in top10 if identity in expected)
        denominator = min(10, len(expected))
        recall = relevant / denominator
        self.assertGreaterEqual(recall, 0.9)

    def test_sort_whitelist_enforced(self) -> None:
        with self.assertRaisesRegex(SearchError, "contract_invalid"):
            search(DB, {"sort": "(SELECT 1); DROP TABLE users;"})
        with self.assertRaisesRegex(SearchError, "contract_invalid"):
            search(DB, {"sort": "title; DROP TABLE source_records"})

    def test_like_wildcards_escaped(self) -> None:
        result = search(DB, {"q": "100%"})
        self.assertEqual(result["total"], 0)

    def test_quote_in_query_rejected(self) -> None:
        with self.assertRaisesRegex(SearchError, "contract_invalid"):
            search(DB, {"q": "x' OR 1=1 --"})

    def test_no_public_routes(self) -> None:
        source = (SIDE / "search.py").read_text(encoding="utf-8")
        for marker in ("HTTPServer", "Flask", "FastAPI", "@app.", "route(", "listen("):
            self.assertNotIn(marker, source)

    def test_p95_under_one_second(self) -> None:
        timings: list[float] = []
        for query in GOLDEN["queries"]:
            params = dict(query["params"])
            params["page_size"] = 100
            search(DB, params)  # warmup
            for _ in range(5):
                start = time.perf_counter()
                search(DB, params)
                timings.append(time.perf_counter() - start)
        self.assertGreaterEqual(len(timings), 100)
        p95 = statistics.quantiles(timings, n=20)[18]
        self.assertLess(p95, 1.0, f"p95={p95:.4f}s")


if __name__ == "__main__":
    unittest.main()
