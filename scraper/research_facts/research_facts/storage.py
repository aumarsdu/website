"""Deterministic persistence: JSONL, JSON, content digests.

Idempotency is a property of this module as much as of the pipeline. Two
guarantees:

1. Row order is decided by the pipeline, not by dict iteration or filesystem
   order, so repeated runs write byte-identical files.
2. ``content_digest`` hashes only the fact payload. Run timestamps live in the
   manifest, so a second run over the same inputs reports the same digest even
   though ``extracted_at`` moved.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from .errors import InputError, StorageError
from .utils import sha256_text


def read_jsonl(path: Path, on_error: Callable[[int, Exception], None] | None = None) -> Iterator[dict[str, Any]]:
    """Yield one object per non-empty line.

    With no ``on_error`` the read is strict and the first bad line raises. When
    ``on_error`` is supplied, a bad line is reported and skipped instead: one
    corrupt record must not discard a 600-line partner export.
    """
    path = Path(path)
    if not path.exists():
        raise InputError(f"input file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                error = InputError(f"{path}:{line_number} is not valid JSON: {exc}")
                if on_error is None:
                    raise error from exc
                on_error(line_number, error)
                continue
            if not isinstance(payload, dict):
                error = InputError(f"{path}:{line_number} must be a JSON object")
                if on_error is None:
                    raise error
                on_error(line_number, error)
                continue
            yield payload


def read_json(path: Path) -> Any:
    path = Path(path)
    if not path.exists():
        raise InputError(f"input file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path} is not valid JSON: {exc}") from exc


def atomic_write_text(path: Path, text: str) -> None:
    """Write via a temporary file so a crashed run never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:  # pragma: no cover - filesystem dependent
        raise StorageError(f"failed to write {path}: {exc}") from exc


def dumps_line(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def write_jsonl(path: Path, rows: Iterable[Any]) -> int:
    lines = [dumps_line(row) for row in rows]
    atomic_write_text(Path(path), "\n".join(lines) + ("\n" if lines else ""))
    return len(lines)


def write_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    atomic_write_text(Path(path), text + "\n")


def content_digest(rows: Iterable[Any]) -> str:
    """SHA-256 over the canonical JSON of every row, in order."""
    digest_input = "\n".join(dumps_line(row) for row in rows)
    return sha256_text(digest_input)


def read_records(path: Path) -> list[Any]:
    """Read fact records back from disk, reconstructing the model objects."""
    from .schema import ProjectFactRecord

    return [ProjectFactRecord.from_dict(row) for row in read_jsonl(Path(path))]
