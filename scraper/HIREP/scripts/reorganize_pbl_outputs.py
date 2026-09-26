from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sou_crawler.storage import iter_jsonl, write_json, write_jsonl
from sou_crawler.utils import file_extension_from_url, safe_filename, stable_hash


ASSET_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bin"}


@dataclass
class MigrationStats:
    output_dir: str
    projects: int = 0
    detail_files_written: int = 0
    asset_manifest_entries: int = 0
    assets_linked_or_copied: int = 0
    assets_already_current: int = 0
    assets_missing_source: int = 0
    assets_without_project: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "projects": self.projects,
            "detail_files_written": self.detail_files_written,
            "asset_manifest_entries": self.asset_manifest_entries,
            "assets_linked_or_copied": self.assets_linked_or_copied,
            "assets_already_current": self.assets_already_current,
            "assets_missing_source": self.assets_missing_source,
            "assets_without_project": self.assets_without_project,
            "errors": self.errors,
        }


def discover_output_dirs(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.glob("output*")
        if path.is_dir() and (path / "processed" / "projects.jsonl").exists()
    )


def migrate_output(output_dir: Path, *, dry_run: bool = False) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    stats = MigrationStats(output_dir=str(output_dir))
    projects = _load_projects(output_dir / "processed" / "projects.jsonl")
    stats.projects = len(projects)
    migrated_projects = with_project_directories(output_dir, projects)
    project_by_id = {
        str(project.get("business_id") or ""): project
        for project in migrated_projects
        if project.get("business_id")
    }

    for item in migrated_projects:
        project_dir = project_folder(output_dir, item)
        if not dry_run:
            project_dir.mkdir(parents=True, exist_ok=True)
            write_json(project_dir / "详情页信息.json", item)
        stats.detail_files_written += 1

    manifest = load_manifest(output_dir)
    stats.asset_manifest_entries = len(manifest)
    migrated_manifest: list[dict[str, Any]] = []
    for item in manifest:
        migrated = dict(item)
        project = _project_for_manifest_item(item, project_by_id)
        if not project:
            stats.assets_without_project += 1
            migrated_manifest.append(migrated)
            continue
        source = _resolve_existing_path(item.get("file"), output_dir)
        if not source:
            stats.assets_missing_source += 1
            migrated["migration_error"] = "source_file_missing"
            migrated_manifest.append(migrated)
            continue
        target = desired_asset_path(output_dir, project, item, source)
        if source.resolve() == target.resolve():
            stats.assets_already_current += 1
        elif target.exists() and _same_file_content(source, target):
            stats.assets_already_current += 1
        else:
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                _link_or_copy(source, target)
            stats.assets_linked_or_copied += 1
        migrated.update(
            {
                "category": project.get("category"),
                "direction": project.get("direction") or project.get("major_name"),
                "project_dir": str(project_folder(output_dir, project)),
                "file": str(target),
                "migration_source_file": str(source),
            }
        )
        migrated_manifest.append(migrated)

    if not dry_run:
        write_jsonl(output_dir / "processed" / "projects.jsonl", migrated_projects)
        if migrated_manifest:
            write_jsonl(output_dir / "processed" / "asset_manifest.jsonl", migrated_manifest)
            write_json(output_dir / "processed" / "asset_manifest.json", migrated_manifest)
        write_json(output_dir / "reports" / "reorganize_assets_report.json", stats.as_dict())
    return stats.as_dict()


def project_folder(output_dir: Path, project: dict[str, Any]) -> Path:
    if project.get("project_dir"):
        return Path(str(project["project_dir"]))
    return base_project_folder(output_dir, project)


def base_project_folder(output_dir: Path, project: dict[str, Any]) -> Path:
    category = safe_filename(project.get("category"), fallback="未分类目录")
    direction = safe_filename(project.get("direction") or project.get("major_name"), fallback="未分类方向")
    title = safe_filename(project.get("title"), fallback=str(project.get("business_id") or "project"))
    return output_dir / "assets" / category / direction / title


def with_project_directories(output_dir: Path, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[Path, int] = {}
    for project in projects:
        folder = base_project_folder(output_dir, project)
        counts[folder] = counts.get(folder, 0) + 1

    migrated: list[dict[str, Any]] = []
    for project in projects:
        item = dict(project)
        folder = base_project_folder(output_dir, item)
        if counts.get(folder, 0) > 1:
            folder = folder.with_name(f"{folder.name}__{safe_filename(item.get('business_id'), fallback='id')}")
        item["project_dir"] = str(folder)
        migrated.append(item)
    return migrated


def desired_asset_path(output_dir: Path, project: dict[str, Any], item: dict[str, Any], source: Path) -> Path:
    source_url = str(item.get("source_url") or "")
    ext = _asset_ext(source, source_url)
    field = str(item.get("field") or "")
    base = _asset_base_name(project, item, field)
    target = project_folder(output_dir, project) / f"{base}{ext}"
    if target.exists() and source.exists() and not _same_file_content(source, target):
        return _unique_path(target)
    return target


def load_manifest(output_dir: Path) -> list[dict[str, Any]]:
    jsonl = output_dir / "processed" / "asset_manifest.jsonl"
    if jsonl.exists():
        return list(iter_jsonl(jsonl) or [])
    json_path = output_dir / "processed" / "asset_manifest.json"
    if not json_path.exists():
        return []
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _load_projects(path: Path) -> list[dict[str, Any]]:
    return [item for item in (iter_jsonl(path) or []) if isinstance(item, dict)]


def _project_for_manifest_item(item: dict[str, Any], project_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    business_id = _business_id_from_manifest_key(str(item.get("manifest_key") or ""))
    if business_id and business_id in project_by_id:
        return project_by_id[business_id]
    title = str(item.get("record_title") or "")
    for project in project_by_id.values():
        if title and title == str(project.get("title") or ""):
            return project
    return None


def _business_id_from_manifest_key(value: str) -> str:
    if "::" not in value:
        return ""
    return value.split("::", 1)[0]


def _resolve_existing_path(value: Any, output_dir: Path) -> Path | None:
    if not value:
        return None
    raw = Path(str(value))
    candidates = [raw]
    if not raw.is_absolute():
        candidates.extend([Path.cwd() / raw, output_dir.parent / raw, output_dir / raw])
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _asset_ext(source: Path, source_url: str) -> str:
    suffix = source.suffix.lower()
    if suffix in ASSET_EXTENSIONS:
        return suffix
    return file_extension_from_url(source_url, suffix or ".bin")


def _asset_base_name(project: dict[str, Any], item: dict[str, Any], field: str) -> str:
    if field in {"attachmentId", "industryPoster"}:
        return "海报"
    if field == "courseBanner":
        return "Banner"
    if field == "thumbnailId":
        return "缩略图"
    if field == "professorAvatar" or "professor" in field.lower():
        return safe_filename(project.get("professor"), fallback="professor")

    file_name = _file_name_for_direct_asset(project, item)
    if file_name:
        return _filename_stem(file_name)

    title = safe_filename(project.get("title"), fallback=str(project.get("business_id") or "project"))
    if field == "detailAsset":
        return f"{title}-详情附件-{stable_hash(str(item.get('source_url') or item.get('file') or title))[:8]}"
    return f"{title}-{safe_filename(field, fallback='asset')}"


def _file_name_for_direct_asset(project: dict[str, Any], item: dict[str, Any]) -> str:
    source_url = str(item.get("source_url") or "")
    field = str(item.get("field") or "")
    for asset in project.get("direct_assets", []) if isinstance(project.get("direct_assets"), list) else []:
        if not isinstance(asset, dict):
            continue
        if source_url and asset.get("url") == source_url and (not field or asset.get("field") == field):
            return str(asset.get("file_name") or "")
    return ""


def _filename_stem(value: Any) -> str:
    name = safe_filename(value, fallback="asset")
    suffix = Path(name).suffix.lower()
    if suffix in {".pdf", ".jpg", ".jpeg", ".png", ".webp"}:
        return Path(name).stem or "asset"
    return name


def _same_file_content(left: Path, right: Path) -> bool:
    try:
        return left.stat().st_size == right.stat().st_size
    except OSError:
        return False


def _link_or_copy(source: Path, target: Path) -> None:
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _unique_path(path: Path) -> Path:
    for idx in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{idx}{path.suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{path.stem}-{stable_hash(str(path))}{path.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reorganize historical PBL crawl outputs into category/direction/topic folders.")
    parser.add_argument("output_dirs", nargs="*", help="Output directories to migrate. Defaults to every output* directory with projects.jsonl.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned stats without writing files.")
    args = parser.parse_args()

    root = Path.cwd()
    output_dirs = [Path(value) for value in args.output_dirs] if args.output_dirs else discover_output_dirs(root)
    reports = [migrate_output(path, dry_run=args.dry_run) for path in output_dirs]
    print(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
