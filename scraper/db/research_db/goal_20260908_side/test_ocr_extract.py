"""T06 OCR extraction cases: synthetic rules plus the 20 real frozen posters."""

import json
import unittest
from pathlib import Path

from ocr_extract import extract_fields, extract_poster, load_csv_rows

SIDE = Path(__file__).resolve().parent


def blocks(*pairs):
    return [{"confidence": c, "polygon": [], "text": t} for c, t in pairs]


class OcrExtractTests(unittest.TestCase):
    def test_full_date_extracted_with_evidence(self) -> None:
        result = extract_fields(
            "p.png", blocks((1.0, "课题X"), (1.0, "开课"), (0.999, "2026年07月25日"))
        )
        field = result["fields"]["start_date"]
        self.assertEqual(field["state"], "value")
        self.assertEqual(field["value"], "2026-07-25")
        self.assertEqual(field["precision"], "day")
        self.assertEqual(field["evidence"][0]["block_index"], 2)

    def test_missing_year_flagged_pending(self) -> None:
        result = extract_fields("p.png", blocks((1.0, "开课"), (0.998, "7月10日")))
        field = result["fields"]["start_date"]
        self.assertEqual(field["state"], "pending_review")
        self.assertTrue(field["missing_year"])

    def test_slash_date_missing_year_pending(self) -> None:
        result = extract_fields("p.png", blocks((1.0, "07/18")))
        field = result["fields"]["start_date"]
        self.assertEqual(field["state"], "pending_review")
        self.assertTrue(field["missing_year"])
        self.assertEqual(field["value"], "--07-18")

    def test_low_confidence_date_pending(self) -> None:
        result = extract_fields(
            "p.png", blocks((1.0, "开课"), (0.95, "2026年07月25日"))
        )
        self.assertEqual(result["fields"]["start_date"]["state"], "pending_review")

    def test_price_absent_not_provided(self) -> None:
        result = extract_fields("p.png", blocks((1.0, "课题X")))
        self.assertEqual(result["fields"]["price"]["state"], "not_provided")

    def test_price_prose_false_friend_ignored(self) -> None:
        result = extract_fields(
            "p.png", blocks((1.0, "以价格分布视角为例"), (1.0, "标题够长的方法研究"))
        )
        self.assertEqual(result["fields"]["price"]["state"], "not_provided")

    def test_price_mark_pending(self) -> None:
        result = extract_fields("p.png", blocks((0.99, "学费 39800 元")))
        field = result["fields"]["price"]
        self.assertEqual(field["state"], "pending_review")
        self.assertIn("39800", field["value_raw"])

    def test_instructor_after_role_label(self) -> None:
        result = extract_fields(
            "p.png",
            blocks(
                (1.0, "课题X"),
                (1.0, "牛津大学"),
                (1.0, "产学研导师"),
                (1.0, "F.B."),
            ),
        )
        field = result["fields"]["instructor"]
        self.assertEqual(field["state"], "value")
        self.assertEqual(field["value"], "F.B.")
        self.assertEqual(field["evidence"][0]["block_index"], 3)

    def test_instructor_junk_after_label_ignored(self) -> None:
        result = extract_fields(
            "p.png",
            blocks(
                (1.0, "产学研导师"), (1.0, "10 封教授网申推荐信+ 1 篇英文会议论文辅导")
            ),
        )
        self.assertEqual(result["fields"]["instructor"]["state"], "not_provided")

    def test_title_from_top_zone_excludes_category(self) -> None:
        result = extract_fields(
            "p.png",
            blocks(
                (1.0, "经济学专题"),
                (1.0, "全球化治理中的贸易投资规则研究"),
                (1.0, "6周"),
                (1.0, "线上直播"),
            ),
        )
        field = result["fields"]["title"]
        self.assertEqual(field["state"], "pending_review")
        self.assertIn("全球化治理", field["value"])
        self.assertNotIn("经济学专题", field["value"])

    def test_real_frozen_posters_coverage(self) -> None:
        manifest = json.loads(
            (SIDE / "pilot_manifest.json").read_text(encoding="utf-8")
        )
        csv_path = (
            SIDE.parent.parent.parent
            / "盐趣"
            / "盐趣7-9月项目合集"
            / "海报文字识别_PP-OCRv6.csv"
        )
        if not csv_path.is_file():
            self.skipTest("yanqu OCR csv not present")
        import hashlib

        self.assertEqual(
            hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "0ff1a345256a6c40f5e369fbce392d75f37ff60843ec2cfa1a3263c4e34c6018",
            "yanqu OCR csv must match the registered input hash",
        )
        rows = load_csv_rows(csv_path)
        dates = instructors = prices_absent = 0
        total = len(manifest["yanqu_original_image_candidates"])
        for candidate in manifest["yanqu_original_image_candidates"]:
            result = extract_poster(
                rows, candidate["csv_row"], candidate["resolved_collection_path"]
            )
            fields = result["fields"]
            for name, field in fields.items():
                for ev_item in field["evidence"]:
                    self.assertTrue(0 <= ev_item["block_index"] < 500, name)
                    if field["state"] == "value":
                        self.assertGreaterEqual(
                            ev_item["confidence"], 0.99, (name, ev_item)
                        )
                    else:
                        self.assertGreaterEqual(ev_item["confidence"], 0.5)
            if fields["start_date"]["state"] != "not_provided":
                dates += 1
            if fields["instructor"]["state"] != "not_provided":
                instructors += 1
            if fields["price"]["state"] == "not_provided":
                prices_absent += 1
        self.assertEqual(total, 20)
        self.assertEqual(dates, 20)
        self.assertEqual(instructors, 18)
        self.assertEqual(prices_absent, 20)


if __name__ == "__main__":
    unittest.main()
