import unittest

from openision_crawler.cli import build_parser


class LibraryCliTests(unittest.TestCase):
    def test_build_libraries_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["build-libraries"])
        self.assertEqual(args.command, "build-libraries")


if __name__ == "__main__":
    unittest.main()
