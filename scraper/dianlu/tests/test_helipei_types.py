from dianedu_archiver.helipei_types import (
    infer_credit,
    infer_delivery_mode,
    infer_library_scope,
    infer_residential,
    standardize_category,
)


def test_standardize_category_rules_in_priority_order():
    assert standardize_category("夏校等", "有学分大学营", "某项目") == ("大学夏校", "有学分大学夏校")
    assert standardize_category("夏校等", "无学分大学营", "pre-college week") == ("大学夏校", "无学分大学夏校")
    assert standardize_category(None, "在线夏校", None) == ("线上项目", "线上夏校")
    assert standardize_category(None, "中学营", None) == ("低龄夏校", "低龄/中学营")
    assert standardize_category(None, "辩论营", None) == ("主题营", "辩论/演讲/领导力营")
    assert standardize_category(None, "插班", None) == ("插班项目", "插班")
    assert standardize_category(None, "海外科研", "科研实习") == ("科研型夏校", "科研项目")
    assert standardize_category("夏校等", "其他类型", None) == ("夏校项目", "其他类型")
    assert standardize_category("公益", "其他类型", "无关键词") == ("相邻项目", "其他类型")


def test_infer_library_scope_buckets():
    assert infer_library_scope("夏校等", None) == "primary_summer"
    assert infer_library_scope("插班", None) == "extension_join_class"
    assert infer_library_scope(None, "探校") == "extension_campus_visit"
    assert infer_library_scope(None, "海外科研") == "adjacent_enrichment"
    assert infer_library_scope("其他", "语言营") == "summer_related"


def test_infer_delivery_mode_and_residential_and_credit():
    assert infer_delivery_mode(None, "在线科研营", None) == "online"
    assert infer_delivery_mode(None, "混合式教学", None) == "hybrid"
    assert infer_delivery_mode("精英夏校", "线下集训", "面授") == "offline"

    assert infer_residential(True, None, None, None) == "residential"
    assert infer_residential(None, "低龄走读营", None, None) == "day"
    assert infer_residential(None, None, "boarding school", None) == "residential"
    assert infer_residential(None, None, "线上课程", "online") == "online"
    assert infer_residential(None, None, None, None) == "unknown"

    assert infer_credit(True, None, None, None) == "credit"
    assert infer_credit(None, "有学分大学营", None, None) == "credit"
    assert infer_credit(None, None, "non-credit program", None) == "non_credit"
    assert infer_credit(None, None, None, None) == "unknown"
