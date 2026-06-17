from pathlib import Path
import sqlite3
import tempfile
import unittest

from openision_crawler.storage import Storage


class LibraryStorageTests(unittest.TestCase):
    def test_init_db_creates_library_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "openision.sqlite"
            Storage(db_path).init_db()
            with sqlite3.connect(db_path) as conn:
                names = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
            self.assertIn("program_library", names)
            self.assertIn("school_library", names)
            self.assertIn("admission_case_library", names)


if __name__ == "__main__":
    unittest.main()
