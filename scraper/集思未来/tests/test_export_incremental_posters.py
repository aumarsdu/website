import json
from pathlib import Path

from scripts.export_incremental_posters import collect_posters, image_suffix, unique_by_content


def write_metadata(path: Path, course_id: str, poster: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "id": course_id,
                "files": [{"role": "课程海报", "copied": True, "source": str(poster)}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_collect_posters_deduplicates_identical_content(tmp_path: Path) -> None:
    source_root = tmp_path / "run"
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    third = tmp_path / "third.png"
    first.write_bytes(b"same-poster")
    second.write_bytes(b"same-poster")
    third.write_bytes(b"different-poster")
    write_metadata(source_root / "sou_tools" / "organized_by_site" / "a" / "metadata.json", "course-a", first)
    write_metadata(source_root / "sou_tools" / "organized_by_site" / "b" / "metadata.json", "course-b", second)
    write_metadata(source_root / "domestic" / "organized_by_site" / "c" / "metadata.json", "course-c", third)

    posters = collect_posters(source_root)
    unique = unique_by_content(posters)

    assert len(posters) == 3
    assert len(unique) == 2
    assert {poster.destination_name for poster in unique} == {"sou_tools__course-a.jpg", "domestic__course-c.png"}


def test_image_suffix_uses_magic_bytes_when_paths_have_no_image_extension(tmp_path: Path) -> None:
    source = tmp_path / "poster"
    source.write_bytes(b"\xff\xd8\xff\xe0jpeg")

    assert image_suffix(source, tmp_path / "unknown") == ".jpg"
