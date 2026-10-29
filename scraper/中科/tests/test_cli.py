import unittest

from sou_crawler.cli import build_parser


class CliTests(unittest.TestCase):
    def test_skip_asset_host_option(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["--skip-asset-host", "example.com", "download-assets", "--dry-run"])

        self.assertEqual(args.skip_asset_host, ["example.com"])

    def test_refresh_public_topics_options(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["--max-details", "55", "refresh-public-topics", "--snapshot-id", "20260730", "--dry-run"])

        self.assertEqual(args.max_details, 55)
        self.assertEqual(args.snapshot_id, "20260730")
        self.assertTrue(args.dry_run)

    def test_audit_archive_requires_a_snapshot(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["audit-archive", "--snapshot-id", "20260730"])

        self.assertEqual(args.snapshot_id, "20260730")

    def test_backfill_details_options(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["--max-details", "55", "backfill-details", "--snapshot-id", "20260730", "--dry-run"])

        self.assertEqual(args.max_details, 55)
        self.assertEqual(args.snapshot_id, "20260730")
        self.assertTrue(args.dry_run)

    def test_cleanup_out_of_scope_requires_explicit_command_confirmation(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["cleanup-out-of-scope", "--snapshot-id", "20260730", "--confirm"])

        self.assertTrue(args.confirm)

    def test_archive_snapshot_topics_options(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "archive-snapshot-topics",
                "--snapshot-id",
                "audit-20260902",
                "--target-dir",
                "/tmp/archive",
                "--dry-run",
            ]
        )

        self.assertEqual(args.snapshot_id, "audit-20260902")
        self.assertEqual(args.target_dir, "/tmp/archive")
        self.assertTrue(args.dry_run)

    def test_download_snapshot_assets_options(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["--max-assets", "5", "download-snapshot-assets", "--snapshot-id", "audit-20260902", "--dry-run"])

        self.assertEqual(args.max_assets, 5)
        self.assertEqual(args.snapshot_id, "audit-20260902")
        self.assertTrue(args.dry_run)


if __name__ == "__main__":
    unittest.main()
