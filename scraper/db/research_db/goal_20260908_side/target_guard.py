"""T01-R3 candidate target identity guard. Read-only precheck; never writes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypedDict, cast


class TargetGuardError(ValueError):
    """The requested target failed the declared candidate identity policy."""


class TargetReport(TypedDict):
    resolved: str
    empty: bool
    owned: bool
    files: int
    bytes: int


def load_policy(policy_path: Path) -> dict[str, object]:
    """Load and structurally validate the committed target policy."""
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError, OSError) as exc:
        raise TargetGuardError("policy_unreadable") from exc
    if not isinstance(policy, dict):
        raise TargetGuardError("policy_invalid")
    for key in ("workspace_root", "side_root", "protected_roots", "ownership_marker"):
        if key not in policy:
            raise TargetGuardError("policy_invalid")
    if not isinstance(policy["protected_roots"], list) or not policy["protected_roots"]:
        raise TargetGuardError("policy_invalid")
    if (
        not isinstance(policy["ownership_marker"], str)
        or not policy["ownership_marker"]
    ):
        raise TargetGuardError("policy_invalid")
    return policy


def _relative_argument(target: str) -> Path:
    rel = Path(target)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise TargetGuardError("target_out_of_scope")
    return rel


def check_target(policy_path: Path, target_argument: str) -> TargetReport:
    """Verify target identity, disjointness and emptiness without writing."""
    policy = load_policy(policy_path)
    workspace = Path(str(policy["workspace_root"]))
    side_root = workspace / str(policy["side_root"])
    try:
        side_resolved = side_root.resolve(strict=True)
    except OSError as exc:
        raise TargetGuardError("side_root_missing") from exc
    if not side_resolved.is_dir():
        raise TargetGuardError("side_root_missing")

    rel = _relative_argument(target_argument)
    target = side_resolved / rel
    current = side_resolved
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise TargetGuardError("target_symlink_rejected")
    if not target.exists():
        raise TargetGuardError("target_missing")
    resolved = target.resolve(strict=True)
    if resolved == side_resolved or side_resolved not in resolved.parents:
        raise TargetGuardError("target_outside_side_root")
    if not resolved.is_dir():
        raise TargetGuardError("target_not_directory")

    protected_roots = cast(list[object], policy["protected_roots"])
    for protected in protected_roots:
        protected_path = workspace / str(protected)
        try:
            protected_resolved = protected_path.resolve(strict=True)
        except OSError as exc:
            raise TargetGuardError("protected_root_missing") from exc
        if (
            resolved == protected_resolved
            or protected_resolved in resolved.parents
            or resolved in protected_resolved.parents
        ):
            raise TargetGuardError("target_overlaps_protected")

    marker_name = str(policy["ownership_marker"])
    files = 0
    total_bytes = 0
    entries = 0
    for entry in resolved.rglob("*"):
        entries += 1
        if entry.is_file() and not entry.is_symlink():
            files += 1
            total_bytes += entry.stat().st_size
    empty = entries == 0
    owned = False
    if not empty:
        marker = resolved / marker_name
        if not marker.is_file():
            raise TargetGuardError("target_not_empty_unowned")
        try:
            claim = json.loads(marker.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError, OSError) as exc:
            raise TargetGuardError("target_ownership_invalid") from exc
        if not isinstance(claim, dict) or not all(
            isinstance(claim.get(key), str) and claim.get(key)
            for key in ("task", "owner", "created_at")
        ):
            raise TargetGuardError("target_ownership_invalid")
        owned = True
    return {
        "resolved": str(resolved),
        "empty": empty,
        "owned": owned,
        "files": files,
        "bytes": total_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args()
    try:
        report = check_target(args.policy, args.target)
    except (TargetGuardError, OSError) as exc:
        code = str(exc) if isinstance(exc, TargetGuardError) else "target_io_error"
        print(json.dumps({"status": "rejected", "error": code}))
        return 1
    print(json.dumps({"status": "target_ok", **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
