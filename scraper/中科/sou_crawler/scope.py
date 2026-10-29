from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


TARGET_ENTRY_URLS = (
    "https://jf.cas-harbour.cn/avocado/#/",
    "https://jf.cas-harbour.cn/mini/#/",
)
HARBOUR_HOST = "jf.cas-harbour.cn"
HARBOUR_TOPIC_LIST_URL = f"https://{HARBOUR_HOST}/zhongkehaobo/v2/topic/list"
HARBOUR_TOPIC_DETAIL_URL = f"https://{HARBOUR_HOST}/zhongkehaobo/v2/topic/detail"
HARBOUR_TOPIC_CATEGORY_URL = f"https://{HARBOUR_HOST}/zhongkehaobo/v2/topic/category"


def is_topic_list_source(value: Any) -> bool:
    return normalized_path(value) == normalized_path(HARBOUR_TOPIC_LIST_URL)


def is_topic_detail_source(value: Any) -> bool:
    return normalized_path(value).startswith(f"{normalized_path(HARBOUR_TOPIC_DETAIL_URL)}/")


def is_topic_source(value: Any) -> bool:
    return is_topic_list_source(value) or is_topic_detail_source(value)


def is_allowed_raw_source(value: Any) -> bool:
    return is_topic_source(value) or normalized_path(value) == normalized_path(HARBOUR_TOPIC_CATEGORY_URL)


def normalized_path(value: Any) -> str:
    parsed = urlparse(str(value or ""))
    if parsed.netloc != HARBOUR_HOST:
        return ""
    return re.sub(r"/{2,}", "/", parsed.path)
