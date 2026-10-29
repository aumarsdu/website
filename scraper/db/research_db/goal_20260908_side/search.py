"""T11 internal search over the candidate corpus.

Deterministic, whitelist-sorted, pagination-stable search returning one card
per source record. Unknown dates/prices are excluded from date/price filters
by default. Local-only: no public HTTP routes are provided by this module.
"""

from __future__ import annotations

from typing import Any

import pg_candidate

SORT_WHITELIST = {
    "identity": "r.identity_key",
    "title": "(b.business ->> 'title')",
}
DEFAULT_PAGE_SIZE = 20


class SearchError(ValueError):
    """The search request violated the whitelist or parameter contract."""


def _escape_like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    if "'" in escaped:
        raise SearchError("contract_invalid")
    return escaped


def _literal(value: str) -> str:
    if "'" in value or ";" in value or "$$" in value:
        raise SearchError("contract_invalid")
    return f"'{value}'"


def search(database: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run one internal search; returns cards, total and the page slice."""
    page = int(params.get("page", 1))
    page_size = int(params.get("page_size", DEFAULT_PAGE_SIZE))
    if page < 1 or page_size < 1 or page_size > 100:
        raise SearchError("contract_invalid")
    sort = params.get("sort", "identity")
    if sort not in SORT_WHITELIST:
        raise SearchError("contract_invalid")

    where = ["1=1"]
    if query := params.get("q"):
        term = _escape_like(str(query))
        where.append(f"(b.business ->> 'title') ILIKE {_literal('%' + term + '%')}")
    if category := params.get("category"):
        where.append(f"(b.business ->> 'category') = {_literal(str(category))}")
    if source := params.get("source"):
        where.append(f"s.source_code = {_literal(str(source))}")
    if instructor := params.get("instructor"):
        where.append(
            f"(b.business ->> 'instructor') ILIKE "
            f"{_literal('%' + _escape_like(str(instructor)) + '%')}"
        )
    if params.get("has_instructor") is True:
        where.append("(b.business ->> 'instructor') IS NOT NULL")
    if params.get("date_from"):
        where.append(f"o.order_key >= {_literal(str(params['date_from']))}")
    if params.get("date_to"):
        import datetime

        next_day = (
            __import__("datetime").date.fromisoformat(str(params["date_to"]))
            + datetime.timedelta(days=1)
        ).isoformat()
        where.append(f"o.order_key < {_literal(next_day)}")
    if params.get("price_min") is not None:
        where.append(
            "NULLIF(b.business ->> 'price', '') ~ '^[0-9]+(\\.[0-9]+)?$' "
            f"AND (b.business ->> 'price')::numeric >= {params['price_min']}"
        )
    if params.get("price_max") is not None:
        where.append(
            "NULLIF(b.business ->> 'price', '') ~ '^[0-9]+(\\.[0-9]+)?$' "
            f"AND (b.business ->> 'price')::numeric <= {params['price_max']}"
        )
    where_clause = " AND ".join(where)

    base = (
        f"FROM source_records r "
        f"JOIN observations o ON o.source_record_id = r.source_record_id "
        f"JOIN content_payloads p ON p.payload_id = o.payload_id "
        f"JOIN content_payload_bodies b ON b.payload_id = o.payload_id "
        f"JOIN sources s ON s.source_id = r.source_id "
        f"WHERE {where_clause}"
    )
    total = int(
        pg_candidate.psql(
            database, f"SELECT count(DISTINCT r.identity_key) {base};"
        ).stdout.strip()
    )
    offset = (page - 1) * page_size
    # One deterministic card per identity: payload variants of the same
    # record collapse to the lexicographically smallest field tuple, so
    # pages partition identities exactly (no duplicates or gaps).
    dedup = (
        f"SELECT DISTINCT ON (r.identity_key) r.identity_key, "
        f"COALESCE(b.business ->> 'title', '') AS title, "
        f"COALESCE(b.business ->> 'category', '') AS category, "
        f"COALESCE(b.business ->> 'instructor', '') AS instructor, "
        f"s.source_code "
        f"{base} "
        f"ORDER BY r.identity_key, 2, 3, 4, 5"
    )
    order_clause = "ORDER BY 2, 1" if sort == "title" else "ORDER BY 1"
    rows = pg_candidate.psql(
        database,
        f"SELECT identity_key, title, category, instructor, source_code "
        f"FROM ({dedup}) cards {order_clause} "
        f"LIMIT {page_size} OFFSET {offset};",
    ).stdout
    cards = []
    for line in rows.splitlines():
        if "|" not in line:
            continue
        identity, title, category, instructor, source_code = line.split("|", 4)
        cards.append(
            {
                "identity_key": identity,
                "title": title,
                "category": category,
                "instructor": instructor,
                "source_code": source_code,
            }
        )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "cards": cards,
        "alias_expansion": "none (taxonomy_aliases empty in candidate corpus)",
    }
