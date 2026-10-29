"""T08 strong staging validator with atomic temp-dir sealing.

Verdicts are frozen in fixtures/t08_expected.json (generated before this
implementation). Output contains approved fields only; raw rows and large SQL
are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from contract import (
    ContractError,
    canonical_json,
    field_state,
    identity_key,
    manifest_digest,
    observation_key,
    payload_hash,
    validate_manifest,
)

VALIDATOR_VERSION = "t08-v1"
SIDEC = Path(__file__).resolve().parent
CONFIG = json.loads((SIDEC / "contract_config.json").read_text(encoding="utf-8"))


class StageError(ValueError):
    """The staging batch failed validation and cannot be sealed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(staging: Path) -> dict[str, Any]:
    manifest_path = staging / "manifest.json"
    if not manifest_path.is_file():
        raise StageError("empty_input")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise StageError("contract_invalid") from exc
    try:
        validate_manifest(manifest)
    except ContractError as exc:
        raise StageError("contract_invalid") from exc
    if not manifest["input_files"]:
        raise StageError("empty_input")
    return manifest


def _input_path(staging: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise StageError("contract_invalid")
    path = staging / rel
    current = staging.resolve()
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise StageError("contract_invalid")
    return path


def _check_inputs(staging: Path, manifest: dict[str, Any]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for entry in manifest["input_files"]:
        rel = entry["relative_path"]
        path = _input_path(staging, rel)
        if not path.is_file():
            raise StageError("input_missing")
        actual = _sha256_file(path)
        if actual != entry["sha256"] or path.stat().st_size != entry["byte_size"]:
            raise StageError("input_changed")
        digests[rel] = actual
        rows = 0
        parse_error = False
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                rows += 1
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    parse_error = True
        if rows != entry["row_count"]:
            raise StageError("row_count_mismatch")
        if parse_error:
            raise StageError("row_truncated")
    return digests


def _classify(staging: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    source = manifest["source_code"]
    config = CONFIG["sources"].get(source)
    if config is None:
        raise StageError("contract_invalid")
    whitelist = list(config["whitelist"])
    batch_id = manifest["batch_id"]
    counts = {"accepted": 0, "duplicate": 0, "quarantined": 0, "rejected": 0}
    rows_read = 0
    seen: set[str] = set()
    accepted_ids: set[str] = set()
    payload_by_id: dict[str, set[str]] = {}
    sealed_rows: list[dict[str, Any]] = []

    records_rel = manifest["input_files"][0]["relative_path"]
    with open(staging / records_rel, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows_read += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                counts["rejected"] += 1
                continue
            native_id = row.get("id")
            if not isinstance(native_id, str) or not native_id:
                counts["rejected"] += 1
                continue
            bad_type = any(
                key in row and row[key] is not None and not isinstance(row[key], str)
                for key in whitelist
            )
            if bad_type:
                counts["quarantined"] += 1
                continue
            ident = identity_key(source, native_id)
            payload = payload_hash(row, whitelist, manifest["hash_version"])
            context_key = str(row.get("context_key") or "default")
            okey = observation_key(batch_id, ident, context_key, payload)
            if okey in seen:
                counts["duplicate"] += 1
                continue
            seen.add(okey)
            counts["accepted"] += 1
            accepted_ids.add(native_id)
            payload_by_id.setdefault(native_id, set()).add(payload)
            sealed_rows.append(
                {
                    "batch_id": batch_id,
                    "context_key": context_key,
                    "field_states": {key: field_state(row, key) for key in whitelist},
                    "identity_key": ident,
                    "observation_key": okey,
                    "order_key": row.get("crawled_at"),
                    "payload_hash": payload,
                    "business": {k: row[k] for k in whitelist if k in row},
                }
            )

    if (
        counts["accepted"]
        + counts["duplicate"]
        + counts["quarantined"]
        + counts["rejected"]
        != rows_read
    ):
        raise StageError("row_count_mismatch")

    observation_errors: list[str] = []
    for entry in manifest["input_files"]:
        if entry.get("role") != "observation":
            continue
        with open(staging / entry["relative_path"], encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                ref = json.loads(line)
                if ref.get("record") not in accepted_ids:
                    observation_errors.append("observation_record_unknown")
                elif ref.get("payload_ref") not in payload_by_id.get(
                    ref.get("record", ""), set()
                ):
                    observation_errors.append("observation_payload_unknown")
    if observation_errors:
        raise StageError("|".join(dict.fromkeys(observation_errors)))

    return {"counts": counts, "rows_read": rows_read, "sealed_rows": sealed_rows}


def _seal(
    staging: Path,
    target: Path,
    manifest: dict[str, Any],
    result: dict[str, Any],
    input_digests: dict[str, str],
) -> None:
    if target.exists():
        raise StageError("seal_target_exists")
    seal = {
        "batch_id": manifest["batch_id"],
        "contract_version": manifest["contract_version"],
        "counts": result["counts"],
        "hash_version": manifest["hash_version"],
        "input_files": input_digests,
        "manifest_digest": manifest_digest(manifest),
        "rows_read": result["rows_read"],
        "source_code": manifest["source_code"],
        "validator_version": VALIDATOR_VERSION,
    }
    temp = target.parent / f".tmp-seal-{target.name}"
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True)
    try:
        rows_path = temp / "batch.jsonl"
        with open(rows_path, "w", encoding="utf-8") as handle:
            handle.writelines(
                canonical_json(row) + "\n" for row in result["sealed_rows"]
            )
        seal["batch_sha256"] = _sha256_file(rows_path)
        (temp / "seal.json").write_text(canonical_json(seal) + "\n", encoding="utf-8")
        for path in temp.iterdir():
            with open(path, "rb") as handle:
                os.fsync(handle.fileno())
        os.replace(temp, target)
    except OSError:
        if temp.exists():
            shutil.rmtree(temp)
        raise


def validate_and_seal(staging: Path, target: Path) -> dict[str, Any]:
    """Validate one staging batch and atomically seal an importable output."""
    try:
        manifest = _load_manifest(staging)
        input_digests = _check_inputs(staging, manifest)
        result = _classify(staging, manifest)
    except StageError as exc:
        return {"sealed": False, "error": str(exc)}
    try:
        _seal(staging, target, manifest, result, input_digests)
    except StageError as exc:
        return {"sealed": False, "error": str(exc), "counts": result["counts"]}
    return {
        "sealed": True,
        "counts": result["counts"],
        "rows_read": result["rows_read"],
        "sealed_rows": len(result["sealed_rows"]),
    }


def validate_only(staging: Path) -> dict[str, Any]:
    """Read-only validation verdict: no target directory is ever created."""
    try:
        manifest = _load_manifest(staging)
        _check_inputs(staging, manifest)
        result = _classify(staging, manifest)
    except StageError as exc:
        return {"sealed": False, "error": str(exc)}
    return {
        "sealed": False,
        "would_seal": True,
        "counts": result["counts"],
        "rows_read": result["rows_read"],
        "sealed_rows": len(result["sealed_rows"]),
    }


def verify_seal(staging: Path, target: Path) -> None:
    """Re-check a sealed batch against its staging inputs; mutation voids it."""
    seal = json.loads((target / "seal.json").read_text(encoding="utf-8"))
    manifest = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
    if seal["manifest_digest"] != manifest_digest(manifest):
        raise StageError("input_changed")
    for entry in manifest["input_files"]:
        if (
            _sha256_file(staging / entry["relative_path"])
            != seal["input_files"][entry["relative_path"]]
        ):
            raise StageError("input_changed")
    batch = target / "batch.jsonl"
    if _sha256_file(batch) != seal["batch_sha256"]:
        raise StageError("input_changed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="read-only verdict; nothing is sealed",
    )
    mode.add_argument(
        "--seal",
        action="store_true",
        help="validate and atomically seal the batch into --target",
    )
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    if args.target is None and args.seal:
        parser.error("--seal requires --target")
    if args.dry_run:
        verdict = validate_only(args.staging)
        print(json.dumps({**verdict, "mode": "dry-run"}, ensure_ascii=False))
        return 0 if verdict.get("would_seal") else 1
    assert args.target is not None
    verdict = validate_and_seal(args.staging, args.target)
    print(json.dumps({**verdict, "mode": "seal"}, ensure_ascii=False))
    return 0 if verdict["sealed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
