from __future__ import annotations

from seed_intel.content.compliance_checker import check_compliance
from seed_intel.enrichment.business_scorer import ProjectScore
from seed_intel.extraction.schema import ProjectRecord


def generate_topics(record: ProjectRecord, score: ProjectScore, limit: int = 5) -> list[dict[str, object]]:
    name = record.project_name or "这个项目"
    grade = record.target_grade or "目标学生"
    templates = [
        ("项目解读型", f"{grade}如何判断{name}值不值得做？", "适配度判断"),
        ("避坑型", f"别只看项目名，报名{name}前先确认这5件事", "风险识别"),
        ("截止提醒型", f"{name}报名节点前，家长需要问清楚什么？", "时间规划"),
        ("专业探索型", f"想做{record.category or '背景提升'}，{name}适合哪些学生？", "方向匹配"),
        ("清单型", f"判断{name}含金量，可以看这几个维度", "项目筛选"),
    ]
    topics: list[dict[str, object]] = []
    for style, title, angle in templates[:limit]:
        compliance = check_compliance(title)
        topics.append({
            "project_uid": record.project_uid,
            "project_name": record.project_name,
            "title": title,
            "title_style": style,
            "content_angle": angle,
            "target_audience": grade,
            "user_pain_point": "不知道项目是否适配申请主线，担心投入时间和预算后效果不明确。",
            "key_selling_point": record.highlights or record.certificate or record.organizer or "页面信息需进一步人工复核。",
            "opening_hook": "报名项目前，先不要只看名称和背书。",
            "outline": [
                "目标人群",
                "项目是什么",
                "为什么值得关注",
                "适合谁",
                "不适合谁",
                "家长该问什么问题",
                "下一步咨询引导",
            ],
            "cover_text": title[:24],
            "cta": "需要判断适配度，可以带着年级、目标方向和时间安排来咨询。",
            "wechat_conversion_script": "先确认学生年级、目标国家/专业、已有经历和暑假时间，再判断是否推荐。",
            "compliance_risk": compliance["risk_level"],
            "priority_score": score.content_potential_score,
            "source_url": record.source_url,
        })
    return topics
