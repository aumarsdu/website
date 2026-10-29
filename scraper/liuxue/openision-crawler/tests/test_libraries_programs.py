import unittest

from openision_crawler.libraries.programs import build_programs


class ProgramBuilderTests(unittest.TestCase):
    def test_build_program_uses_nested_school_country_and_fee_known(self) -> None:
        rows = [
            {
                "id": "m1",
                "school": {"id": "s1", "name": "学校", "name_en": "School", "country": "英国", "qs": 12},
                "major_name_cn": "计算机科学",
                "major_name_en": "Computer Science",
                "major_direction": "计算机",
                "fees": 0,
                "tuition_cn": "待确认",
                "similar_case_count": 2,
            }
        ]
        programs = build_programs(rows, {"m1": 3})
        self.assertEqual(len(programs), 1)
        row = programs[0].to_dict()
        self.assertEqual(row["country"], "英国")
        self.assertFalse(row["fee_known"])
        self.assertEqual(row["case_count"], 3)
        self.assertEqual(row["similar_case_count"], 2)


if __name__ == "__main__":
    unittest.main()
