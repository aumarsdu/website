import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sou_crawler.config import Settings
from sou_crawler.pbl_audit import build_pbl_coverage_report


class PblAuditTest(unittest.TestCase):
    def test_reports_current_public_course_missing_from_local_history(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects_path = self._write_batch(root, "output_pbl_full", "ce-1", self._pbl_source("ce-1"))

            report = build_pbl_coverage_report(
                Settings(output_dir=root / "output_pbl_audit"),
                [{"courseExtendId": "ce-1"}, {"courseExtendId": "ce-2"}],
                [projects_path],
            )

            self.assertFalse(report["coverage"]["complete"])
            self.assertEqual(report["coverage"]["missing_business_ids"], ["ce-2"])
            self.assertTrue(report["details"]["complete"])
            self.assertTrue(report["layout"]["complete"])

    def test_reports_out_of_scope_batch_as_deletion_candidate_without_deleting_it(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_name = "output_pbl_legacy"
            projects_path = self._write_batch(
                root,
                output_name,
                "legacy-1",
                "https://example.com/course?id=legacy-1",
            )

            report = build_pbl_coverage_report(
                Settings(output_dir=root / "output_pbl_audit"),
                [],
                [projects_path],
            )

            self.assertFalse(report["scope_validation"]["clean"])
            self.assertEqual(len(report["scope_validation"]["out_of_scope_project_records"]), 1)
            candidate = report["scope_validation"]["deletion_candidates"][0]
            self.assertEqual(candidate["candidate_type"], "output_directory")
            self.assertEqual(candidate["path"], str((root / output_name).resolve()))
            self.assertTrue((root / output_name).is_dir())

    def _write_batch(self, root: Path, output_name: str, business_id: str, source_url: str) -> Path:
        output = root / output_name
        project_dir = output / "assets" / "理科" / "化学" / "课题 A"
        project_dir.mkdir(parents=True)
        (project_dir / "详情页信息.json").write_text("{}", encoding="utf-8")
        projects_path = output / "processed" / "projects.jsonl"
        projects_path.parent.mkdir(parents=True)
        projects_path.write_text(
            json.dumps(
                {
                    "business_id": business_id,
                    "category": "理科",
                    "direction": "化学",
                    "title": "课题 A",
                    "source_url": source_url,
                    "project_dir": str(project_dir),
                    "raw": {"detail": {"courseNameCn": "课题 A"}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (output / "processed" / "asset_manifest.jsonl").write_text("", encoding="utf-8")
        return projects_path

    def _pbl_source(self, business_id: str) -> str:
        return f"https://pbl.hirepglobal.com/Professor?courseExtendId={business_id}&productPackageId=pkg&h5Type=1"


if __name__ == "__main__":
    unittest.main()
