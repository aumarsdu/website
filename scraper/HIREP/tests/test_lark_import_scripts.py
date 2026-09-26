import unittest

from scripts.import_pbl_to_lark_base import (
    MATERIALS_TABLE_ID,
    MATERIALS_WRITE_FIELDS,
    project_to_row,
    resolve_write_profile,
    write_fields_for_profile,
)


class LarkImportScriptsTest(unittest.TestCase):
    def test_materials_profile_uses_real_target_fields(self):
        profile = resolve_write_profile("auto", MATERIALS_TABLE_ID)

        self.assertEqual(profile, "materials")
        self.assertIn("教授论文指导范围（CIS特有）", write_fields_for_profile(profile))
        self.assertNotIn("海报文字内容", write_fields_for_profile(profile))

    def test_materials_row_maps_teaching_mode_to_existing_select_option(self):
        fields = MATERIALS_WRITE_FIELDS
        project = {
            "title": "课题 A",
            "teaching_mode": 1,
            "raw": {"detail": {"customizedTopic": "论文方向"}},
        }

        row = project_to_row(project, write_profile="materials")

        self.assertEqual(row[fields.index("项目类型")], "线上")
        self.assertEqual(row[fields.index("教授论文指导范围（CIS特有）")], "论文方向")
        self.assertEqual(len(row), len(fields))


if __name__ == "__main__":
    unittest.main()
