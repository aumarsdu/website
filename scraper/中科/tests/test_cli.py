import unittest

from sou_crawler.cli import build_parser


class CliTests(unittest.TestCase):
    def test_skip_asset_host_option(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["--skip-asset-host", "example.com", "download-assets", "--dry-run"])

        self.assertEqual(args.skip_asset_host, ["example.com"])


if __name__ == "__main__":
    unittest.main()
