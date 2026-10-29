import unittest

from openision_crawler.libraries.models import AdmissionCase, Program, School
from openision_crawler.libraries.quality import build_quality_report


class QualityReportTests(unittest.TestCase):
    def test_quality_report_counts_join_failures_and_unknowns(self) -> None:
        programs = [Program(program_id="m1", school_id="s1", fee_known=False)]
        cases = [AdmissionCase(case_id="c1", program_id="m1", target_school_id="s1", admission_year_valid=False)]
        schools = [School(school_id="s1")]
        report = build_quality_report(programs, cases, schools)
        self.assertEqual(report["counts"]["programs"], 1)
        self.assertEqual(report["counts"]["cases"], 1)
        self.assertEqual(report["counts"]["schools"], 1)
        self.assertEqual(report["joins"]["case_program_join_failures"], 0)
        self.assertEqual(report["quality"]["unknown_fee_programs"], 1)
        self.assertEqual(report["quality"]["invalid_year_cases"], 1)


if __name__ == "__main__":
    unittest.main()
