from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@dataclass(frozen=True)
class Poster:
    site: str
    course_id: str
    source: Path
    digest: str
    suffix: str

    @property
    def destination_name(self) -> str:
        return f"{self.site}__{self.course_id}{self.suffix}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export unique course posters from an incremental crawl run.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    posters = collect_posters(args.source_root)
    selected = unique_by_content(posters)
    result = {
        "source_root": str(args.source_root),
        "destination": str(args.destination),
        "poster_references": len(posters),
        "unique_posters": len(selected),
        "copied": [],
        "skipped_existing": [],
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        result["planned_files"] = [poster.destination_name for poster in selected]
        write_json(args.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    args.destination.mkdir(parents=True, exist_ok=True)
    for poster in selected:
        destination = args.destination / poster.destination_name
        if destination.exists():
            if file_digest(destination) == poster.digest:
                result["skipped_existing"].append(str(destination))
                continue
            raise FileExistsError(f"Refusing to overwrite a different poster: {destination}")
        shutil.copy2(poster.source, destination)
        result["copied"].append(
            {
                "site": poster.site,
                "course_id": poster.course_id,
                "source": str(poster.source),
                "destination": str(destination),
            }
        )
    write_json(args.report, result)
    print(json.dumps({key: result[key] for key in ("unique_posters", "copied", "skipped_existing")}, ensure_ascii=False))
    return 0


def collect_posters(source_root: Path) -> list[Poster]:
    posters: list[Poster] = []
    for site in ("sou_tools", "domestic"):
        organized_root = source_root / site / "organized_by_site"
        for metadata_path in organized_root.glob("**/metadata.json"):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            course_id = str(metadata.get("id") or "").strip()
            if not course_id:
                continue
            for item in metadata.get("files") or []:
                if not isinstance(item, dict) or item.get("role") != "课程海报" or not item.get("copied"):
                    continue
                source = Path(str(item.get("source") or ""))
                suffix = image_suffix(source, Path(str(item.get("target") or "")))
                if source.is_file() and suffix:
                    posters.append(
                        Poster(
                            site=site,
                            course_id=course_id,
                            source=source,
                            digest=file_digest(source),
                            suffix=suffix,
                        )
                    )
    return sorted(posters, key=lambda poster: (poster.course_id, poster.site, str(poster.source)))


def unique_by_content(posters: list[Poster]) -> list[Poster]:
    selected: list[Poster] = []
    seen: set[str] = set()
    for poster in posters:
        if poster.digest in seen:
            continue
        seen.add(poster.digest)
        selected.append(poster)
    return selected


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def image_suffix(source: Path, target: Path) -> str | None:
    for candidate in (target.suffix.lower(), source.suffix.lower()):
        if candidate in IMAGE_SUFFIXES:
            return candidate
    if not source.is_file():
        return None
    header = source.read_bytes()[:16]
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    return None


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
