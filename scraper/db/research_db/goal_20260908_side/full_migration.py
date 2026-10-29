"""Full-candidate migration (Owner-approved 2026-09-27).

Pipeline per approved application draft (evidence/full_migration_application_draft.md):
  registered inputs -> T04-style adaptation (str coercion) -> T08 seal (<=500/batch)
  -> T09 import (idempotent, committed receipts) -> set-based current-pointer update
  -> reconciliation + projection consistency + double-replay digest comparison.

Authorization: Owner confirmed the application draft ("确认，继续执行").
Real-target switch and publication remain out of scope (separate authorization).
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pg_candidate
from stage_validator import validate_and_seal

SIDE = Path(__file__).resolve().parent
WORKSPACE = SIDE.parent.parent.parent
REGISTRY = json.loads((SIDE / "source_registry.json").read_text(encoding="utf-8"))
CHUNK = 500


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def source_inputs(source_code: str) -> list[dict]:
    src = next(s for s in REGISTRY["sources"] if s["source_code"] == source_code)
    return src["inputs"]


FIELDS = {
    "jisi_future_sou_tools": {
        "title": "name",
        "instructor": "raw.dTeacherNickName",
        "institution": "raw.dTeacherSchool",
        "start_date": "raw.schoolBegins",
        "duration": "raw.cycle",
    },
    "jisi_future_domestic": {
        "title": "name",
        "instructor": "raw.dTeacherNickName",
        "institution": "raw.dTeacherSchool",
        "start_date": "raw.schoolBegins",
        "duration": "raw.cycle",
    },
    "zhongke": {
        "title": "title",
        "category": "category",
        "instructor": "teacher",
        "institution": "university",
    },
    "hirep": {
        "title": "title",
        "category": "category",
        "instructor": "professor",
        "institution": "university",
    },
}


def resolve(record: dict, dotted: str):
    cur = record
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def iter_structured(source: str):
    for entry in source_inputs(source):
        path = WORKSPACE / entry["relative_path"]
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield entry["relative_path"], json.loads(line)


def iter_yanqu():
    import csv

    csv_path = WORKSPACE / "盐趣/盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv"
    collection = WORKSPACE / "盐趣/盐趣7-9月项目合集"
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            poster_rel = row["poster_path"]
            image = collection / poster_rel
            if image.is_file():
                poster_id = "poster-" + sha_file(image)[:32]
            else:
                poster_id = "poster-" + sha_bytes(poster_rel.encode())[:32]
            category = row.get("\ufeffcategory") or row.get("category", "")
            yield {
                "id": poster_id,
                "category": category,
                "poster_text": (row.get("poster_text") or "")[:4000],
                "text_block_count": row.get("text_block_count", ""),
            }


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_yinzhi():
    from yinzhi_segment import segment_file

    result = segment_file(WORKSPACE / "引知/data/archive/public/content.md")
    lines = (
        (WORKSPACE / "引知/data/archive/public/content.md")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    for entry in result["entries"]:
        body = lines[entry["content_lines"][0] - 1] if entry["content_lines"] else ""
        yield {
            "id": f"entry-{entry['anchor_line']}",
            "title": entry["title"],
            "body_text": body.strip()[:500],
        }


def write_and_seal(
    name: str,
    batch_id: str,
    source: str,
    rows: list[dict],
    coverage: str,
    work: Path,
    candidate_identities: bool,
):
    staging = work / name / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    with open(staging / "records.jsonl", "w", encoding="utf-8") as out:
        out.writelines(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        )
    data = (staging / "records.jsonl").read_bytes()
    manifest = {
        "contract_version": "1",
        "batch_id": batch_id,
        "source_code": source,
        "capture_mode": "full" if mode_of(source) == "structured" else mode_of(source),
        "captured_at": "unknown",
        "observed_order": "unknown",
        "coverage": coverage,
        "adapter_version": "full-v1",
        "mapping_version": "full-v1",
        "hash_version": "h1",
        "scope": {"entry": source, "candidate_identities": candidate_identities},
        "input_files": [
            {
                "relative_path": "records.jsonl",
                "sha256": sha_bytes(data),
                "byte_size": len(data),
                "row_count": len(rows),
                "format": "jsonl",
                "role": "fact",
            }
        ],
    }
    (staging / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sealed = work / name / "sealed"
    if sealed.exists():
        import shutil

        shutil.rmtree(sealed)
    verdict = validate_and_seal(staging, sealed)
    return staging, sealed, verdict


def mode_of(source: str) -> str:
    return {"yanqu_ocr": "ocr", "yinzhi_public": "archive"}.get(source, "full")


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def collect_all():
    """Return {source: {"rows": [...], "coerced": int, "rejected": int}}."""
    out = {}
    structured = ("jisi_future_sou_tools", "jisi_future_domestic", "zhongke", "hirep")
    for source in structured:
        rows, coerced, rejected = [], 0, 0
        for _path, row in iter_structured(source):
            native = row.get("id") or row.get("business_id")
            if not native:
                rejected += 1
                continue
            staged = {"id": str(native)}
            for target, dotted in FIELDS[source].items():
                v = resolve(row, dotted)
                if v is None:
                    continue
                if isinstance(v, str):
                    if v.strip():
                        staged[target] = v
                else:
                    staged[target] = str(v)
                    coerced += 1
            if row.get("crawled_at"):
                staged["crawled_at"] = row["crawled_at"]
            rows.append(staged)
        out[source] = {"rows": rows, "coerced": coerced, "rejected": rejected}
    ya = list(iter_yanqu())
    out["yanqu_ocr"] = {"rows": ya, "coerced": 0, "rejected": 0}
    yz = list(iter_yinzhi())
    out["yinzhi_public"] = {"rows": yz, "coerced": 0, "rejected": 0}
    return out


def main() -> int:
    started = time.time()
    pg_candidate.init_cluster()
    corpus = collect_all()
    totals = {s: len(d["rows"]) for s, d in corpus.items()}
    print("collected:", json.dumps(totals, ensure_ascii=False))

    results = {}
    for replay in (1, 2):
        db = f"candidate_full_{replay}"
        pg_candidate.drop_database(db)
        pg_candidate.create_database(db)
        import run_migrations

        assert (
            run_migrations.run(db, SIDE / "migrations", __import__("sys").stdout)
            == run_migrations.EXIT_OK
        )
        work = SIDE / "candidate_data" / f"full_migration_{replay}"
        if work.exists():
            import shutil

            shutil.rmtree(work)
        receipts = []
        for source, data in corpus.items():
            limit = {"yanqu_ocr": 500, "yinzhi_public": 500}.get(source, 500)
            for idx, chunk_rows in enumerate(chunks(data["rows"], limit), 1):
                name = f"{source}-{idx:03d}"
                batch_id = f"full-{source}-{idx:03d}"
                cand = source in ("yanqu_ocr", "yinzhi_public")
                staging, sealed, verdict = write_and_seal(
                    name, batch_id, source, chunk_rows, "complete", work, cand
                )
                if not verdict["sealed"]:
                    raise SystemExit(f"{batch_id} seal failed: {verdict}")
                import importer

                receipt = importer.import_sealed(staging, sealed, db, max_rows=500)
                if receipt["status"] != "committed":
                    raise SystemExit(f"{batch_id} import failed: {receipt}")
                receipts.append(
                    {
                        "batch": batch_id,
                        "rows": len(chunk_rows),
                        "inserted": receipt["counts"]["inserted_observations"],
                        "unchanged": receipt["counts"]["unchanged_observations"],
                    }
                )
        total_rows = sum(r["rows"] for r in receipts)
        total_obs = sum(r["inserted"] for r in receipts)
        digest_input = pg_candidate.psql(
            db,
            "SELECT r.identity_key, p.payload_hash, o.order_key, o.context_key "
            "FROM observations o "
            "JOIN content_payloads p ON p.payload_id = o.payload_id "
            "JOIN source_records r ON r.source_record_id = o.source_record_id "
            "ORDER BY 1,2,3,4;",
        ).stdout.splitlines()
        current_map = pg_candidate.psql(
            db,
            "SELECT r.identity_key, c.status FROM source_record_current c "
            "JOIN source_records r ON r.source_record_id = c.source_record_id "
            "ORDER BY 1;",
        ).stdout.splitlines()
        digest = hashlib.sha256(
            (
                "\n".join(sorted(digest_input)) + "\n" + "\n".join(sorted(current_map))
            ).encode("utf-8")
        ).hexdigest()
        import projection

        consistency = projection.rebuild_consistency(db)
        results[db] = {
            "digest": digest,
            "total_rows": total_rows,
            "total_observations": total_obs,
            "counts": {
                t: int(
                    pg_candidate.psql(db, f"SELECT count(*) FROM {t};").stdout.strip()
                )
                for t in ("source_records", "observations", "conflicts")
            },
            "consistency": consistency,
            "receipts": receipts,
        }
        print(
            db,
            "digest:",
            digest[:16],
            "rows:",
            total_rows,
            "consistent:",
            consistency["consistent"],
        )

    identical = (
        results["candidate_full_1"]["digest"] == results["candidate_full_2"]["digest"]
        and results["candidate_full_1"]["counts"]
        == results["candidate_full_2"]["counts"]
    )
    elapsed = round(time.time() - started, 1)
    report = {
        "executed_at": "2026-09-27",
        "authorization": "Owner 确认申请草案（'确认，继续执行'）；执行按草案范围与上限",
        "totals_collected": totals,
        "coercions_to_str": {s: d["coerced"] for s, d in corpus.items()},
        "rejected_missing_id": {s: d["rejected"] for s, d in corpus.items()},
        "replay_1": {
            k: v for k, v in results["candidate_full_1"].items() if k != "receipts"
        },
        "replay_2": {
            k: v for k, v in results["candidate_full_2"].items() if k != "receipts"
        },
        "identical": identical,
        "elapsed_seconds": elapsed,
        "batch_receipts_replay_1": results["candidate_full_1"]["receipts"],
    }
    (SIDE / "evidence" / "full_migration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps({"identical": identical, "elapsed_s": elapsed}, ensure_ascii=False)
    )
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
