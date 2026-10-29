import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.verify_pbl_output import verify_pbl_output


class VerifyPblOutputTest(unittest.TestCase):
    def test_verify_accepts_complete_output(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "output_pbl_incremental"
            project_dir = output / "assets" / "理科" / "化学" / "课题 A"
            project_dir.mkdir(parents=True)
            (project_dir / "详情页信息.json").write_text("{}", encoding="utf-8")
            poster = project_dir / "海报.jpg"
            poster.write_bytes(b"poster")
            self._write_output(output, project_dir, poster)

            result = verify_pbl_output(output)

            self.assertTrue(result["valid"])
            self.assertEqual(result["projects"], 1)
            self.assertEqual(result["manifest_entries"], 1)

    def test_verify_reports_missing_manifest_asset(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "output_pbl_incremental"
            project_dir = output / "assets" / "理科" / "化学" / "课题 A"
            project_dir.mkdir(parents=True)
            (project_dir / "详情页信息.json").write_text("{}", encoding="utf-8")
            missing_poster = project_dir / "海报.jpg"
            self._write_output(output, project_dir, missing_poster)

            result = verify_pbl_output(output)

            self.assertFalse(result["valid"])
            self.assertEqual(result["missing_asset_files"], 1)
            self.assertIn("missing_manifest_asset_files", result["errors"])

    def test_verify_warns_but_does_not_fail_for_historical_duplicate_business_ids(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "output_pbl_incremental"
            project_dir = output / "assets" / "理科" / "化学" / "课题 A__ce-1"
            project_dir.mkdir(parents=True)
            (project_dir / "详情页信息.json").write_text("{}", encoding="utf-8")
            poster = project_dir / "海报.jpg"
            poster.write_bytes(b"poster")
            self._write_output(output, project_dir, poster)
            projects_path = output / "processed" / "projects.jsonl"
            projects_path.write_text(projects_path.read_text(encoding="utf-8") * 2, encoding="utf-8")

            result = verify_pbl_output(output)

            self.assertTrue(result["valid"])
            self.assertEqual(result["duplicate_business_ids"], 1)
            self.assertIn("duplicate_business_ids", result["warnings"])

    def test_verify_reports_project_directory_that_does_not_match_category_direction_and_title(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "output_pbl_incremental"
            project_dir = output / "assets" / "理科" / "物理" / "课题 A"
            project_dir.mkdir(parents=True)
            (project_dir / "详情页信息.json").write_text("{}", encoding="utf-8")
            poster = project_dir / "海报.jpg"
            poster.write_bytes(b"poster")
            self._write_output(output, project_dir, poster)

            result = verify_pbl_output(output)

            self.assertFalse(result["valid"])
            self.assertEqual(result["misplaced_project_directories"], 1)
            self.assertIn("misplaced_project_directories", result["errors"])

    def _write_output(self, output: Path, project_dir: Path, asset: Path) -> None:
        processed = output / "processed"
        processed.mkdir(parents=True, exist_ok=True)
        (processed / "projects.jsonl").write_text(
            json.dumps(
                {
                    "business_id": "ce-1",
                    "category": "理科",
                    "direction": "化学",
                    "title": "课题 A",
                    "project_dir": str(project_dir),
                    "raw": {"detail": {"courseNameCn": "课题 A"}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (processed / "asset_manifest.jsonl").write_text(
            json.dumps(
                {
                    "manifest_key": "ce-1::attachment::attachmentId",
                    "project_dir": str(project_dir),
                    "file": str(asset),
                }
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
