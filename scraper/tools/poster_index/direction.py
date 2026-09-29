"""细分方向打标（需求 细分方向标签 §4 + §8 决议 D1-D8）。

纯标准库；词表来自 direction_taxonomy.json（数组顺序即优先级，D6）。
判定次序：override → 原始标签 → 整标题 → 语料前200字（词频，D5）。
缩写佐证（D4）：某方向命中全为 abbrev 型时，需同文本存在任一非 abbrev 关键词
或该缩写出现 ≥2 次，否则该方向命中作废。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .common import OUTPUT_DIR

TAXONOMY_PATH = Path(__file__).resolve().parent / "direction_taxonomy.json"
DIRECTION_OVERRIDES_PATH = OUTPUT_DIR / "direction_overrides.json"
CORPUS_HEAD = 200
MIN_CORPUS_HITS = 2


@lru_cache(maxsize=1)
def load_taxonomy() -> dict[str, Any]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _compiled() -> list[dict[str, Any]]:
    """预编译关键词匹配器；保留词表顺序（D6）。"""
    out = []
    for entry in load_taxonomy()["directions"]:
        matchers = []
        for kw in entry["keywords"]:
            if isinstance(kw, dict):
                matchers.append((kw["kw"], True))
            else:
                matchers.append((kw, False))
        out.append({"subject": entry["subject"], "direction": entry["direction"], "matchers": matchers})
    return out


def allowed_directions() -> tuple[str, ...]:
    tax = load_taxonomy()
    return tuple(d["direction"] for d in tax["directions"]) + tuple(tax["reserved"])


@lru_cache(maxsize=1)
def _allowed_set() -> frozenset[str]:
    return frozenset(allowed_directions())


def direction_subject(direction: str) -> str:
    for entry in _compiled():
        if entry["direction"] == direction:
            return entry["subject"]
    return "其他"  # 保留值（职业与实习/待确认）→ 其他（D7）


def _kw_pattern(kw: str) -> re.Pattern[str]:
    if re.fullmatch(r"[A-Za-z0-9]+", kw):
        return re.compile(rf"(?<![A-Za-z0-9]){re.escape(kw)}(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(re.escape(kw))


def _hits_in_text(text: str) -> list[dict[str, Any]]:
    """返回按词表顺序排列的有效方向命中（含 D4 佐证过滤与命中次数）。"""
    if not text:
        return []
    has_non_abbrev_word = False
    counts_by_kw: dict[tuple[str, str], int] = {}
    for entry in _compiled():
        for kw, is_abbrev in entry["matchers"]:
            n = len(_kw_pattern(kw).findall(text))
            if n:
                counts_by_kw[(entry["direction"], kw)] = n
                if not is_abbrev:
                    has_non_abbrev_word = True
    hits = []
    for entry in _compiled():
        kws = []
        valid = False
        for kw, is_abbrev in entry["matchers"]:
            n = counts_by_kw.get((entry["direction"], kw), 0)
            if not n:
                continue
            kws.append(kw)
            if not is_abbrev:
                valid = True
            elif n >= 2:
                valid = True  # 缩写自身出现≥2次
        if kws and not valid and has_non_abbrev_word:
            valid = True  # 文本内存在任一非 abbrev 关键词（任意方向）作佐证（D4）
        if valid:
            hits.append({"direction": entry["direction"], "keywords": kws,
                         "freq": sum(counts_by_kw[(entry["direction"], k)] for k in kws)})
    return hits


def strip_prefix(title: str) -> str:
    tax = load_taxonomy()
    t = (title or "").strip()
    for pat in tax.get("prefix_patterns", []):
        t = re.sub(pat, "", t).strip()
    for prefix in tax.get("prefixes", []):
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
    # 「大学名 + 空格」开头的 RA 项目（§4.1）
    t = re.sub(r"^[A-Za-z\s·]{4,40}\s+[A-Za-z][A-Za-z\s&·]{2,30}(?=[\u4e00-\u9fff])", "", t, count=1).strip()
    return t


def raw_label(title: str) -> str | None:
    tax = load_taxonomy()
    stripped = strip_prefix(title)
    seg = re.split(r"[：:]", stripped, 1)[0].strip()
    for suffix in sorted(tax.get("label_suffixes", []), key=len, reverse=True):
        if seg.endswith(suffix):
            seg = seg[: -len(suffix)].strip()
    if 1 <= len(seg) <= 30 and re.search(r"[\u4e00-\u9fffA-Za-z]", seg):
        return seg
    return None


def load_direction_overrides() -> dict[str, str]:
    if not DIRECTION_OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(DIRECTION_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict) and isinstance(data.get("overrides"), dict):
        data = data["overrides"]
    allowed = set(allowed_directions())
    return {k: v for k, v in data.items() if isinstance(v, str) and v in allowed}


def classify(
    title: str,
    *,
    corpus: str = "",
    override_key: str | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """返回 {direction, directionSecondary, directionBasis, subject}。"""
    overrides = overrides if overrides is not None else load_direction_overrides()
    label = raw_label(title)
    stripped = strip_prefix(title)

    def basis(source: str, keyword: str | None, hits: list[dict[str, Any]]) -> dict[str, Any]:
        main = hits[0]
        secondary = hits[1]["direction"] if len(hits) > 1 else None
        return {
            "direction": main["direction"],
            "directionSecondary": secondary,
            "directionBasis": {"source": source, "keyword": keyword or (main["keywords"] or [None])[0], "rawLabel": label},
            "subject": direction_subject(main["direction"]),
        }

    if override_key and overrides.get(override_key) in _allowed_set():
        d = overrides[override_key]
        return {"direction": d, "directionSecondary": None,
                "directionBasis": {"source": "override", "keyword": None, "rawLabel": label},
                "subject": direction_subject(d)}

    # 佐证与命中统一在标题文本内判定（避免标签拼接导致缩写双计，D4）
    title_hits = _hits_in_text(stripped)

    # 第 1 步：原始标签命中（方向的关键词出现在标签里）
    if label:
        label_only = [h for h in title_hits if any(_kw_pattern(k).search(label) for k in h["keywords"])]
        if label_only:
            kw = next(k for h in label_only for k in h["keywords"] if _kw_pattern(k).search(label))
            return basis("label", kw, label_only)

    # 第 2 步：整条标题
    if title_hits:
        return basis("title", None, title_hits)

    # 第 3 步：语料前 200 字，词频最高（平票按行序），总命中≥2（D5）
    head = (corpus or "")[:CORPUS_HEAD]
    hits = _hits_in_text(head)
    if hits and sum(h["freq"] for h in hits) >= MIN_CORPUS_HITS:
        ranked = sorted(hits, key=lambda h: -h["freq"])
        main = ranked[0]
        secondary = ranked[1]["direction"] if len(ranked) > 1 else None
        return {"direction": main["direction"], "directionSecondary": secondary,
                "directionBasis": {"source": "corpus", "keyword": main["keywords"][0], "rawLabel": label},
                "subject": direction_subject(main["direction"])}

    return {"direction": "待确认", "directionSecondary": None,
            "directionBasis": {"source": "corpus", "keyword": None, "rawLabel": label},
            "subject": "其他"}


def summarize(items: list[dict[str, Any]], *, today: str | None = None) -> dict[str, Any]:
    """报告四件套（§5）：方向分布(含可报名)、待确认清单、依据来源分布、标签映射表。"""
    from datetime import date as _date

    today = today or _date.today().isoformat()
    dist: dict[str, dict[str, int]] = {}
    pending: list[dict[str, str]] = []
    basis_sources: dict[str, int] = {}
    label_map: dict[str, dict[str, Any]] = {}
    for item in items:
        direction = item["direction"]
        slot = dist.setdefault(direction, {"courses": 0, "open": 0})
        slot["courses"] += 1
        begins = item.get("schoolBegins")
        if begins and begins > today:
            slot["open"] += 1
        src = (item.get("directionBasis") or {}).get("source") or "?"
        basis_sources[src] = basis_sources.get(src, 0) + 1
        label = (item.get("directionBasis") or {}).get("rawLabel")
        if label:
            entry = label_map.setdefault(label, {"direction": direction, "count": 0})
            entry["count"] += 1
        if direction == "待确认":
            pending.append({"recordId": item.get("recordId"), "title": item.get("title"),
                            "rawLabel": label or ""})
    return {
        "direction_distribution": dist,
        "direction_pending_review": pending,
        "direction_basis_sources": basis_sources,
        "direction_label_mapping": label_map,
    }
