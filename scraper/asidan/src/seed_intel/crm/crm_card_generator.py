from __future__ import annotations

from seed_intel.extraction.schema import ProjectRecord


def generate_crm_card(record: ProjectRecord) -> dict[str, object]:
    name = record.project_name or "该项目"
    return {
        "project_uid": record.project_uid,
        "project_name": record.project_name,
        "project_summary": f"{name}，项目类型：{record.category or '待确认'}，适合年级：{record.target_grade or '待确认'}。",
        "who_should_buy": record.suitable_for or "目标方向、时间安排和项目产出与页面信息匹配的学生。",
        "who_should_not_buy": record.not_suitable_for or "目标不清晰、时间冲突、预算或交付方式不匹配的学生。",
        "opening_script": f"我先不直接推荐{name}，想先确认孩子年级、申请方向和暑假时间是否匹配。",
        "qualification_questions": [
            "学生目前几年级？",
            "目标申请国家和专业方向是什么？",
            "是否已有科研、竞赛、公益或实习经历？",
            "更看重成果产出、机构背书，还是专业探索？",
            "暑假时间是否已经确定？",
            "预算区间大概是多少？",
            "是否能接受线上项目？",
        ],
        "objection_handling": [
            {
                "objection": "价格太贵",
                "response": "先不要只按价格判断，可以看项目产出、适配度、是否服务申请主线三个维度。",
                "next_question": "目前家长更希望项目解决专业探索，还是申请材料丰富度？",
            },
            {
                "objection": "担心项目水",
                "response": "可以先核对主办方、交付形式、成果产出和往期信息，证据不足就不建议直接推进。",
                "next_question": "家长最在意证书、论文/作品，还是过程体验？",
            },
        ],
        "recommended_next_steps": [
            "核对截止日期、价格和交付方式。",
            "判断学生目标方向与项目主题是否一致。",
            "证据不足字段进入人工复核。",
        ],
        "risk_warnings": record.risks or ("需要人工复核" if record.needs_human_review else "不得承诺录取结果或夸大项目含金量。"),
        "required_followup_info": "学生年级、目标方向、时间安排、预算、已有经历。",
        "source_url": record.source_url,
        "evidence": [item.model_dump() for item in record.evidence],
    }
