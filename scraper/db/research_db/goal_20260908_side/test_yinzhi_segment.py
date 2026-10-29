"""T07 segmentation cases: golden anchors, zero navigation, page context."""

import json
import unittest
from pathlib import Path

from yinzhi_segment import is_navigation, segment_file

SIDE = Path(__file__).resolve().parent
GOLDEN = json.loads((SIDE / "fixtures" / "t07_golden.json").read_text(encoding="utf-8"))
CONTENT = SIDE.parent.parent.parent / "引知/data/archive/public/content.md"
RESULT = segment_file(CONTENT)


class YinzhiSegmentTests(unittest.TestCase):
    def test_recall_matches_golden_fully(self) -> None:
        golden_anchors = {e["anchor_line"] for e in GOLDEN["entries"]}
        found = {e["anchor_line"] for e in RESULT["entries"]}
        recall = len(golden_anchors & found) / len(golden_anchors)
        self.assertGreaterEqual(recall, 0.9)
        self.assertEqual(recall, 1.0)
        self.assertEqual(RESULT["counts"]["entries"], GOLDEN["entry_count"])

    def test_no_false_positive_entries(self) -> None:
        golden_anchors = {e["anchor_line"] for e in GOLDEN["entries"]}
        for entry in RESULT["entries"]:
            self.assertIn(entry["anchor_line"], golden_anchors)

    def test_zero_navigation_inside_entries(self) -> None:
        for entry in RESULT["entries"]:
            self.assertFalse(is_navigation(entry["title"]), entry["anchor_line"])
            for line in entry["content_lines"]:
                self.assertFalse(
                    is_navigation(
                        CONTENT.read_text(encoding="utf-8").splitlines()[line - 1]
                    ),
                    (entry["anchor_line"], line),
                )

    def test_page_front_matter_and_highlights_not_entries(self) -> None:
        for entry in RESULT["entries"]:
            self.assertGreater(entry["anchor_line"], 25, entry)
        self.assertEqual(RESULT["page_context"]["编码"], "qYtCDec")
        self.assertEqual(RESULT["page_context"]["更新时间"], "2026-05-21T02:26:25.000Z")
        self.assertIn(11, RESULT["highlights_lines"])

    def test_trailing_nav_and_benefits_not_entries(self) -> None:
        anchors = {e["anchor_line"] for e in RESULT["entries"]}
        for excluded in (713, 715, 721, 729, 675, 679, 709, 735, 737):
            self.assertNotIn(excluded, anchors)

    def test_navigation_excluded_reported(self) -> None:
        self.assertGreater(RESULT["counts"]["navigation_excluded"], 20)
        nav_lines = {n["line"] for n in RESULT["navigation_excluded"]}
        for line in (93, 715, 731, 735):
            self.assertIn(line, nav_lines)

    def test_bilingual_pairs_linked_bidirectionally(self) -> None:
        by_anchor = {e["anchor_line"]: e for e in RESULT["entries"]}
        pairs = {
            (e["anchor_line"], e["pair_anchor"])
            for e in RESULT["entries"]
            if "pair_anchor" in e
        }
        self.assertEqual(len(pairs), 64)
        undirected = {frozenset(pair) for pair in pairs}
        self.assertEqual(len(undirected), 32)
        for zh, en in pairs:
            if by_anchor[zh]["language"] == "zh":
                self.assertEqual(by_anchor[en]["language"], "en")
            else:
                self.assertEqual(by_anchor[en]["language"], "zh")
            self.assertEqual(by_anchor[en]["pair_anchor"], zh)
            self.assertEqual(by_anchor[zh]["pair_anchor"], en)
        for pair in ((87, 97), (187, 197), (207, 217), (471, 481), (555, 565)):
            self.assertIn(pair, pairs)

    def test_unmarked_and_english_variants_included(self) -> None:
        unmarked = {e["anchor_line"] for e in RESULT["entries"] if e["kind"] != "quota"}
        for line in (
            47,
            127,
            147,
            227,
            347,
            371,
            391,
            411,
            431,
            491,
            531,
            555,
            575,
            595,
        ):
            self.assertIn(line, unmarked)
        for en_variant in (37, 77, 117, 177, 297, 461, 521, 625, 665):
            self.assertIn(
                en_variant,
                unmarked
                | {e["anchor_line"] for e in RESULT["entries"] if e["kind"] == "quota"},
            )

    def test_category_context_bound_to_entries(self) -> None:
        by_anchor = {e["anchor_line"]: e for e in RESULT["entries"]}
        self.assertEqual(by_anchor[27]["category"], "理工科项目")
        self.assertEqual(by_anchor[371]["category"], "人文社科项目")
        self.assertEqual(by_anchor[655]["category"], "商科、艺术、建筑类项目")
        self.assertEqual(by_anchor[565]["subcategory"], "Business, Art & Architecture")

    def test_all_entries_confirmed_with_content(self) -> None:
        self.assertEqual(RESULT["counts"]["pending"], 0)
        for entry in RESULT["entries"]:
            self.assertEqual(entry["status"], "confirmed")
            self.assertGreaterEqual(len(entry["content_lines"]), 1)


if __name__ == "__main__":
    unittest.main()
