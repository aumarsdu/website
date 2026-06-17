import unittest

from openision_crawler.libraries.normalizers import (
    normalize_admission_year,
    normalize_fee,
    normalize_school_tag,
    parse_float,
    text_or_none,
)


class LibraryNormalizerTests(unittest.TestCase):
    def test_text_or_none_strips_blank(self) -> None:
        self.assertIsNone(text_or_none("  "))
        self.assertEqual(text_or_none(" 英国 "), "英国")

    def test_parse_float_handles_text(self) -> None:
        self.assertEqual(parse_float("87.5"), 87.5)
        self.assertIsNone(parse_float(""))
        self.assertIsNone(parse_float(None))

    def test_normalize_fee_marks_zero_as_unknown(self) -> None:
        self.assertEqual(normalize_fee(0, "£24,000"), (None, False, "£24,000"))
        self.assertEqual(normalize_fee(24000, "£24,000"), (24000.0, True, "£24,000"))

    def test_normalize_admission_year_rejects_invalid(self) -> None:
        self.assertEqual(normalize_admission_year("2025"), (2025, True))
        self.assertEqual(normalize_admission_year("0000"), (None, False))
        self.assertEqual(normalize_admission_year(""), (None, False))

    def test_normalize_school_tag(self) -> None:
        self.assertEqual(normalize_school_tag(" 985院校 "), "985院校")
        self.assertEqual(normalize_school_tag(""), "未知背景")


if __name__ == "__main__":
    unittest.main()
