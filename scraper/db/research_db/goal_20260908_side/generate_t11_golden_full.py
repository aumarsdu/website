"""Generate and freeze the full-corpus T11 search golden: 20 annotated queries.

Same independence pattern as generate_t11_queries.py: annotations are computed
by straightforward per-query SQL scans over candidate_full_1, independent of
the search implementation. Query definitions are imported unchanged from the
pilot generator; only the annotation corpus and expected values differ.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pg_candidate

SIDE = Path(__file__).resolve().parent
DB = "candidate_full_1"

# Mirrors generate_t11_queries.QUERIES verbatim; duplicated on purpose because
# importing that module would re-run its module-level pilot golden generation.
QUERIES = [
    {"id": "q01_ai", "params": {"q": "人工智能"}},
    {"id": "q02_ml", "params": {"q": "机器学习"}},
    {"id": "q03_market", "params": {"q": "市场"}},
    {"id": "q04_quantum", "params": {"q": "量子"}},
    {"id": "q05_ai_english", "params": {"q": "AI"}},
    {"id": "q06_business_cat", "params": {"category": "商科"}},
    {"id": "q07_business_cat_exact", "params": {"category": "计算机"}},
    {"id": "q08_source_hirep", "params": {"source": "hirep"}},
    {"id": "q09_source_domestic", "params": {"source": "jisi_future_domestic"}},
    {"id": "q10_instructor_prof", "params": {"instructor": "Prof"}},
    {"id": "q11_has_instructor", "params": {"has_instructor": True}},
    {
        "id": "q12_date_window",
        "params": {"date_from": "2026-06-02", "date_to": "2026-06-02"},
    },
    {"id": "q13_price_floor", "params": {"price_min": 100}},
    {"id": "q14_ai_and_cat", "params": {"q": "人工智能", "category": "计算机科研"}},
    {"id": "q15_nonexistent_word", "params": {"q": "不存在的词xyz"}},
    {"id": "q16_nonexistent_category", "params": {"category": "不存在的分类"}},
    {"id": "q17_percent_literal", "params": {"q": "100%"}},
    {"id": "q18_ai_page2", "params": {"q": "人工智能", "page": 2, "page_size": 3}},
    {"id": "q19_sorted_market", "params": {"q": "市场", "sort": "title"}},
    {"id": "q20_all", "params": {}},
]


def scan(params: dict) -> list[str]:
    where = ["1=1"]
    if params.get("q"):
        term = params["q"].replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        where.append(f"(b.business ->> 'title') ILIKE '%{term}%'")
    if params.get("category"):
        where.append(f"(b.business ->> 'category') = '{params['category']}'")
    if params.get("source"):
        where.append(f"s.source_code = '{params['source']}'")
    if params.get("instructor"):
        where.append(f"(b.business ->> 'instructor') ILIKE '%{params['instructor']}%'")
    if params.get("has_instructor") is True:
        where.append("(b.business ->> 'instructor') IS NOT NULL")
    if params.get("date_from"):
        where.append(f"o.order_key >= '{params['date_from']}'")
    if params.get("date_to"):
        import datetime as _dt

        next_day = (
            _dt.date.fromisoformat(params["date_to"]) + _dt.timedelta(days=1)
        ).isoformat()
        where.append(f"o.order_key < '{next_day}'")
    if params.get("price_min") is not None:
        where.append(
            f"NULLIF(b.business ->> 'price', '') ~ '^[0-9]+(\\.[0-9]+)?$' "
            f"AND (b.business ->> 'price')::numeric >= {params['price_min']}"
        )
    sql = (
        "SELECT DISTINCT r.identity_key FROM source_records r "
        "JOIN observations o ON o.source_record_id = r.source_record_id "
        "JOIN content_payloads p ON p.payload_id = o.payload_id "
        "JOIN content_payload_bodies b ON b.payload_id = o.payload_id "
        "JOIN sources s ON s.source_id = r.source_id "
        "WHERE " + " AND ".join(where) + " ORDER BY r.identity_key;"
    )
    result = pg_candidate.psql(DB, sql).stdout.splitlines()
    return [line for line in result if line.strip()]


def main() -> None:
    pg_candidate.init_cluster()
    if not pg_candidate.database_exists(DB):
        raise SystemExit(f"full corpus database {DB} missing; run full_migration.py")

    records = int(
        pg_candidate.psql(DB, "SELECT count(*) FROM source_records;").stdout.strip()
    )
    observations = int(
        pg_candidate.psql(DB, "SELECT count(*) FROM observations;").stdout.strip()
    )
    sources = [
        line
        for line in pg_candidate.psql(
            DB, "SELECT source_code FROM sources ORDER BY source_code;"
        ).stdout.splitlines()
        if line.strip()
    ]

    golden = {
        "frozen_at": "2026-09-28",
        "corpus": {
            "database": DB,
            "records": records,
            "observations": observations,
            "sources": sources,
            "origin": "full migration double replay digest e05ebc98123cee35636d805c19e2318986a367be1ad83ca80d9b0c382205d44e",
        },
        "semantics": {
            "note": "same filter/sort/pagination semantics as the pilot golden; expected values re-annotated by direct SQL on the full corpus",
        },
        "queries": [],
    }
    for query in QUERIES:
        expected = scan(query["params"])
        golden["queries"].append(
            {**query, "expected_identities": expected, "expected_total": len(expected)}
        )

    out = SIDE / "fixtures" / "t11_golden_full.json"
    out.write_text(
        json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for query in golden["queries"]:
        print(query["id"], "total:", query["expected_total"])
    print("sha256:", hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
