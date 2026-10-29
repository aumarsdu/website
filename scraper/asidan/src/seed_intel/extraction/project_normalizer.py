from __future__ import annotations

from seed_intel.extraction.schema import ProjectRecord


def normalize_delivery_mode(record: ProjectRecord) -> str | None:
    text = " ".join(filter(None, [record.location, record.description])).lower()
    has_online = "线上" in text or "online" in text
    has_offline = "线下" in text or "offline" in text
    if has_online and has_offline:
        return "hybrid"
    if has_online:
        return "online"
    if has_offline:
        return "offline"
    return record.delivery_mode


def normalize_project(record: ProjectRecord) -> ProjectRecord:
    record.delivery_mode = normalize_delivery_mode(record)
    if record.price and ("¥" in record.price or "￥" in record.price or "人民币" in record.price or "RMB" in record.price.upper()):
        record.currency = "CNY"
    return record
