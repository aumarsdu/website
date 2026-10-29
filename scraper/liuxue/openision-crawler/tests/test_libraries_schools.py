import unittest

from openision_crawler.libraries.models import AdmissionCase, Program
from openision_crawler.libraries.schools import build_schools


class SchoolBuilderTests(unittest.TestCase):
    def test_build_school_aggregates_programs_and_cases(self) -> None:
        programs = [
            Program(program_id="m1", school_id="s1", school_name_cn="学校", country="英国", major_direction="计算机"),
            Program(program_id="m2", school_id="s1", school_name_cn="学校", country="英国", major_direction="金融"),
        ]
        cases = [
            AdmissionCase(case_id="c1", program_id="m1", target_school_id="s1", china_gpa=87.0, admission_year=2025, admission_year_valid=True),
            AdmissionCase(case_id="c2", program_id="m2", target_school_id="s1", china_gpa=90.0, admission_year=2024, admission_year_valid=True),
        ]
        schools = build_schools(programs, cases)
        row = schools[0].to_dict()
        self.assertEqual(row["program_count"], 2)
        self.assertEqual(row["case_count"], 2)
        self.assertEqual(row["major_directions"], ["计算机", "金融"])
        self.assertEqual(row["admission_year_range"], {"min": 2024, "max": 2025})
        self.assertEqual(row["admitted_gpa_distribution"]["avg"], 88.5)


if __name__ == "__main__":
    unittest.main()
