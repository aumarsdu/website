from __future__ import annotations

import re
from urllib.parse import urlsplit

from seed_intel.common.hashing import stable_text_hash
from seed_intel.common.url_utils import extract_domain
from seed_intel.extraction.schema import Evidence, ParsedPage, ProjectRecord

CATEGORY_RULES: list[tuple[str, str]] = [
    ("科研项目", r"科研|research|paper|publication|课题"),
    ("论文发表", r"论文|发表|journal|publication"),
    ("国际竞赛", r"竞赛|challenge|competition|olympiad|奥林匹克"),
    ("世界名校夏校", r"夏校|summer school|summer program|暑校"),
    ("国际研学", r"研学|study tour|camp|海外"),
    ("公益项目", r"公益|volunteer|public welfare|志愿"),
    ("专业实践", r"实习|实践|internship|professional practice"),
    ("英语测评", r"英语|English|assessment|测评"),
    ("音乐艺术", r"音乐|music|艺术|festival"),
    ("商科挑战", r"商科|business|economics|经济"),
    ("理工实验室", r"STEM|lab|实验室|工程|理工"),
]

FIELD_PATTERNS: dict[str, list[str]] = {
    "application_deadline": [
        r"(?:报名截止|申请截止|截止日期|Deadline|Application Deadline)[：:\s]*([^\n。；;]{4,80})",
    ],
    "start_date": [
        r"(?:项目时间|活动时间|Start Date|项目日期)[：:\s]*([^\n。；;]{4,100})",
    ],
    "target_age": [
        r"(?:适合年龄|适合学生年龄|Age)[：:\s]*([^\n。；;]{2,80})",
    ],
    "target_grade": [
        r"(?:适合年级|适合学生|参与对象|参赛对象|Eligibility)[：:\s]*([^\n。；;]{2,120})",
        r"(G(?:rade)?\s*\d{1,2}\s*[-–至到]\s*G?(?:rade)?\s*\d{1,2})",
        r"(\d{1,2}\s*[-–至到]\s*\d{1,2}年级)",
        r"(高中生|初中生|小学生|大学生)",
    ],
    "price": [
        r"((?:¥|￥|RMB|人民币)\s*[\d,]+(?:\.\d+)?)",
        r"(?:费用|项目费用|price|tuition|fee)[：:\s]*([^\n。；;]{2,80})",
    ],
    "location": [
        r"(?:地点|项目地点|举办地点|Location)[：:\s]*([^\n。；;]{2,80})",
        r"(线上|线下|Online|Offline|北京|上海|深圳|美国|英国|新加坡|香港|海外)",
    ],
    "organizer": [
        r"(?:主办方|主办单位|Organizer)[：:\s]*([^\n。；;]{2,80})",
    ],
    "certificate": [
        r"(证书|certificate|结业证明|成果证书)[^\n。；;]{0,80}",
    ],
}


def _clean_project_name(title: str | None, h1: str | None) -> str | None:
    candidates = [h1, title]
    for candidate in candidates:
        if not candidate:
            continue
        name = candidate.strip()
        if "项目简介" in name or name.strip("—- ") in {"项目简介", "报名信息", "联系我们"}:
            continue
        return name.split(" - 阿思丹", 1)[0].strip()
    if title:
        return title.split(" - 阿思丹", 1)[0].strip()
    return None


def _first_evidence(field_name: str, patterns: list[str], text: str, source_url: str) -> tuple[str | None, Evidence | None]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1) if match.groups() else match.group(0)
        evidence_text = match.group(0).strip()
        return value.strip(), Evidence(
            field_name=field_name,
            value=value.strip(),
            evidence_text=evidence_text,
            source_url=source_url,
            confidence=0.85,
            extractor="rule",
        )
    return None, None


def _category(text: str, source_url: str) -> tuple[str, Evidence]:
    for category, pattern in CATEGORY_RULES:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return category, Evidence(
                field_name="category",
                value=category,
                evidence_text=match.group(0),
                source_url=source_url,
                confidence=0.75,
                extractor="rule",
            )
    return "其他", Evidence(
        field_name="category",
        value="其他",
        evidence_text=None,
        source_url=source_url,
        confidence=0.5,
        extractor="rule",
    )


def extract_project_from_page(page: ParsedPage) -> ProjectRecord:
    text = page.body_text
    evidence: list[Evidence] = []
    fields: dict[str, str | None] = {}

    project_name = _clean_project_name(page.title, page.h1)
    if project_name:
        evidence.append(Evidence(
            field_name="project_name",
            value=project_name,
            evidence_text=project_name,
            source_url=page.source_url,
            confidence=0.95,
            extractor="rule",
        ))

    category, category_evidence = _category(text, page.source_url)
    evidence.append(category_evidence)

    for field_name, patterns in FIELD_PATTERNS.items():
        value, item = _first_evidence(field_name, patterns, text, page.source_url)
        fields[field_name] = value
        if item:
            evidence.append(item)

    confidence = sum(item.confidence for item in evidence) / max(len(evidence), 1)
    needs_review = (
        not project_name
        or category == "其他"
        or not fields.get("target_grade")
        or confidence < 0.75
    )
    domain = extract_domain(page.source_url)
    uid_source = f"{domain}|{project_name or urlsplit(page.source_url).path}|{fields.get('application_deadline') or ''}"
    return ProjectRecord(
        project_uid=stable_text_hash(uid_source)[:16],
        project_name=project_name,
        category=category,
        target_grade=fields.get("target_grade"),
        target_age=fields.get("target_age"),
        start_date=fields.get("start_date"),
        application_deadline=fields.get("application_deadline"),
        location=fields.get("location"),
        organizer=fields.get("organizer"),
        certificate=fields.get("certificate"),
        price=fields.get("price"),
        price_notes=None if fields.get("price") else "页面未明确披露",
        pdf_links=page.pdf_urls,
        image_links=page.image_urls,
        source_url=page.source_url,
        source_title=page.title,
        source_domain=domain,
        extraction_method="rule",
        extraction_confidence=round(confidence, 3),
        evidence=evidence,
        needs_human_review=needs_review,
        content_hash=stable_text_hash(text),
    )
