"""poster_index 离线单元测试（全部使用临时目录夹具，不触真实素材库）。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poster_index import common  # noqa: E402


def make_image(path: Path, content: bytes = b"img") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class MapSubjectTest(unittest.TestCase):
    def test_mapping_table(self):
        self.assertEqual(common.map_subject("文科"), "人文社科")
        self.assertEqual(common.map_subject("理科"), "理工科")
        self.assertEqual(common.map_subject("工科"), "理工科")
        self.assertEqual(common.map_subject("商科"), "金融商科")
        self.assertEqual(common.map_subject("计算机"), "计算机与人工智能")
        self.assertEqual(common.map_subject("人文"), "人文社科")
        self.assertEqual(common.map_subject("计算机与人工智能"), "计算机与人工智能")
        self.assertIsNone(common.map_subject("未知分类"))
        self.assertIsNone(common.map_subject(None))

    def test_enum_guard(self):
        with self.assertRaises(common.IndexItemError):
            common.build_item(supplier="X", subject="文科", subjectSource="supplier",
                              posterVariant="raw", recordId="r", title="t",
                              posterPath="/p.jpg", posterSha256="h")


class SelectPosterTest(unittest.TestCase):
    def test_manifest_sha_wins_even_if_raw(self):
        raw = make_image(Path("/tmp/pi_a/raw.jpg"), b"raw")
        fin = make_image(Path("/tmp/pi_a/Finish_x.jpg"), b"fin")
        import hashlib
        want = hashlib.sha256(b"raw").hexdigest()
        picked, variant, cands = common.select_poster([raw, fin], manifest_sha256=want)
        self.assertEqual(picked, raw)
        self.assertEqual(variant, "raw")
        self.assertEqual(len(cands), 2)

    def test_processed_preferred_without_manifest(self):
        raw = make_image(Path("/tmp/pi_b/x.jpg"), b"raw")
        fin = make_image(Path("/tmp/pi_b/Finish_x.jpg"), b"fin")
        picked, variant, _ = common.select_poster([raw, fin])
        self.assertEqual(picked, fin)
        self.assertEqual(variant, "processed")

    def test_empty_and_non_image_rejected(self):
        empty = make_image(Path("/tmp/pi_c/a.jpg"), b"")
        notimg = make_image(Path("/tmp/pi_c/b.txt"), b"x")
        picked, _v, cands = common.select_poster([empty, notimg])
        self.assertIsNone(picked)
        self.assertEqual(cands, [])


class DedupTest(unittest.TestCase):
    def test_keeps_latest_crawled(self):
        records = [
            {"id": "a", "crawled_at": "2026-01-01", "v": 1},
            {"id": "a", "crawled_at": "2026-03-01", "v": 3},
            {"id": "a", "crawled_at": "2026-02-01", "v": 2},
            {"id": "", "crawled_at": "2026-04-01", "v": 9},
        ]
        out = common.dedup_keep_latest(records, key_fn=lambda r: r["id"], crawled_fn=lambda r: r["crawled_at"])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["v"], 3)


class FindTest(unittest.TestCase):
    def _items(self):
        return [
            {"supplier": "S", "recordId": "1", "title": "甲", "subject": "理工科",
             "projectType": "T", "schoolBegins": "2026-10-01"},
            {"supplier": "S", "recordId": "2", "title": "乙", "subject": "金融商科",
             "projectType": "T", "schoolBegins": "2026-09-01"},
            {"supplier": "S", "recordId": "3", "title": "丙", "subject": "理工科",
             "projectType": "U", "schoolBegins": None},
        ]

    def test_filters_and_sort(self):
        out = common.find_in_index(self._items(), subject="理工科", open_only=True, today="2026-09-28")
        self.assertEqual([i["recordId"] for i in out], ["1"])
        out = common.find_in_index(self._items(), begins_from="2026-09-15", today="2026-09-28")
        self.assertEqual([i["recordId"] for i in out], ["1"])  # 无日期不落入区间
        out = common.find_in_index(self._items(), limit=1, today="2026-09-28")
        self.assertEqual(out[0]["recordId"], "2")


class AtomicWriteTest(unittest.TestCase):
    def test_write_and_replace(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "x.json"
            original = common.OUTPUT_DIR
            try:
                common.OUTPUT_DIR = Path(tmp)
                common.write_index_and_report("测试", [{"recordId": "1"}], {"a": 1})
                self.assertTrue((Path(tmp) / "测试.index.json").exists())
                doc = json.loads((Path(tmp) / "测试.index.json").read_text())
                self.assertEqual(doc["items"][0]["recordId"], "1")
                leftovers = [p.name for p in Path(tmp).iterdir() if ".tmp" in p.name]
                self.assertEqual(leftovers, [])
            finally:
                common.OUTPUT_DIR = original


if __name__ == "__main__":
    unittest.main()
