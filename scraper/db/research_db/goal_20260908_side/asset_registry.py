"""T05 asset registry: streaming hashes, blob dedup, locations, links, derivation.

Pure functions plus optional PostgreSQL persistence via the T03 model tables
(asset_blobs / asset_locations / asset_links). Locations must resolve inside an
approved root; missing files and unknown positions are reported separately.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class AssetError(ValueError):
    """The asset violated the registry boundary."""


def sha256_stream(path: Path) -> str:
    """Stream a file; never loads whole files into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def safe_asset_path(root: Path, relative: str) -> Path:
    """Reject absolute paths, traversal and symlink components."""
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise AssetError("path_out_of_scope")
    path = root / rel
    current = root.resolve()
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise AssetError("path_out_of_scope")
    return path


def register_location(
    root: Path,
    relative: str,
    state: str,
    blobs: dict[str, dict[str, Any]],
    locations: dict[str, dict[str, Any]],
    derived_from: str | None = None,
) -> dict[str, Any]:
    """Register one file location; identical bytes reuse the existing blob."""
    if state not in ("downloaded", "original", "processed", "delivery"):
        raise AssetError("unknown_location_state")
    path = safe_asset_path(root, relative)
    if not path.is_file():
        entry = {
            "relative_path": relative,
            "state": state,
            "status": "missing",
            "blob_sha256": None,
            "byte_size": None,
            "derived_from": derived_from,
        }
        locations[relative] = entry
        return entry
    digest = sha256_stream(path)
    blob = blobs.setdefault(
        digest,
        {"sha256": digest, "byte_size": path.stat().st_size, "locations": []},
    )
    blob["locations"].append(relative)
    entry = {
        "relative_path": relative,
        "state": state,
        "status": "ok",
        "blob_sha256": digest,
        "byte_size": blob["byte_size"],
        "derived_from": derived_from,
    }
    locations[relative] = entry
    return entry


def link_blob(
    blob_sha256: str,
    role: str,
    blobs: dict[str, dict[str, Any]],
    locations: dict[str, dict[str, Any]],
    links: list[dict[str, Any]],
    provider_project: str | None = None,
    source_record: str | None = None,
    derived_from_location: str | None = None,
) -> dict[str, Any]:
    """Attach a blob to a project/record; one blob may serve many projects."""
    if blob_sha256 not in blobs:
        raise AssetError("blob_unknown")
    if provider_project is None and source_record is None:
        raise AssetError("link_target_missing")
    if derived_from_location is not None and (
        derived_from_location not in locations
        or locations[derived_from_location]["status"] != "ok"
    ):
        raise AssetError("derived_from_unknown")
    link = {
        "blob_sha256": blob_sha256,
        "role": role,
        "provider_project": provider_project,
        "source_record": source_record,
        "location_path": derived_from_location,
    }
    links.append(link)
    return link


def derivation_chain(
    start_location: str, locations: dict[str, dict[str, Any]]
) -> list[str]:
    """Follow processed→original derivation; unknown and missing visible; loop detection."""
    chain = [start_location]
    seen = {start_location}
    current = start_location
    while True:
        entry = locations.get(current)
        if entry is None:
            chain.append("<unknown_location>")
            return chain
        if entry["status"] == "missing":
            chain.append("<missing_file>")
            return chain
        derived_from = entry.get("derived_from")
        if derived_from is None:
            return chain
        if derived_from in seen:
            chain.append(f"<cycle:{derived_from}>")
            return chain
        chain.append(derived_from)
        seen.add(derived_from)
        current = derived_from


def counts(
    blobs: dict[str, dict[str, Any]],
    locations: dict[str, dict[str, Any]],
    links: list[dict[str, Any]],
) -> dict[str, int]:
    """Report file locations, unique blobs and links separately."""
    return {
        "file_locations": len(locations),
        "missing_locations": sum(
            1 for l in locations.values() if l["status"] == "missing"
        ),
        "unique_blobs": len(blobs),
        "links": len(links),
    }
