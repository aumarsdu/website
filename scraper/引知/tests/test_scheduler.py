import unittest

from caoliao_archiver.scheduler import UrlScheduler


class SchedulerTests(unittest.TestCase):
    def test_scheduler_deduplicates_and_skips_out_of_scope(self):
        scheduler = UrlScheduler(max_pages=10, allow_url=lambda url: "allowed.test" in url)
        scheduler.add_many(
            [
                "https://allowed.test/a/",
                "https://allowed.test/a",
                "https://blocked.test/a",
            ]
        )
        self.assertEqual(list(scheduler), ["https://allowed.test/a"])
        self.assertEqual(scheduler.duplicates, 1)
        self.assertEqual(scheduler.skipped_out_of_scope, 1)
        self.assertEqual(scheduler.skipped_over_limit, 0)

    def test_scheduler_tracks_items_skipped_over_limit(self):
        scheduler = UrlScheduler(max_pages=1, allow_url=lambda url: True)
        scheduler.add_many(["https://allowed.test/a", "https://allowed.test/b"])
        self.assertEqual(list(scheduler), ["https://allowed.test/a"])
        self.assertEqual(scheduler.skipped_over_limit, 1)


if __name__ == "__main__":
    unittest.main()
