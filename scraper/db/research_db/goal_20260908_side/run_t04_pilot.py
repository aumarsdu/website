"""T04 pilot: adapt pilot rows from registered real inputs, validate and seal
through the T08 staging path into candidate_data/pilot/<entry>/.

Pilot limits (原 Spec): jisi entries ≤25 rows each, zhongke/hirep ≤50 rows;
no assets. Only candidate_data/ is written; sources stay read-only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from adapters import adapt_rows
from contract import canonical_json
from stage_validator import validate_and_seal

SIDE = Path(__file__).resolve().parent
WORKSPACE = SIDE.parent.parent.parent
PILOT_FILES = {
    "jisi_future_sou_tools": (
        WORKSPACE
        / "集思未来/output/full_refresh/20260602-full-refresh/sou_tools/processed/records.jsonl",
        25,
    ),
    "jisi_future_domestic": (
        WORKSPACE
        / "集思未来/output/full_refresh/20260602-full-refresh/domestic/processed/records.jsonl",
        25,
    ),
    "zhongke": (WORKSPACE / "中科/output/processed/projects.jsonl", 50),
    "hirep": (
        WORKSPACE / "HIREP/output_pbl_full_refresh_20260602/processed/projects.jsonl",
        50,
    ),
}
PILOT = SIDE / "candidate_data" / "pilot"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_staging(entry: str, source: Path, limit: int) -> Path:
    rows = []
    with open(source, encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if index > limit:
                break
            if line.strip():
                rows.append(json.loads(line))
    result = adapt_rows(entry, rows)
    staging = PILOT / entry / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with open(staging / "records.jsonl", "w", encoding="utf-8") as out:
        out.writelines(
            canonical_json(adapted["staging_row"]) + "\n"
            for adapted in result["mapped"]
        )
    data = (staging / "records.jsonl").read_bytes()
    manifest = {
        "contract_version": "1",
        "batch_id": f"pilot-{entry}-20260925",
        "source_code": entry,
        "capture_mode": "full",
        "captured_at": max(
            (m["order_key"] for m in result["mapped"] if m["order_key"]),
            default="unknown",
        ),
        "observed_order": "unknown",
        "coverage": "partial",
        "adapter_version": "t04-v1",
        "mapping_version": "t04-v1",
        "hash_version": "h1",
        "scope": {"entry": entry, "pilot_rows": limit},
        "input_files": [
            {
                "relative_path": "records.jsonl",
                "sha256": sha(data),
                "byte_size": len(data),
                "row_count": len(result["mapped"]),
                "format": "jsonl",
                "role": "fact",
            }
        ],
    }
    (staging / "manifest.json").write_text(
        canonical_json(manifest) + "\n", encoding="utf-8"
    )
    return staging


def main() -> int:
    if PILOT.exists():
        shutil.rmtree(PILOT)
    report = {
        "checked_at": "2026-09-25",
        "limits": {k: v[1] for k, v in PILOT_FILES.items()},
        "entries": {},
    }
    for entry, (source, limit) in PILOT_FILES.items():
        staging = build_staging(entry, source, limit)
        target = PILOT / entry / "sealed"
        verdict = validate_and_seal(staging, target)
        report["entries"][entry] = {
            "rows_in": limit,
            "staging_rows": len(
                (staging / "records.jsonl").read_text(encoding="utf-8").splitlines()
            ),
            "verdict": verdict,
        }
        if verdict["sealed"]:
            report["entries"][entry]["seal"] = json.loads(
                (target / "seal.json").read_text(encoding="utf-8")
            )["batch_sha256"][:16]
    out = SIDE / "evidence" / "t04_pilot.json"
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v["verdict"].get("counts") for k, v in report["entries"].items()},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
