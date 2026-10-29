"""T08 staging validator cases against frozen fixture verdicts."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from stage_validator import (
    StageError,
    validate_and_seal,
    validate_only,
    verify_seal,
)

SIDE = Path(__file__).resolve().parent
FIXTURES = SIDE / "fixtures" / "t08"
EXPECTED = json.loads(
    (SIDE / "fixtures" / "t08_expected.json").read_text(encoding="utf-8")
)["cases"]


class StageValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def run_case(self, name: str) -> dict:
        target = self.work / name
        return validate_and_seal(FIXTURES / name, target)

    def assert_sealed_false(self, verdict: dict, error: str) -> None:
        self.assertFalse(verdict["sealed"])
        self.assertEqual(verdict["error"], error)

    def test_case_ok_sealed_with_frozen_verdict(self) -> None:
        verdict = self.run_case("case_ok")
        expected = EXPECTED["case_ok"]["expected"]
        self.assertTrue(verdict["sealed"])
        self.assertEqual(
            verdict["counts"],
            {
                "accepted": expected["accepted"],
                "duplicate": expected["duplicate"],
                "quarantined": expected["quarantined"],
                "rejected": expected["rejected"],
            },
        )
        self.assertEqual(verdict["rows_read"], expected["rows_read"])
        self.assertEqual(verdict["sealed_rows"], expected["sealed_rows"])

    def test_case_ok_scrubbed_output(self) -> None:
        self.run_case("case_ok")
        text = (self.work / "case_ok" / "batch.jsonl").read_text(encoding="utf-8")
        for forbidden in EXPECTED["case_ok"]["expected"]["scrubbed_fields_absent"]:
            self.assertNotIn(f'"{forbidden}"', text)

    def test_case_bad_json_count_mismatch(self) -> None:
        verdict = self.run_case("case_bad_json")
        self.assert_sealed_false(
            verdict, EXPECTED["case_bad_json"]["expected"]["error"]
        )
        self.assertFalse((self.work / "case_bad_json").exists())

    def test_case_truncated_detected(self) -> None:
        verdict = self.run_case("case_truncated")
        self.assert_sealed_false(
            verdict, EXPECTED["case_truncated"]["expected"]["error"]
        )

    def test_case_missing_file(self) -> None:
        verdict = self.run_case("case_missing_file")
        self.assert_sealed_false(
            verdict, EXPECTED["case_missing_file"]["expected"]["error"]
        )

    def test_case_hash_mismatch(self) -> None:
        verdict = self.run_case("case_hash_mismatch")
        self.assert_sealed_false(
            verdict, EXPECTED["case_hash_mismatch"]["expected"]["error"]
        )

    def test_case_empty_dir(self) -> None:
        verdict = self.run_case("case_empty_dir")
        self.assert_sealed_false(
            verdict, EXPECTED["case_empty_dir"]["expected"]["error"]
        )

    def test_case_observation_bad_refs(self) -> None:
        verdict = self.run_case("case_observations_bad_refs")
        self.assertFalse(verdict["sealed"])
        for error in EXPECTED["case_observations_bad_refs"]["expected"]["errors"]:
            self.assertIn(error, verdict["error"])

    def test_sealing_is_deterministic(self) -> None:
        self.run_case("case_ok")
        first = (self.work / "case_ok" / "seal.json").read_bytes()
        second_target = self.work / "case_ok_second"
        validate_and_seal(FIXTURES / "case_ok", second_target)
        second = (second_target / "seal.json").read_bytes()
        self.assertEqual(first, second)

    def test_seal_target_exists_rejected(self) -> None:
        self.run_case("case_ok")
        verdict = validate_and_seal(FIXTURES / "case_ok", self.work / "case_ok")
        self.assert_sealed_false(verdict, "seal_target_exists")

    def test_input_change_after_seal_voids_seal(self) -> None:
        staging = self.work / "mutable_staging"
        shutil.copytree(FIXTURES / "case_ok", staging)
        target = self.work / "mutable_target"
        verdict = validate_and_seal(staging, target)
        self.assertTrue(verdict["sealed"])
        verify_seal(staging, target)
        records = staging / "records.jsonl"
        records.write_text(
            records.read_text(encoding="utf-8").replace("项目A", "项目Y"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(StageError, "input_changed"):
            verify_seal(staging, target)

    def test_no_temp_leftover_on_failure(self) -> None:
        self.run_case("case_bad_json")
        leftovers = [
            p.name for p in self.work.iterdir() if p.name.startswith(".tmp-seal-")
        ]
        self.assertEqual(leftovers, [])

    def test_dry_run_creates_no_target(self) -> None:
        verdict = validate_only(FIXTURES / "case_ok")
        self.assertTrue(verdict["would_seal"])
        self.assertEqual(verdict["sealed_rows"], 2)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_traversal_and_symlink_inputs_rejected(self) -> None:
        staging = self.work / "evil_staging"
        shutil.copytree(FIXTURES / "case_ok", staging)
        outside = self.work / "outside.jsonl"
        outside.write_text("{}\n", encoding="utf-8")
        (staging / "link.jsonl").symlink_to(outside)
        manifest_path = staging / "manifest.json"
        for relative in ("../outside.jsonl", "link.jsonl"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["input_files"].append(
                {
                    "relative_path": relative,
                    "sha256": "0" * 64,
                    "byte_size": 3,
                    "row_count": 1,
                    "format": "jsonl",
                    "role": "fact",
                }
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
            verdict = validate_only(staging)
            self.assertFalse(verdict["sealed"])
            self.assertEqual(verdict["error"], "contract_invalid")

    def test_valid_observations_pass(self) -> None:
        import hashlib

        from contract import payload_hash

        staging = self.work / "obs_ok_staging"
        shutil.copytree(FIXTURES / "case_ok", staging)
        manifest_path = staging / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = [
            json.loads(line)
            for line in (staging / "records.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        wl = json.loads(
            Path(__file__).with_name("contract_config.json").read_text(encoding="utf-8")
        )["sources"]["jisi_future_sou_tools"]["whitelist"]
        payloads = sorted(
            (
                (r["id"], payload_hash(r, wl, "h1"))
                for r in records
                if r.get("id") in ("SYN-001", "SYN-002")
            ),
            key=lambda item: item[1],
        )
        obs_rows = [
            {
                "record": rec_id,
                "context_key": "detail",
                "payload_ref": payload,
                "order_key": "2026-06-02T07:52:16Z",
            }
            for rec_id, payload in payloads
        ]
        obs_text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in obs_rows)
        (staging / "observations.jsonl").write_text(obs_text, encoding="utf-8")
        manifest["input_files"].append(
            {
                "relative_path": "observations.jsonl",
                "sha256": hashlib.sha256(obs_text.encode("utf-8")).hexdigest(),
                "byte_size": len(obs_text.encode("utf-8")),
                "row_count": len(obs_rows),
                "format": "jsonl",
                "role": "observation",
            }
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        target = self.work / "obs_ok_target"
        verdict = validate_and_seal(staging, target)
        self.assertTrue(verdict["sealed"], verdict)
        self.assertEqual(verdict["sealed_rows"], 2)


if __name__ == "__main__":
    unittest.main()
