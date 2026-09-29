"""direction 模块单测（需求 §4 + §8 决议 D1-D7）。全部离线。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poster_index import common, direction  # noqa: E402


class LabelExtractionTest(unittest.TestCase):
    def test_prefix_strip_and_label(self):
        self.assertEqual(direction.raw_label("【研助起航计划】人工智能 ChatGPT专题：计算语言模型"), "人工智能 ChatGPT")
        self.assertEqual(direction.raw_label("金融工程专题：期权定价"), "金融工程")
        self.assertEqual(direction.raw_label("EE电子工程 模拟电路专题：信号"), "EE电子工程 模拟电路")
        self.assertEqual(direction.raw_label("致理计划：经济学专题：土地经济学"), "经济学")
        self.assertIsNone(direction.raw_label("无冒号的超长标题" * 10))

    def test_suffix_variants(self):
        self.assertEqual(direction.raw_label("人工智能与机器学习课题：xxx"), "人工智能与机器学习")


class MatchingOrderTest(unittest.TestCase):
    def test_row_order_financial_econ(self):
        r = direction.classify("金融经济学专题：资产定价")
        self.assertEqual(r["direction"], "金融与投资")
        self.assertEqual(r["directionBasis"]["source"], "label")

    def test_cross_block_priority_with_secondary(self):
        r = direction.classify("商业分析与人工智能专题：机器学习在商业中的应用")
        self.assertEqual(r["direction"], "人工智能与机器学习")  # D6: 行序优先
        self.assertEqual(r["directionSecondary"], "管理与商业分析")

    def test_title_fallback_when_label_misses(self):
        r = direction.classify("某个稀奇古怪的标签：深度学习在金融中的应用")
        self.assertEqual(r["directionBasis"]["source"], "title")
        self.assertEqual(r["direction"], "人工智能与机器学习")


class AbbreviationTest(unittest.TestCase):
    def test_abbrev_with_corroboration(self):
        r = direction.classify("EE电子工程 模拟电路专题：信号与系统")
        self.assertEqual(r["direction"], "电子电气与通信")

    def test_bare_abbrev_pending(self):
        r = direction.classify("AI专题：一场对话")
        self.assertEqual(r["direction"], "待确认")
        self.assertEqual(r["subject"], "其他")

    def test_abbrev_repeated_counts_as_corroboration(self):
        r = direction.classify("ECE 与 ECE 系统设计")
        self.assertNotEqual(r["direction"], "待确认")


class CorpusFallbackTest(unittest.TestCase):
    def test_corpus_frequency(self):
        title = "跨界项目：从零到一"  # 标签与标题均无命中
        corpus = "本课题聚焦金融风险管理、投资组合与金融市场，涉及金融工程与量化投资。"
        r = direction.classify(title, corpus=corpus)
        self.assertEqual(r["directionBasis"]["source"], "corpus")
        self.assertEqual(r["direction"], "金融与投资")

    def test_corpus_min_hits(self):
        r = direction.classify("跨界项目：从零到一", corpus="简单介绍")
        self.assertEqual(r["direction"], "待确认")

    def test_corpus_head_limit(self):
        # 200 字后才出现的关键词不参与（D5）
        filler = "本项目介绍" * 45
        r = direction.classify("跨界项目：从零到一", corpus=filler + "深度学习机器学习")
        self.assertEqual(r["direction"], "待确认")


class OverrideTest(unittest.TestCase):
    def test_override_precedence_and_subject(self):
        ov = {"集思未来:42": "心理学"}
        r = direction.classify("金融工程专题：期权", override_key="集思未来:42", overrides=ov)
        self.assertEqual(r["direction"], "心理学")
        self.assertEqual(r["subject"], "人文社科")
        self.assertEqual(r["directionBasis"]["source"], "override")

    def test_invalid_override_ignored(self):
        r = direction.classify("金融工程专题：期权", override_key="X:1", overrides={"X:1": "不存在的方向"})
        self.assertEqual(r["direction"], "金融与投资")


class ReservedTest(unittest.TestCase):
    def test_career_direction_maps_to_other(self):
        r = direction.classify("职业通途计划——产品策划项目")
        self.assertEqual(r["direction"], "职业与实习")
        self.assertEqual(r["subject"], "其他")


class ContractTest(unittest.TestCase):
    def test_build_item_accepts_new_fields(self):
        item = common.build_item(
            supplier="X", recordId="1", title="t",
            subject="人文社科", subjectSource="override", subjectOriginal="理工科",
            direction="心理学", directionSecondary=None,
            directionBasis={"source": "override", "keyword": None, "rawLabel": None},
            posterVariant="raw", posterPath="/p.jpg", posterSha256="h")
        self.assertEqual(item["direction"], "心理学")

    def test_build_item_rejects_bad_direction(self):
        with self.assertRaises(common.IndexItemError):
            common.build_item(
                supplier="X", recordId="1", title="t", subject="人文社科",
                subjectSource="label", subjectOriginal="理工科",
                direction="风水学", directionSecondary=None, directionBasis={"source": "label"},
                posterVariant="raw", posterPath="/p.jpg", posterSha256="h")

    def test_build_item_rejects_legacy_subject_source(self):
        with self.assertRaises(common.IndexItemError):
            common.build_item(
                supplier="X", recordId="1", title="t", subject="人文社科",
                subjectSource="supplier", subjectOriginal="理工科",
                direction="心理学", directionSecondary=None, directionBasis={"source": "label"},
                posterVariant="raw", posterPath="/p.jpg", posterSha256="h")


class SummarizeTest(unittest.TestCase):
    def test_report_quartet(self):
        items = [
            {"direction": "金融与投资", "schoolBegins": "2027-01-01", "recordId": "1", "title": "a",
             "directionBasis": {"source": "label", "rawLabel": "金融工程"}},
            {"direction": "待确认", "schoolBegins": None, "recordId": "2", "title": "b",
             "directionBasis": {"source": "corpus", "rawLabel": None}},
        ]
        s = direction.summarize(items, today="2026-10-01")
        self.assertEqual(s["direction_distribution"]["金融与投资"], {"courses": 1, "open": 1})
        self.assertEqual(len(s["direction_pending_review"]), 1)
        self.assertEqual(s["direction_basis_sources"], {"label": 1, "corpus": 1})
        self.assertEqual(s["direction_label_mapping"]["金融工程"], {"direction": "金融与投资", "count": 1})


class TaxonomyFileTest(unittest.TestCase):
    def test_file_valid_and_subjects(self):
        tax = json.loads(direction.TAXONOMY_PATH.read_text(encoding="utf-8"))
        subjects = {d["subject"] for d in tax["directions"]}
        self.assertTrue(subjects <= set(common.SUBJECTS) | {"其他"})
        self.assertEqual(len({d["direction"] for d in tax["directions"]}), len(tax["directions"]))


if __name__ == "__main__":
    unittest.main()
