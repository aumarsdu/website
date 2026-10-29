"""Adapter registry: map an input file to the adapter that can read it."""

from __future__ import annotations

from pathlib import Path

from ..errors import InputError
from .base import Adapter, AdapterOutput, SourceDocument
from .csv_table import CsvTableAdapter, TableProfile, detect_profile, table_profiles_from_file
from .textblock import handbook_adapter, poster_adapter
from .web_json import WebJsonAdapter, get_profile, load_profile_file, register_profile

# Table profiles registered from --profile-file, keyed by profile name.
TABLE_PROFILES: dict[str, TableProfile] = {}

__all__ = [
    "Adapter",
    "AdapterOutput",
    "CsvTableAdapter",
    "SourceDocument",
    "TABLE_PROFILES",
    "TableProfile",
    "WebJsonAdapter",
    "build_adapter",
    "describe_adapters",
    "get_profile",
    "handbook_adapter",
    "load_profile_file",
    "poster_adapter",
    "table_profiles_from_file",
    "register_profile",
]


def describe_adapters() -> list[dict[str, object]]:
    return [
        {"name": name, "source_kind": kind, "accepts": list(accepts)}
        for name, kind, accepts in (
            (poster_adapter.name, poster_adapter.source_kind, poster_adapter.accepts),
            (handbook_adapter.name, handbook_adapter.source_kind, handbook_adapter.accepts),
            (WebJsonAdapter.name, WebJsonAdapter.source_kind, WebJsonAdapter.accepts),
            (CsvTableAdapter.name, CsvTableAdapter.source_kind, CsvTableAdapter.accepts),
        )
    ]


def build_adapter(path: Path, *, source_kind: str | None = None, profile: str | None = None) -> Adapter:
    """Pick an adapter.

    ``source_kind`` is required, not inferred. Every input in this workspace is
    a ``.jsonl`` file, so guessing would silently read a handbook as a poster
    and produce a differently-shaped result set with no error. The pipeline
    passes it from the ``path:kind`` suffix or ``--source-kind``.
    """
    if source_kind == "poster_ocr":
        return poster_adapter
    if source_kind == "handbook_pdf":
        return handbook_adapter
    if source_kind == "web_json":
        return WebJsonAdapter(profile=get_profile(profile))
    if source_kind == "table_csv":
        # A profile name may live in either registry, so --profile works for
        # both without a second flag.
        # An explicit name wins when it exists; otherwise fall back to matching
        # the file's columns, so one --profile can cover both registries.
        table = (TABLE_PROFILES.get(profile) if profile else None) or detect_profile(
            path, TABLE_PROFILES
        )
        if table is None:
            known = ", ".join(sorted(TABLE_PROFILES)) or "(none loaded)"
            raise InputError(
                "a CSV source needs a table profile: pass --profile-file with a "
                f'"kind": "csv" profile, or --profile <name>. Loaded: {known}'
            )
        return CsvTableAdapter(table)
    raise InputError(
        f"{Path(path).name}: source kind is required "
        "(poster_ocr | handbook_pdf | web_json | table_csv); pass --source-kind or use "
        f"{Path(path).name}:web_json"
    )
