"""Web material adapter: structured partner records mapped by a source profile.

A :class:`SourceProfile` *is* the field table. Adding a new partner, or
confirming the real field names for an existing one, is a data edit in
:data:`SOURCE_PROFILES` -- no code change, and no risk of a claim being
extracted by a rule nobody reviewed.

A profile lists, per canonical field, the ordered JSON paths to try. A field
with no path stays missing on purpose. That is the difference between "not
stated by this source" and "we guessed".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..config import Settings
from ..errors import InputError
from ..extract import claims_from_json_paths
from ..schema import FieldClaim, RejectedCandidate
from ..storage import read_jsonl
from ..utils import clean_text, comparison_key, json_path_get
from .base import AdapterOutput, make_document


@dataclass(frozen=True)
class SourceProfile:
    """How one partner's payload maps onto the six canonical fields."""

    name: str
    provider: str
    fields: Mapping[str, tuple[str, ...]]
    external_id_paths: tuple[str, ...] = ()
    title_paths: tuple[str, ...] = ()
    probe_paths: tuple[str, ...] = ()
    source_authority: str = "supplier_official"
    notes: str = ""

    def external_id(self, payload: Any) -> str | None:
        return self._first(payload, self.external_id_paths)

    def title(self, payload: Any) -> str | None:
        return self._first(payload, self.title_paths)

    @staticmethod
    def _first(payload: Any, paths: Iterable[str]) -> str | None:
        for path in paths:
            value = json_path_get(payload, path)
            if isinstance(value, (str, int, float)) and clean_text(value):
                return clean_text(value)
        return None

    def consumed_leaf_keys(self, payload: Any) -> set[str]:
        """Leaf keys of every path that actually resolved for this record."""
        keys: set[str] = set()
        for paths in (*self.external_id_paths, *self.title_paths, *(self.fields.values())):
            for path in paths:
                value = json_path_get(payload, path)
                if value is None or isinstance(value, (dict, list)):
                    continue
                leaf = path.split(".")[-1].replace("$..", "")
                if leaf:
                    keys.add(comparison_key(leaf))
        return keys

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "source_authority": self.source_authority,
            "fields": {field: list(paths) for field, paths in self.fields.items()},
            "notes": self.notes,
        }


# --------------------------------------------------------------------------
# Profiles. Order matters: auto-detection returns the first profile whose
# probe paths resolve.
# --------------------------------------------------------------------------

_SOU_FIELDS: dict[str, tuple[str, ...]] = {
    "project_title": ("$.name", "$.raw.name"),
    "instructor": ("$.raw.teacherName", "$.raw.teacher", "$.raw.teacherNameEn"),
    "start_date": ("$.raw.schoolBegins",),
    "duration": ("$.raw.cycle",),
    "suitable_audience": ("$.raw.suggestBasics",),
    "output_description": ("$.raw.output",),
}

SOURCE_PROFILES: dict[str, SourceProfile] = {
    "sou_domestic": SourceProfile(
        name="sou_domestic",
        provider="sou_domestic",
        fields=_SOU_FIELDS,
        external_id_paths=("$.id", "$.raw.id"),
        title_paths=("$.name", "$.raw.name"),
        probe_paths=("$.raw.cycle", "$.raw.schoolBegins", "$.raw.teacherName"),
        notes="集思未来 domestic.gecacademy.cn 归一化产出 (sou_crawler processed/records.jsonl)。",
    ),
    "sou_overseas": SourceProfile(
        name="sou_overseas",
        provider="sou_overseas",
        fields=_SOU_FIELDS,
        external_id_paths=("$.id", "$.raw.id"),
        title_paths=("$.name", "$.raw.name"),
        probe_paths=("$.raw.cycle", "$.raw.schoolBegins", "$.raw.teacherName"),
        notes="集思未来 sou-tools.gecacademy.cn 归一化产出，字段结构与 domestic 一致。",
    ),
    "zhongke": SourceProfile(
        name="zhongke",
        provider="zhongke",
        # Only title and instructor are confirmed present in the normalized
        # record. 开课日期 lives in the separate 开课时间汇总 CSV and is not
        # mapped here on purpose: an unmapped field stays missing instead of
        # being back-filled from a different file.
        fields={
            "project_title": ("$.title", "$.raw.title"),
            "instructor": ("$.teacher", "$.raw.teacher"),
        },
        external_id_paths=("$.id", "$.uuid", "$.raw.id", "$.raw.uuid"),
        title_paths=("$.title", "$.raw.title"),
        probe_paths=("$.title", "$.teacher"),
        notes="中科 sou_crawler 归一化产出。开课日期/周期/产出需接《中科课题开课时间汇总》CSV 后再补映射。",
    ),
    "generic": SourceProfile(
        name="generic",
        provider="generic",
        # Recursive paths are a documented fallback, not a guess: they only run
        # after every explicit path failed, and they extract at "low" confidence.
        fields={
            "project_title": ("$.title", "$.project_title", "$.name", "$..name"),
            "instructor": ("$.teacher", "$.instructor", "$.professor", "$..teacherName", "$..teacher"),
            "start_date": ("$.start_date", "$..schoolBegins", "$..startDate"),
            "duration": ("$.duration", "$..cycle", "$..duration"),
            "suitable_audience": ("$.suitable_audience", "$..suggestBasics", "$..suitableFor"),
            "output_description": ("$.output_description", "$..output", "$..deliverables"),
        },
        external_id_paths=("$.id", "$.uuid", "$.record_key", "$.raw.id"),
        title_paths=("$.title", "$.name", "$.raw.name"),
        probe_paths=("$.title", "$.name", "$.raw"),
        notes="通用兜底档。真实接线时用 --profile 显式指定，避免误配。",
    ),
}


def get_profile(name: str | None) -> SourceProfile | None:
    if not name:
        return None
    return SOURCE_PROFILES.get(name)


# Auto-detection order. Built-ins are ordered as declared; a profile loaded
# from a file is moved to the front, because an operator who supplied a field
# table means it -- a built-in guess must not win over it.
_DETECTION_ORDER: list[str] = list(SOURCE_PROFILES)


def detection_order() -> list[SourceProfile]:
    return [SOURCE_PROFILES[name] for name in _DETECTION_ORDER if name in SOURCE_PROFILES]


def register_profile(profile: SourceProfile, *, prefer: bool = True) -> SourceProfile:
    """Add or replace a profile at runtime (used by ``--profile-file``)."""
    SOURCE_PROFILES[profile.name] = profile
    if prefer:
        if profile.name in _DETECTION_ORDER:
            _DETECTION_ORDER.remove(profile.name)
        _DETECTION_ORDER.insert(0, profile.name)
    return profile


def load_profile_file(path: str | Path) -> SourceProfile:
    """Load a field table from JSON.

    This is the wiring surface for a new partner: the field mapping is data, so
    connecting a real source needs a JSON file and no code change. See
    ``data/synthetic/web_profile.demo.json`` for the exact shape.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InputError(f"{path}: profile file must be a JSON object")
    name = clean_text(str(payload.get("name", "")))
    if not name:
        raise InputError(f"{path}: profile needs a 'name'")
    raw_fields = payload.get("fields") or {}
    if not isinstance(raw_fields, dict):
        raise InputError(f"{path}: 'fields' must be an object")
    fields = {
        str(field): tuple(str(item) for item in paths if str(item))
        for field, paths in raw_fields.items()
        if isinstance(paths, (list, tuple))
    }
    probe = [str(item) for item in (payload.get("probe_paths") or [])]
    if not probe:
        # Default probes let auto-detection work for a file-provided profile.
        probe = [paths[0] for paths in fields.values() if paths]
    return register_profile(
        SourceProfile(
            name=name,
            provider=clean_text(str(payload.get("provider", ""))) or name,
            fields=fields,
            external_id_paths=tuple(payload.get("external_id_paths") or ()),
            title_paths=tuple(payload.get("title_paths") or ()),
            probe_paths=tuple(probe),
            source_authority=clean_text(str(payload.get("source_authority", "supplier_official"))),
            notes=clean_text(str(payload.get("notes", ""))),
        )
    )


class WebJsonAdapter:
    """Read partner crawler JSONL output through a source profile."""

    name = "web_json"
    source_kind = "web_json"
    accepts = ("*.jsonl",)

    def __init__(self, profile: SourceProfile | None = None) -> None:
        self.profile = profile
        # Set by the pipeline so one corrupt line does not lose the whole file.
        self.on_error: Callable[[int, Exception], None] | None = None

    def resolve_profile(self, payload: Any) -> SourceProfile:
        if self.profile is not None:
            return self.profile
        for profile in detection_order():
            for probe in profile.probe_paths:
                value = json_path_get(payload, probe)
                if value is not None and not isinstance(value, (dict, list)):
                    return profile
        return SOURCE_PROFILES["generic"]

    def load(self, path: Path, settings: Settings) -> list[AdapterOutput]:
        rows = list(read_jsonl(Path(path), on_error=self.on_error))
        # Resolve profiles first so every document records what the file looked like.
        resolved = [self.resolve_profile(payload) for payload in rows]
        profiles_used: dict[str, int] = {}
        for profile in resolved:
            profiles_used[profile.name] = profiles_used.get(profile.name, 0) + 1

        outputs: list[AdapterOutput] = []
        for index, (payload, profile) in enumerate(zip(rows, resolved)):
            external_id = profile.external_id(payload)
            stable_key = (
                external_id
                or clean_text(payload.get("record_key", ""))
                or clean_text(payload.get("source_url", ""))
                or f"row-{index:05d}"
            )
            document_id = f"{profile.provider}#{stable_key}"

            rejected: list[RejectedCandidate] = []
            claims: list[FieldClaim] = claims_from_json_paths(
                payload,
                profile.fields,
                document_id=document_id,
                profile_name=profile.name,
                rejected=rejected,
            )

            consumed = profile.consumed_leaf_keys(payload)
            raw_payload = payload.get("raw")
            candidate_keys = set(payload.keys())
            if isinstance(raw_payload, dict):
                candidate_keys |= set(raw_payload.keys())
            unmapped = sorted(
                key
                for key in candidate_keys
                if key != "raw" and comparison_key(key) not in consumed
            )

            document = make_document(
                document_id=document_id,
                source_kind=self.source_kind,
                provider=profile.provider,
                origin=str(Path(path)),
                external_id=external_id,
                title_hint=profile.title(payload),
                source_authority=profile.source_authority,
                meta={
                    "profile": profile.name,
                    "profiles_in_file": dict(sorted(profiles_used.items())),
                    "source_url": clean_text(payload.get("source_url", "")) or None,
                    "crawled_at": clean_text(payload.get("crawled_at", "")) or None,
                    "profile_notes": profile.notes,
                },
            )
            outputs.append(
                AdapterOutput(
                    document=document,
                    claims=claims,
                    rejected=rejected,
                    stats={"profile": profile.name},
                    unmapped_source_keys=unmapped,
                )
            )
        return outputs


def profile_catalog() -> list[dict[str, Any]]:
    return [SOURCE_PROFILES[name].to_dict() for name in sorted(SOURCE_PROFILES)]
