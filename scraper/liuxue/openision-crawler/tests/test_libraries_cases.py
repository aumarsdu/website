import unittest

from openision_crawler.libraries.cases import build_cases, count_cases_by_program


class CaseBuilderTests(unittest.TestCase):
    def test_build_case_normalizes_year_gpa_and_unknown_school_tag(self) -> None:
        rows = [
            {
                "id": "c1",
                "major_id": "m1",
                "target_school_id": "s1",
                "target_school_name": "学校",
                "school_name": "本科",
                "school_tag": "",
                "china_gpa": "87.5",
                "admission_year": "0000",
                "english_score": "",
                "exp_info": "科研一段",
            }
        ]
        cases = build_cases(rows)
        row = cases[0].to_dict()
        self.assertEqual(row["school_tag_normalized"], "未知背景")
        self.assertEqual(row["china_gpa"], 87.5)
        self.assertFalse(row["admission_year_valid"])
        self.assertFalse(row["english_score_known"])

    def test_count_cases_by_program(self) -> None:
        self.assertEqual(count_cases_by_program([{"major_id": "m1"}, {"major_id": "m1"}]), {"m1": 2})


if __name__ == "__main__":
    unittest.main()
