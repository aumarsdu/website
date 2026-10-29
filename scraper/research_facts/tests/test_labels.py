"""Label extraction: explicit labels only, with boundary protection."""

from __future__ import annotations

import unittest

from research_facts.config import Settings
from research_facts.extract import claims_from_blocks
from research_facts.labels import TextBlock, is_stop_line, scan_line, template_signature


def blocks_from(lines: list[str], start: int = 0) -> list[TextBlock]:
    return [
        TextBlock(text=line, pointer=f"p1#b{start + index}", detail="page=1", order=start + index)
        for index, line in enumerate(lines)
    ]


def line_hits(text: str) -> dict[str, str]:
    return {hit.field: hit.value for hit in scan_line(text, require_delimiter=True)}


def row_hits(text: str) -> dict[str, str]:
    return {hit.field: hit.value for hit in scan_line(text, require_delimiter=False)}


class TestLineScanning(unittest.TestCase):
    def test_explicit_label_with_colon(self) -> None:
        self.assertEqual(line_hits("开课日期：2027年1月8日"), {"start_date": "2027年1月8日"})

    def test_label_without_colon_is_not_a_line_hit(self) -> None:
        # Free text must not be mined for values; posters use row mode instead.
        self.assertEqual(line_hits("本项目开课日期2027年1月8日开始"), {})

    def test_row_mode_allows_a_missing_separator(self) -> None:
        self.assertEqual(row_hits("开课日期2027/01/08"), {"start_date": "2027/01/08"})
        self.assertEqual(row_hits("研究周期8周"), {"duration": "8周"})

    def test_compound_label_beats_its_suffix(self) -> None:
        hits = row_hits("项目周期：8周")
        self.assertEqual(hits, {"duration": "8周"})

    def test_professor_label_does_not_match_inside_another_word(self) -> None:
        # "副教授" must not be read as the label "教授".
        self.assertEqual(row_hits("副教授：张三"), {"instructor": "张三"})

    def test_deadline_is_not_a_start_date(self) -> None:
        self.assertNotIn("start_date", row_hits("报名截止：2026年12月1日"))
        self.assertNotIn("start_date", line_hits("申请截止日期：2026年12月1日"))

    def test_label_inside_a_sentence_is_rejected(self) -> None:
        self.assertEqual(row_hits("本项目适合遥感方向的学生"), {})

    def test_two_labels_on_one_line_each_get_their_own_value(self) -> None:
        hits = row_hits("研究周期 8周 适合人群 遥感、仿生学")
        self.assertEqual(hits["duration"], "8周")
        self.assertEqual(hits["suitable_audience"], "遥感、仿生学")

    def test_english_label_matches_with_or_without_space(self) -> None:
        self.assertEqual(row_hits("Duration: 10 weeks"), {"duration": "10 weeks"})
        self.assertEqual(row_hits("CourseTitle Urban Wind"), {"project_title": "Urban Wind"})


class TestStopLines(unittest.TestCase):
    def test_known_label_ends_a_multi_line_value(self) -> None:
        self.assertTrue(is_stop_line("成果形式：报告"))

    def test_section_heading_ends_a_multi_line_value(self) -> None:
        self.assertTrue(is_stop_line("一、课题背景"))
        self.assertTrue(is_stop_line("第 3 讲 数据处理"))

    def test_blank_line_ends_a_multi_line_value(self) -> None:
        self.assertTrue(is_stop_line("   "))

    def test_plain_sentence_continues(self) -> None:
        self.assertFalse(is_stop_line("项目报告一份"))


class TestClaimBuilding(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings()

    def test_single_line_field_does_not_swallow_the_next_line(self) -> None:
        blocks = blocks_from(["开课日期：2027年1月8日", "研究周期：8周"])
        claims = claims_from_blocks(
            blocks, document_id="d1", source_kind="handbook_pdf", settings=self.settings
        )
        values = {claim.field: claim.raw_text for claim in claims}
        self.assertEqual(values, {"start_date": "2027年1月8日", "duration": "8周"})

    def test_multi_line_field_collects_the_following_lines(self) -> None:
        blocks = blocks_from(
            ["成果形式：", "项目报告", "结业证书", "一、课题背景", "背景正文"]
        )
        claims = claims_from_blocks(
            blocks, document_id="d1", source_kind="handbook_pdf", settings=self.settings
        )
        output = next(claim for claim in claims if claim.field == "output_description")
        self.assertEqual(output.raw_text, "项目报告\n结业证书")
        self.assertEqual(output.extraction_method, "label_multiline")
        self.assertEqual(output.locator.pointer, "p1#b0..p1#b2")
        self.assertEqual(output.extraction_confidence, "medium")

    def test_multi_line_field_appends_to_an_inline_first_item(self) -> None:
        blocks = blocks_from(["成果形式：仿真数据集", "导师推荐信", "适合人群：建筑学"])
        claims = claims_from_blocks(
            blocks, document_id="d1", source_kind="handbook_pdf", settings=self.settings
        )
        output = next(claim for claim in claims if claim.field == "output_description")
        self.assertEqual(output.raw_text, "仿真数据集\n导师推荐信")

    def test_bare_label_without_continuation_produces_nothing(self) -> None:
        blocks = blocks_from(["指导教师："])
        claims = claims_from_blocks(
            blocks, document_id="d1", source_kind="handbook_pdf", settings=self.settings
        )
        self.assertEqual(claims, [])

    def test_low_ocr_confidence_caps_the_claim(self) -> None:
        block = TextBlock(
            text="开课日期：2027年1月8日",
            pointer="row1",
            detail="image=poster.jpg",
            bbox=(0, 0, 10, 10),
            ocr_confidence=0.55,
        )
        claims = claims_from_blocks(
            [block],
            document_id="d1",
            source_kind="poster_ocr",
            settings=self.settings,
            require_delimiter=False,
            locator_kind="text_row",
            base_confidence="medium",
        )
        self.assertEqual(claims[0].extraction_confidence, "low")

    def test_good_ocr_confidence_keeps_the_poster_ceiling(self) -> None:
        block = TextBlock(
            text="开课日期：2027年1月8日",
            pointer="row1",
            detail="image=poster.jpg",
            bbox=(0, 0, 10, 10),
            ocr_confidence=0.97,
        )
        claims = claims_from_blocks(
            [block],
            document_id="d1",
            source_kind="poster_ocr",
            settings=self.settings,
            require_delimiter=False,
            locator_kind="text_row",
            base_confidence="medium",
        )
        self.assertEqual(claims[0].extraction_confidence, "medium")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestRealPosterRows(unittest.TestCase):
    """Rows copied from a real supplier poster set (195 posters, PP-OCRv6).

    These are the rows that produced 49 fabricated claims before the
    geometric rules below existed. A marketing poster is a *metadata grid*, and
    its header row is indistinguishable from a label/value pair by shape alone:
    both are two or more short cells on one line. Position and the value's own
    form are what separate them.
    """

    def test_header_row_is_not_read_as_a_label_value_pair(self) -> None:
        # A four-cell header row: 项目周期 is a header, 开班人数 is a header.
        self.assertEqual(
            scan_line("项目模式 项目周期 开班人数 开课日期", require_delimiter=False),
            [hit for hit in scan_line("项目模式 项目周期 开班人数 开课日期", require_delimiter=False)
             if hit.label in ("项目周期", "开课日期")],
        )
        self.assertEqual(
            scan_line(
                "项目模式 项目周期 开班人数 开课日期",
                require_delimiter=False,
                label_must_lead_row=True,
            ),
            [],
        )

    def test_fragmented_header_row_is_still_refused(self) -> None:
        # Row grouping split the four header cells across bands, so 项目名称
        # ended up leading a three-cell row. The value still starts with a label
        # word, which is what marks it as a header rather than a title.
        self.assertEqual(
            scan_line(
                "项目名称 教授背景 招生状态",
                require_delimiter=False,
                label_must_lead_row=True,
            ),
            [],
        )

    def test_genuine_pair_survives(self) -> None:
        hits = scan_line(
            "开课时间 2026年09月19日", require_delimiter=False, label_must_lead_row=True
        )
        self.assertEqual([(hit.field, hit.value) for hit in hits], [("start_date", "2026年09月19日")])

    def test_bare_academic_title_is_not_a_poster_label(self) -> None:
        # "牛津大学 终身正教授  招生中": 教授 is a job title *value*, and 招生中
        # is an enrollment-status chip. In a handbook "教授：张三" is a real
        # label, so the restriction is row-mode only.
        self.assertEqual(
            scan_line("教授 招生中", require_delimiter=False, label_must_lead_row=True), []
        )
        self.assertEqual(
            [(hit.field, hit.value) for hit in scan_line("教授：张三", require_delimiter=True)],
            [("instructor", "张三")],
        )

    def test_line_mode_is_unaffected_by_the_geometric_rules(self) -> None:
        # Handbook text keeps working: no leftmost requirement, no title filter.
        hits = scan_line("开班人数", require_delimiter=False, label_must_lead_row=True)
        self.assertEqual(hits, [])
        self.assertTrue(scan_line("项目周期：8周", require_delimiter=True))


class TestTemplateSignature(unittest.TestCase):
    def test_stat_tile_family_is_named(self) -> None:
        rows = [
            TextBlock(text="AI+商业分析专题", pointer="row0"),
            TextBlock(text="3周 线上直播 6周 论文辅导 6次 产学研导师课", pointer="row1"),
            TextBlock(text="10 封教授网申推荐信+ 1 篇英文会议论文辅导", pointer="row2"),
        ]
        self.assertEqual(template_signature(rows), ("<no-leading-label>",))

    def test_metadata_grid_family_is_named(self) -> None:
        rows = [TextBlock(text="开课时间 2026年09月19日", pointer="row1")]
        self.assertEqual(template_signature(rows), ("开课时间",))


class TestDeliverableShape(unittest.TestCase):
    """A marketing poster states deliverables as a counted list, not behind a label."""

    def _claim(self, text: str):
        from research_facts.extract import deliverable_shape_claim

        return deliverable_shape_claim(
            TextBlock(text=text, pointer="row2", detail="image=p.jpg"),
            document_id="d1",
            locator_kind="text_row",
        )

    def test_a_counted_deliverable_line_is_read(self) -> None:
        claim = self._claim("10 封教授网申推荐信+ 1 篇英文会议论文辅导")
        self.assertIsNotNone(claim)
        self.assertEqual(claim.field, "output_description")
        self.assertEqual(claim.extractor, "deliverable_shape")
        # A shape rule must not claim the certainty of a labelled read.
        self.assertEqual(claim.extraction_confidence, "low")

    def test_it_is_always_marked_as_a_promise(self) -> None:
        claim = self._claim("10 封教授网申推荐信+ 1 篇英文会议论文辅导")
        self.assertEqual(claim.evidence_kind, "conditional_claim")
        self.assertFalse(claim.has_factual_content)

    def test_the_stat_strip_is_not_a_deliverable(self) -> None:
        # "3周 线上直播 6周 论文辅导" names phases; 论文辅导 is a caption far
        # from its number, and 周 is schedule rather than an artefact.
        self.assertIsNone(self._claim("3周 线上直播 6周 论文辅导 6次 产学研导师课"))

    def test_schedule_and_plain_lines_are_refused(self) -> None:
        for text in ("3周", "共126课时", "1500字左右的项目报告", "牛津大学终身正教授"):
            self.assertIsNone(self._claim(text), text)

    def test_a_line_that_has_a_label_uses_the_labelled_path(self) -> None:
        self.assertIsNone(self._claim("成果形式：10 封推荐信"))

    def test_an_over_long_line_is_refused(self) -> None:
        self.assertIsNone(self._claim("10 封推荐信" + "，以及若干说明" * 20))
