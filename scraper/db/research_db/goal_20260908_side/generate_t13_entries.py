"""T13 gap closure: build yanqu_ocr and yinzhi_public sealed batches from the
T06/T07 candidate outputs so the double replay covers all six frozen entries.

Identity handling (per T02 boundaries): neither source has a reliable native
id, so candidate identities are content/anchor derived and explicitly marked
candidate_until_confirmed by the importing source config:
  - yanqu: poster text-hash (content derived, not path derived)
  - yinzhi: front-matter code + anchor line (positional within a frozen file)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract import canonical_json
from stage_validator import validate_and_seal

SIDE = Path(__file__).resolve().parent
WORKSPACE = SIDE.parent.parent.parent
PILOT = SIDE / "candidate_data" / "pilot"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_yanqu() -> None:
    sys.path.insert(0, str(SIDE))
    from ocr_extract import extract_fields, load_csv_rows

    manifest = json.loads((SIDE / "pilot_manifest.json").read_text(encoding="utf-8"))
    csv_rows = load_csv_rows(
        WORKSPACE / "盐趣/盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv"
    )
    rows = []
    for candidate in manifest["yanqu_original_image_candidates"]:
        result = extract_fields(
            candidate["resolved_collection_path"],
            json.loads(csv_rows[candidate["csv_row"]]["text_blocks_json"]),
        )
        poster_hash = hashlib.sha256(
            (WORKSPACE / candidate["resolved_collection_path"]).read_bytes()
        ).hexdigest()
        fields = result["fields"]
        rows.append(
            {
                "id": f"poster-{poster_hash[:32]}",
                "category": candidate["csv_poster_path"].split("/")[0],
                "poster_text": " ".join(
                    ev["text"] for field in fields.values() for ev in field["evidence"]
                )[:2000],
                "row": candidate["csv_row"],
            }
        )
    staging = PILOT / "yanqu_ocr" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    with open(staging / "records.jsonl", "w", encoding="utf-8") as out:
        for row in rows:
            payload = {k: row[k] for k in ("id", "category", "poster_text")}
            out.write(canonical_json(payload) + "\n")
    finish(
        staging,
        PILOT / "yanqu_ocr" / "sealed",
        "pilot-yanqu-ocr",
        len(rows),
        "ocr",
    )


def build_yinzhi() -> None:
    sys.path.insert(0, str(SIDE))
    from yinzhi_segment import segment_file

    result = segment_file(WORKSPACE / "引知/data/archive/public/content.md")
    lines = (
        (WORKSPACE / "引知/data/archive/public/content.md")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    rows = []
    for entry in result["entries"]:
        body = lines[entry["content_lines"][0] - 1] if entry["content_lines"] else ""
        rows.append(
            {
                "id": f"entry-{entry['anchor_line']}",
                "title": entry["title"],
                "body_text": body.strip()[:500],
            }
        )
    staging = PILOT / "yinzhi_public" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    with open(staging / "records.jsonl", "w", encoding="utf-8") as out:
        for row in rows:
            payload = {k: row[k] for k in ("id", "title", "body_text")}
            out.write(canonical_json(payload) + "\n")
    finish(
        staging,
        PILOT / "yinzhi_public" / "sealed",
        "pilot-yinzhi",
        len(rows),
        "archive",
    )


def finish(
    staging: Path, sealed_dir: Path, batch_id: str, row_count: int, mode: str
) -> None:
    import shutil

    if sealed_dir.exists():
        shutil.rmtree(sealed_dir)
    sealed_dir.parent.mkdir(parents=True, exist_ok=True)
    data = (staging / "records.jsonl").read_bytes()
    manifest = {
        "contract_version": "1",
        "batch_id": batch_id,
        "source_code": batch_source(batch_id),
        "capture_mode": mode,
        "captured_at": "unknown",
        "observed_order": "unknown",
        "coverage": "complete",
        "adapter_version": "t13-v1",
        "mapping_version": "t13-v1",
        "hash_version": "h1",
        "scope": {"entry": batch_source(batch_id), "candidate_identities": True},
        "input_files": [
            {
                "relative_path": "records.jsonl",
                "sha256": sha_bytes(data),
                "byte_size": len(data),
                "row_count": row_count,
                "format": "jsonl",
                "role": "fact",
            }
        ],
    }
    (staging / "manifest.json").write_text(
        canonical_json(manifest) + "\n", encoding="utf-8"
    )
    verdict = validate_and_seal(staging, sealed_dir)
    print(batch_id, "sealed:", verdict["sealed"], verdict.get("counts"))


def batch_source(batch_id: str) -> str:
    return "yanqu_ocr" if "yanqu" in batch_id else "yinzhi_public"


if __name__ == "__main__":
    build_yanqu()
    build_yinzhi()
