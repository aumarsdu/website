from pathlib import Path
import tempfile
import unittest

from openision_crawler.libraries.build import build_libraries
from openision_crawler.libraries.io import write_jsonl


class LibraryBuildTests(unittest.TestCase):
    def test_build_libraries_writes_three_jsonl_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(
                root / "data" / "normalized" / "majors_list.jsonl",
                [{"id": "m1", "school": {"id": "s1", "name": "学校", "country": "英国"}, "major_name_cn": "专业"}],
            )
            write_jsonl(
                root / "data" / "normalized" / "cases_list.jsonl",
                [{"id": "c1", "major_id": "m1", "target_school_id": "s1", "target_school_name": "学校"}],
            )
            report = build_libraries(root)
            self.assertEqual(report["counts"]["programs"], 1)
            self.assertTrue((root / "data" / "libraries" / "program_library.jsonl").exists())
            self.assertTrue((root / "data" / "libraries" / "school_library.jsonl").exists())
            self.assertTrue((root / "data" / "libraries" / "admission_case_library.jsonl").exists())
            self.assertTrue((root / "data" / "reports" / "library_quality_report.md").exists())


if __name__ == "__main__":
    unittest.main()
