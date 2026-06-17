import unittest

from openision_crawler.libraries.models import AdmissionCase, Program, School


class LibraryModelTests(unittest.TestCase):
    def test_program_to_dict(self) -> None:
        row = Program(program_id="m1", school_id="s1", school_name_cn="学校", major_name_cn="专业").to_dict()
        self.assertEqual(row["program_id"], "m1")
        self.assertEqual(row["case_count"], 0)

    def test_case_to_dict(self) -> None:
        row = AdmissionCase(case_id="c1", program_id="m1", target_school_id="s1").to_dict()
        self.assertEqual(row["case_id"], "c1")
        self.assertFalse(row["english_score_known"])

    def test_school_to_dict(self) -> None:
        row = School(school_id="s1", school_name_cn="学校").to_dict()
        self.assertEqual(row["school_id"], "s1")
        self.assertEqual(row["program_count"], 0)


if __name__ == "__main__":
    unittest.main()
