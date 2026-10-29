"""Offline T01-R3 negative cases for the candidate target identity guard."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from target_guard import TargetGuardError, check_target, load_policy


class TargetGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.workspace = self.base / "workspace"
        self.side = self.workspace / "side"
        self.target = self.side / "candidate_data"
        self.target.mkdir(parents=True)
        (self.side / "evidence").mkdir()
        (self.side / "evidence" / "deep").mkdir()
        (self.workspace / "源目录").mkdir()
        (self.workspace / "legacy").mkdir()
        (self.workspace / "legacy" / "schema.sql").write_text(
            "-- synthetic legacy ddl\n", encoding="utf-8"
        )
        self.policy_path = self.base / "policy.json"
        self.policy: dict[str, object] = {
            "workspace_root": str(self.workspace),
            "side_root": "side",
            "default_target": "candidate_data",
            "protected_roots": [
                "源目录",
                "legacy",
                "legacy/schema.sql",
                "side/evidence",
                "side/evidence/deep",
            ],
            "ownership_marker": ".target_ownership.json",
        }
        self.write_policy(self.policy)

    def write_policy(self, policy: dict[str, object]) -> None:
        self.policy_path.write_text(
            json.dumps(policy, ensure_ascii=False), encoding="utf-8"
        )

    def marker(self) -> None:
        (self.target / ".target_ownership.json").write_text(
            json.dumps({"task": "T01", "owner": "writer", "created_at": "2026-09-25"}),
            encoding="utf-8",
        )

    def test_empty_target_ok(self) -> None:
        report = check_target(self.policy_path, "candidate_data")
        self.assertTrue(report["empty"])
        self.assertFalse(report["owned"])

    def test_parent_escape_rejected(self) -> None:
        with self.assertRaisesRegex(TargetGuardError, "target_out_of_scope"):
            check_target(self.policy_path, "../elsewhere")

    def test_absolute_target_rejected(self) -> None:
        with self.assertRaisesRegex(TargetGuardError, "target_out_of_scope"):
            check_target(self.policy_path, str(self.target))

    def test_root_target_rejected(self) -> None:
        with self.assertRaisesRegex(TargetGuardError, "target_out_of_scope"):
            check_target(self.policy_path, ".")

    def test_symlink_target_rejected(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        (self.side / "linked").symlink_to(outside)
        with self.assertRaisesRegex(TargetGuardError, "target_symlink_rejected"):
            check_target(self.policy_path, "linked")

    def test_target_equal_protected_rejected(self) -> None:
        with self.assertRaisesRegex(TargetGuardError, "target_overlaps_protected"):
            check_target(self.policy_path, "evidence")

    def test_target_inside_protected_rejected(self) -> None:
        nested = self.side / "evidence" / "nested"
        nested.mkdir()
        with self.assertRaisesRegex(TargetGuardError, "target_overlaps_protected"):
            check_target(self.policy_path, "evidence/nested")

    def test_target_ancestor_of_protected_rejected(self) -> None:
        policy = dict(self.policy)
        policy["protected_roots"] = ["源目录", "side/evidence/deep"]
        self.write_policy(policy)
        with self.assertRaisesRegex(TargetGuardError, "target_overlaps_protected"):
            check_target(self.policy_path, "evidence")

    def test_missing_target_rejected(self) -> None:
        with self.assertRaisesRegex(TargetGuardError, "target_missing"):
            check_target(self.policy_path, "not_created")

    def test_non_empty_without_marker_rejected(self) -> None:
        (self.target / "stale.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(TargetGuardError, "target_not_empty_unowned"):
            check_target(self.policy_path, "candidate_data")

    def test_owned_non_empty_target_ok(self) -> None:
        self.marker()
        (self.target / "owned.json").write_text("{}\n", encoding="utf-8")
        report = check_target(self.policy_path, "candidate_data")
        self.assertTrue(report["owned"])
        self.assertEqual(report["files"], 2)

    def test_invalid_marker_rejected(self) -> None:
        (self.target / "data.json").write_text("{}\n", encoding="utf-8")
        (self.target / ".target_ownership.json").write_text(
            "not json", encoding="utf-8"
        )
        with self.assertRaisesRegex(TargetGuardError, "target_ownership_invalid"):
            check_target(self.policy_path, "candidate_data")

    def test_marker_missing_fields_rejected(self) -> None:
        (self.target / "data.json").write_text("{}\n", encoding="utf-8")
        (self.target / ".target_ownership.json").write_text(
            json.dumps({"task": "T01"}), encoding="utf-8"
        )
        with self.assertRaisesRegex(TargetGuardError, "target_ownership_invalid"):
            check_target(self.policy_path, "candidate_data")

    def test_protected_root_missing_is_policy_error(self) -> None:
        policy = dict(self.policy)
        policy["protected_roots"] = ["源目录", "gone"]
        self.write_policy(policy)
        with self.assertRaisesRegex(TargetGuardError, "protected_root_missing"):
            check_target(self.policy_path, "candidate_data")

    def test_policy_bad_json_rejected(self) -> None:
        self.policy_path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(TargetGuardError, "policy_unreadable"):
            load_policy(self.policy_path)

    def run_cli(self, target: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(__file__).with_name("target_guard.py")),
                "--policy",
                str(self.policy_path),
                "--target",
                target,
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_cli_empty_target_ok(self) -> None:
        result = self.run_cli("candidate_data")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "target_ok")

    def test_cli_unowned_non_empty_rejected(self) -> None:
        (self.target / "stray.json").write_text("{}\n", encoding="utf-8")
        result = self.run_cli("candidate_data")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "target_not_empty_unowned")


if __name__ == "__main__":
    unittest.main()
