"""Offline T01 negative cases; all fixtures are synthetic."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inventory import InventoryError, fingerprint, register, safe_path, verify


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir()
        (self.root / "records.jsonl").write_text('{"id":"synthetic"}\n')

    def test_explicit_file_is_stable(self) -> None:
        entries = register(self.root, ["records.jsonl"], ["records.jsonl"])
        verify(self.root, entries)
        self.assertEqual(len(entries[0]["sha256"]), 64)

    def test_traversal(self) -> None:
        with self.assertRaisesRegex(InventoryError, "path_out_of_scope"):
            safe_path(self.root, "../outside.json")

    def test_absolute_path(self) -> None:
        with self.assertRaisesRegex(InventoryError, "path_out_of_scope"):
            safe_path(self.root, str(self.root / "records.jsonl"))

    def test_external_symlink(self) -> None:
        outside = self.base / "outside.json"
        outside.write_text("{}")
        (self.root / "link.json").symlink_to(outside)
        with self.assertRaisesRegex(InventoryError, "path_out_of_scope"):
            safe_path(self.root, "link.json")

    def test_changed_after_inventory(self) -> None:
        entry = fingerprint(self.root, "records.jsonl")
        (self.root / "records.jsonl").write_text('{"id":"changed"}\n')
        with self.assertRaisesRegex(InventoryError, "input_changed"):
            verify(self.root, [entry])

    def test_replacement_during_inventory(self) -> None:
        original_safe_path = safe_path
        calls = 0

        def replace_before_recheck(root: Path, relative: str) -> Path:
            nonlocal calls
            calls += 1
            if calls == 2:
                replacement = self.root / "new.jsonl"
                replacement.write_text('{"id":"replacement"}\n')
                replacement.replace(self.root / "records.jsonl")
            return original_safe_path(root, relative)

        with (
            patch("inventory.safe_path", side_effect=replace_before_recheck),
            self.assertRaisesRegex(InventoryError, "input_changed"),
        ):
            fingerprint(self.root, "records.jsonl")

    def test_empty_request(self) -> None:
        with self.assertRaisesRegex(InventoryError, "empty_input"):
            register(self.root, [], [])

    def test_delivery_copy_excluded(self) -> None:
        (self.root / "delivery.jsonl").write_text("{}\n")
        with self.assertRaisesRegex(InventoryError, "input_not_registered"):
            register(self.root, ["delivery.jsonl"], ["records.jsonl"])

    def test_hidden_and_secret_file_excluded(self) -> None:
        with self.assertRaisesRegex(InventoryError, "hidden_input_excluded"):
            safe_path(self.root, ".env")

    def test_archive_excluded(self) -> None:
        with self.assertRaisesRegex(InventoryError, "unsupported_input_format"):
            safe_path(self.root, "delivery.zip")

    def test_duplicate_requested_path(self) -> None:
        with self.assertRaisesRegex(InventoryError, "duplicate_input"):
            register(self.root, ["records.jsonl"] * 2, ["records.jsonl"])

    def test_missing_file(self) -> None:
        with self.assertRaisesRegex(InventoryError, "input_missing"):
            safe_path(self.root, "missing.jsonl")

    def test_empty_verification(self) -> None:
        with self.assertRaisesRegex(InventoryError, "empty_input"):
            verify(self.root, [])

    def run_cli(
        self, requested: str, *, changed: bool = False, wrong_root: bool = False
    ):
        registry = self.base / "registry.json"
        registry.write_text(
            json.dumps(
                {
                    "approved_root": str(self.root),
                    "sources": [{"inputs": [fingerprint(self.root, "records.jsonl")]}],
                }
            )
        )
        if changed:
            (self.root / "records.jsonl").write_text('{"id":"modified"}\n')
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(__file__).with_name("inventory.py")),
                "--root",
                str(self.base if wrong_root else self.root),
                "--registry",
                str(registry),
                "--input",
                requested,
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_cli_registered_input(self) -> None:
        result = self.run_cli("records.jsonl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "inventoried")

    def test_cli_delivery_copy_rejected(self) -> None:
        (self.root / "delivery.jsonl").write_text("{}\n")
        result = self.run_cli("delivery.jsonl")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "input_not_registered")

    def test_cli_changed_registered_input(self) -> None:
        result = self.run_cli("records.jsonl", changed=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "input_changed")

    def test_cli_wrong_root(self) -> None:
        result = self.run_cli("records.jsonl", wrong_root=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "root_not_registered")


if __name__ == "__main__":
    unittest.main()
