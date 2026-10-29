"""T04 adapter cases against frozen sample expectations and semantics."""

import json
import random
import unittest
from pathlib import Path

from adapters import ADAPTER_CONFIG, AdapterError, adapt_row, adapt_rows
from contract import identity_key

SIDE = Path(__file__).resolve().parent
FROZEN = json.loads(
    (SIDE / "fixtures" / "t04" / "t04_expected.json").read_text(encoding="utf-8")
)
ENTRIES = [
    "jisi_future_sou_tools",
    "jisi_future_domestic",
    "zhongke",
    "hirep",
]


def load_samples(entry: str) -> list[dict]:
    path = SIDE / "fixtures" / "t04" / entry / "samples.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class AdapterTests(unittest.TestCase):
    def test_config_matches_frozen(self) -> None:
        for entry in ENTRIES:
            self.assertEqual(
                ADAPTER_CONFIG[entry],
                FROZEN["entries"][entry]["config"],
                entry,
            )

    def test_frozen_expectations_matched_item_by_item(self) -> None:
        for entry in ENTRIES:
            samples = load_samples(entry)
            expectations = FROZEN["entries"][entry]["expectations"]
            self.assertEqual(len(samples), len(expectations), entry)
            self.assertGreaterEqual(len(samples), 10, entry)
            for sample, expected in zip(samples, expectations):
                adapted = adapt_row(entry, sample)
                self.assertEqual(adapted["native_id"], expected["native_id"], entry)
                self.assertEqual(
                    adapted["field_states"], expected["field_states"], entry
                )
                self.assertEqual(adapted["order_key"], expected["order_key"], entry)
                for field, state in expected["field_states"].items():
                    if state == "value":
                        self.assertEqual(
                            adapted["staging_row"].get(field),
                            expected["business"][field],
                            (entry, field),
                        )
                    else:
                        self.assertNotIn(field, adapted["staging_row"], (entry, field))

    def test_identity_separated_across_entries(self) -> None:
        samples = load_samples("hirep")
        native = samples[0]["business_id"]
        keys = {identity_key(entry, native) for entry in ENTRIES}
        self.assertEqual(len(keys), len(ENTRIES))

    def test_same_entry_two_runs_one_identity(self) -> None:
        sample = load_samples("jisi_future_sou_tools")[0]
        first = adapt_row("jisi_future_sou_tools", sample)
        rerun = dict(sample)
        rerun["crawled_at"] = "2026-07-03T09:55:05Z"
        second = adapt_row("jisi_future_sou_tools", rerun)
        self.assertEqual(first["identity_key"], second["identity_key"])
        self.assertNotEqual(first["order_key"], second["order_key"])

    def test_disorder_invariant(self) -> None:
        entry = "zhongke"
        samples = load_samples(entry)
        forward = adapt_rows(entry, samples)
        shuffled = list(samples)
        random.Random(7).shuffle(shuffled)
        backward = adapt_rows(entry, shuffled)
        self.assertEqual(
            {m["identity_key"] for m in forward["mapped"]},
            {m["identity_key"] for m in backward["mapped"]},
        )
        self.assertEqual(forward["counts"]["rows_in"], backward["counts"]["rows_in"])

    def test_counts_reconcile(self) -> None:
        for entry in ENTRIES:
            result = adapt_rows(entry, load_samples(entry))
            self.assertEqual(
                result["counts"],
                {
                    "rows_in": len(load_samples(entry)),
                    "mapped": len(load_samples(entry)),
                    "unmapped": 0,
                },
                entry,
            )

    def test_missing_id_counted_not_dropped(self) -> None:
        result = adapt_rows("hirep", [{"title": "no id here"}])
        self.assertEqual(result["counts"], {"rows_in": 1, "mapped": 0, "unmapped": 1})
        self.assertEqual(result["unmapped"], 1)

    def test_added_unknown_field_no_version_change(self) -> None:
        sample = load_samples("hirep")[0]
        base = adapt_row("hirep", sample)
        noisy = dict(sample)
        noisy["internal_note"] = "secret"
        noisy["tracking"] = "abc?utm=x"
        same = adapt_row("hirep", noisy)
        self.assertEqual(base["staging_row"], same["staging_row"])

    def test_changed_title_detectable(self) -> None:
        sample = load_samples("hirep")[0]
        base = adapt_row("hirep", sample)
        changed_row = dict(sample)
        changed_row["title"] = base["staging_row"]["title"] + "（更新）"
        changed = adapt_row("hirep", changed_row)
        self.assertNotEqual(
            base["staging_row"]["title"], changed["staging_row"]["title"]
        )

    def test_uncertain_instructor_never_invented(self) -> None:
        row = {"business_id": "H1", "title": "T"}
        adapted = adapt_row("hirep", row)
        self.assertEqual(adapted["field_states"]["instructor"], "not_provided")
        self.assertNotIn("instructor", adapted["staging_row"])
        a = adapt_row("hirep", {"business_id": "H1", "title": "T", "professor": "张三"})
        b = adapt_row(
            "hirep", {"business_id": "H2", "title": "T2", "professor": "张三"}
        )
        self.assertEqual(a["staging_row"]["instructor"], "张三")
        self.assertEqual(b["staging_row"]["instructor"], "张三")
        self.assertNotEqual(a["identity_key"], b["identity_key"])

    def test_unconfigured_entry_rejected(self) -> None:
        with self.assertRaisesRegex(AdapterError, "entry_not_configured"):
            adapt_row("unknown_entry", {})

    def test_same_native_id_across_runs_traced(self) -> None:
        """Full refresh and incremental rows of one id keep one identity."""
        sample = load_samples("jisi_future_domestic")[0]
        incremental = dict(sample)
        incremental["crawled_at"] = "2026-09-02T04:12:23Z"
        first = adapt_row("jisi_future_domestic", sample)
        second = adapt_row("jisi_future_domestic", incremental)
        self.assertEqual(first["native_id"], second["native_id"])
        self.assertIsNotNone(first["native_id"])
        self.assertEqual(first["identity_key"], second["identity_key"])


if __name__ == "__main__":
    unittest.main()
