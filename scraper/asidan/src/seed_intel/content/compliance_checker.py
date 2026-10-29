from __future__ import annotations

HIGH_RISK_TERMS = [
    "保录取",
    "guaranteed admission",
    "guaranteed offer",
    "100%录取",
    "必上",
    "必拿",
    "内推保录",
    "官方保录",
    "名校直录",
    "无条件录取",
    "保藤校",
    "稳赚",
]


def check_compliance(text: str) -> dict[str, object]:
    lowered = text.lower()
    found = [term for term in HIGH_RISK_TERMS if term.lower() in lowered]
    if found:
        return {
            "risk_level": "high",
            "terms": found,
            "suggestion": "删除录取/结果承诺类表达，改为基于证据的适配度说明。",
            "needs_human_review": True,
        }
    return {"risk_level": "low", "terms": [], "suggestion": None, "needs_human_review": False}
