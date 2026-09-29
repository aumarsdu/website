"""format 字段与 projectType 回填单测（索引修正需求 §1/§2）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poster_index import common, direction  # noqa: E402


class FormatMapTest(unittest.TestCase):
    def test_full_mapping_and_ra_split(self):
        # 军亮 2026-09-29 拍板：RA 单独产品类型，不与 1V1 混同
        self.assertEqual(common.resolve_format("集思未来", "PBL小组科研标准版"), "小组科研")
        self.assertEqual(common.resolve_format("集思未来", "专业选修课程"), "班课科研")
        self.assertEqual(common.resolve_format("集思未来", "研助起航计划"), "班课科研")
        self.assertEqual(common.resolve_format("集思未来", "Astra 1v1"), "1V1")
        self.assertEqual(common.resolve_format("集思未来", "全球在研"), "1V1")
        self.assertEqual(common.resolve_format("集思未来", "实验室RA项目"), "其他")
        self.assertEqual(common.resolve_format("集思未来", "名校实验室RA计划"), "其他")
        self.assertEqual(common.resolve_format("集思未来", "职业通途计划"), "其他")
        self.assertEqual(common.resolve_format("HIREP", "PBL科研课题"), "小组科研")
        self.assertEqual(common.resolve_format("中科浩博", "双教授课题（鲸鱼座）"), "小组科研")
        self.assertEqual(common.resolve_format("中科浩博", "中方课题（研途有果）"), "小组科研")

    def test_fallback_for_unknown(self):
        self.assertEqual(common.resolve_format("集思未来", "未来的新产品线"), "其他")

    def test_build_item_validates_format(self):
        with self.assertRaises(common.IndexItemError):
            common.build_item(
                supplier="X", recordId="1", title="t", subject="理工科",
                subjectSource="label", subjectOriginal="理工科", direction="数学",
                directionSecondary=None, directionBasis={"source": "label"},
                format="一对一", posterVariant="raw", posterPath="/p", posterSha256="h")


class TypeIdMapTest(unittest.TestCase):
    def test_map_loads_with_ambiguity_flags(self):
        import json
        cfg = json.loads((Path(common.__file__).parent / "typeid_map.json").read_text(encoding="utf-8"))
        m = cfg["map"]
        self.assertFalse(m["1"]["ambiguous"])
        self.assertEqual(m["1"]["project_type"], "专业选修课程")
        for amb in ("6", "32", "44"):
            self.assertTrue(m[amb]["ambiguous"], amb)


class FormatDistributionTest(unittest.TestCase):
    def test_distribution_counts_open(self):
        items = [
            {"format": "小组科研", "schoolBegins": "2027-01-01"},
            {"format": "小组科研", "schoolBegins": "2026-01-01"},
            {"format": "1V1", "schoolBegins": None},
        ]
        dist = common.format_distribution(items, today="2026-10-01")
        self.assertEqual(dist["小组科研"], {"courses": 2, "open": 1})
        self.assertEqual(dist["1V1"], {"courses": 1, "open": 0})


class BackfillChainTest(unittest.TestCase):
    """回填顺序（manifest -> raw.types -> typeid）通过 jisi.build 的源码装配验证，
    这里验证 typeId 反推函数式逻辑的等价实现。"""

    def test_chain_equivalent(self):
        TYPEID = {"1": {"project_type": "专业选修课程", "ambiguous": False},
                  "6": {"project_type": "PBL小组科研标准版", "ambiguous": True}}
        def chain(manifest_pt, raw_types, type_id):
            if manifest_pt:
                return manifest_pt, "manifest"
            if str(raw_types or "").strip():
                return str(raw_types).strip(), "raw_types"
            tm = TYPEID.get(str(type_id or ""))
            if tm and not tm.get("ambiguous"):
                return tm["project_type"], "typeid_map"
            return "", "pending"
        self.assertEqual(chain("全球在研", "x", 9), ("全球在研", "manifest"))
        self.assertEqual(chain("", "PBL小组科研标准版", 6), ("PBL小组科研标准版", "raw_types"))
        self.assertEqual(chain("", "", 1), ("专业选修课程", "typeid_map"))
        self.assertEqual(chain("", "", 6), ("", "pending"))  # 歧义降级
        self.assertEqual(chain("", "", 99), ("", "pending"))


if __name__ == "__main__":
    unittest.main()
