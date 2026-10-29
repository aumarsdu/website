"""T01 metadata inventory. Explicit inputs only; never copy source contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import TypedDict


class InventoryError(ValueError):
    """A source failed the declared inventory boundary."""


class FileEntry(TypedDict):
    relative_path: str
    sha256: str
    byte_size: int


def safe_path(root: Path, relative: str) -> Path:
    """Resolve an explicit regular file within its approved root."""
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise InventoryError("path_out_of_scope")
    if any(part.startswith(".") for part in rel.parts):
        raise InventoryError("hidden_input_excluded")
    if rel.suffix.lower() not in {".jsonl", ".json", ".csv", ".md", ".sql", ".py"}:
        raise InventoryError("unsupported_input_format")
    resolved_root = root.resolve(strict=True)
    try:
        resolved = (resolved_root / rel).resolve(strict=True)
    except FileNotFoundError as exc:
        raise InventoryError("input_missing") from exc
    if not resolved.is_relative_to(resolved_root):
        raise InventoryError("path_out_of_scope")
    if not resolved.is_file():
        raise InventoryError("input_not_regular")
    return resolved


def fingerprint(root: Path, relative: str) -> FileEntry:
    """Hash without printing values; reject detectable concurrent mutations."""
    path = safe_path(root, relative)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise InventoryError("input_not_regular")
        digest = hashlib.sha256()
        size = 0
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(handle.fileno())
    current = safe_path(root, relative)
    current_stat = current.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if (
        current != path
        or any(getattr(before, x) != getattr(after, x) for x in fields)
        or any(getattr(after, x) != getattr(current_stat, x) for x in fields)
        or size != after.st_size
    ):
        raise InventoryError("input_changed")
    return {"relative_path": relative, "sha256": digest.hexdigest(), "byte_size": size}


def register(root: Path, requested: list[str], approved: list[str]) -> list[FileEntry]:
    """An explicit allowlist excludes delivery copies even inside the root."""
    if not requested:
        raise InventoryError("empty_input")
    if len(requested) != len(set(requested)):
        raise InventoryError("duplicate_input")
    if not set(requested).issubset(approved):
        raise InventoryError("input_not_registered")
    return [fingerprint(root, path) for path in requested]


def verify(root: Path, entries: list[FileEntry]) -> None:
    """Recheck every sealed source immediately before dependent work."""
    if not entries:
        raise InventoryError("empty_input")
    for entry in entries:
        if fingerprint(root, entry["relative_path"]) != entry:
            raise InventoryError("input_changed")


def approved_entries(registry_path: Path, root: Path) -> dict[str, FileEntry]:
    """Load the separate, explicit registry and bind it to its source root."""
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(registry, dict):
            raise InventoryError("registry_invalid")
        registered_root = registry.get("approved_root")
        sources = registry.get("sources")
        if not isinstance(registered_root, str) or not isinstance(sources, list):
            raise InventoryError("registry_invalid")
        if root.resolve(strict=True) != Path(registered_root).resolve(strict=True):
            raise InventoryError("root_not_registered")
        result: dict[str, FileEntry] = {}
        for source in sources:
            if not isinstance(source, dict) or not isinstance(
                source.get("inputs"), list
            ):
                raise InventoryError("registry_invalid")
            for entry in source["inputs"]:
                if not isinstance(entry, dict):
                    raise InventoryError("registry_invalid")
                relative = entry.get("relative_path")
                digest = entry.get("sha256")
                size = entry.get("byte_size")
                if (
                    not isinstance(relative, str)
                    or not isinstance(digest, str)
                    or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)
                    or type(size) is not int
                    or size < 0
                    or relative in result
                ):
                    raise InventoryError("registry_invalid")
                result[relative] = {
                    "relative_path": relative,
                    "sha256": digest,
                    "byte_size": size,
                }
        if not result:
            raise InventoryError("registry_empty")
        return result
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise InventoryError("registry_invalid") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args()
    inputs: list[str] = args.input
    try:
        approved = approved_entries(args.registry, args.root)
        entries = register(args.root, inputs, list(approved))
        if any(entry != approved[entry["relative_path"]] for entry in entries):
            raise InventoryError("input_changed")
    except (InventoryError, OSError) as exc:
        code = str(exc) if isinstance(exc, InventoryError) else "input_io_error"
        print(json.dumps({"status": "rejected", "error": code}))
        return 1
    print(json.dumps({"status": "inventoried", "files": entries}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
