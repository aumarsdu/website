"""Normalization must restructure what a source said and never add to it."""

from __future__ import annotations

import unittest

from research_facts.normalize import (
    normalize_audience,
    normalize_date,
    normalize_duration,
    normalize_field,
    normalize_instructor,
    normalize_output,
    normalize_title,
)


class TestDate(unittest.TestCase):
    def test_recognizes_common_formats(self) -> None:
        for raw in ("2027-01-08", "2027/1/8", "2027.01.08", "2027年1月8日", "20270108"):
            result = normalize_date(raw)
            self.assertIsNotNone(result, raw)
            self.assertEqual(result.value, "2027-01-08", raw)
            self.assertEqual(result.precision, "exact", raw)

    def test_iso_datetime_keeps_the_literal_date(self) -> None:
        # 16:00Z is the next day in UTC+8. Converting would invent a date.
        result = normalize_date("2027-01-08T16:00:00.000Z")
        self.assertEqual(result.value, "2027-01-08")

    def test_partial_precision_is_kept(self) -> None:
        year = normalize_date("2027年春季")
        self.assertEqual((year.value, year.precision), ("2027", "term"))
        self.assertEqual(year.extra["term"], "spring")

        month = normalize_date("2027年9月")
        self.assertEqual((month.value, month.precision), ("2027-09", "month"))
        self.assertEqual(month.extra["day"], "not_stated")

        bare_year = normalize_date("2027年")
        self.assertEqual((bare_year.value, bare_year.precision), ("2027", "year"))

    def test_range_keeps_both_ends(self) -> None:
        result = normalize_date("2027-01-08 至 2027-02-05")
        self.assertEqual(result.value, "2027-01-08/2027-02-05")
        self.assertEqual(result.precision, "range")

    def test_approximate_wording_downgrades_precision(self) -> None:
        self.assertEqual(normalize_date("2027年1月8日左右").precision, "approximate")

    def test_unparseable_returns_none(self) -> None:
        self.assertIsNone(normalize_date("开课时间待定"))
        self.assertIsNone(normalize_date("2027-02-30"))  # impossible date
        self.assertIsNone(normalize_date(""))


class TestDuration(unittest.TestCase):
    def test_single_unit(self) -> None:
        result = normalize_duration("8周")
        self.assertEqual(result.value, "8周")
        self.assertEqual(result.rule, "duration_weeks")

    def test_unit_canonicalization(self) -> None:
        self.assertEqual(normalize_duration("3个月").value, "3个月")
        self.assertEqual(normalize_duration("12课时").value, "12课时")
        self.assertEqual(normalize_duration("16 weeks").value, "16周")

    def test_composite_segments_are_concatenated_not_summed(self) -> None:
        # The arithmetic is the whole point: 4周+2周 must not become 6周.
        result = normalize_duration("4周在线小组科研+2周论文指导")
        self.assertEqual(result.value, "4周+2周")
        self.assertEqual(result.extra["arithmetic"], "none")
        self.assertEqual(result.items, ["4周", "2周"])

    def test_range(self) -> None:
        result = normalize_duration("4-6周")
        self.assertEqual((result.value, result.precision), ("4-6周", "range"))

    def test_text_around_a_number_is_kept_in_metadata(self) -> None:
        result = normalize_duration("8周（含2周论文指导）")
        self.assertEqual(result.value, "8周")
        self.assertIn("8周（含2周论文指导）", result.extra["segments"][0]["text"])

    def test_no_duration_returns_none(self) -> None:
        self.assertIsNone(normalize_duration("详见附件"))
        self.assertIsNone(normalize_duration(""))


class TestTextFields(unittest.TestCase):
    def test_title_drops_a_decorative_prefix(self) -> None:
        result = normalize_title("密集项目：遥感无人机")
        self.assertEqual(result.value, "遥感无人机")
        self.assertTrue(result.extra["prefix_removed"])

    def test_instructor_keeps_affiliation_in_value_but_not_in_comparison(self) -> None:
        short = normalize_instructor("张三")
        full = normalize_instructor("张三（北京大学）")
        self.assertEqual(full.value, "张三（北京大学）")
        self.assertEqual(full.extra["affiliation_hint"], "北京大学")
        # Same person: the comparison key ignores the parenthetical.
        self.assertEqual(short.compare_key, full.compare_key)

    def test_audience_is_order_insensitive(self) -> None:
        left = normalize_audience("遥感、仿生学")
        right = normalize_audience("仿生学、遥感")
        self.assertEqual(left.compare_key, right.compare_key)
        self.assertEqual(left.items, ["遥感", "仿生学"])

    def test_output_keeps_bullets_as_items(self) -> None:
        result = normalize_output("- 项目报告\n- 项目结业证书")
        self.assertEqual(result.items, ["项目报告", "项目结业证书"])

    def test_output_keeps_slash_terms_whole(self) -> None:
        # "EI/CPCI/Scopus" is one term; splitting on "/" would corrupt it.
        result = normalize_output("EI/CPCI/Scopus检索国际会议发表指导")
        self.assertEqual(result.items, ["EI/CPCI/Scopus检索国际会议发表指导"])

    def test_html_is_flattened_without_losing_the_list(self) -> None:
        result = normalize_output("<p>项目报告</p><p>结业证书</p>")
        self.assertEqual(result.items, ["项目报告", "结业证书"])

    def test_unknown_field_has_no_normalizer(self) -> None:
        self.assertIsNone(normalize_field("not_a_field", "x"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
