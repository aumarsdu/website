#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dianedu_archiver.helipei_summer import build_helipei_summer_db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Helipei summer program SQLite database from DianEdu archive.")
    parser.add_argument("--source-db", default=str(ROOT / "data" / "processed" / "dianedu.sqlite"))
    parser.add_argument("--output-db", default=str(ROOT / "data" / "processed" / "helipei_summer_programs.sqlite"))
    args = parser.parse_args()
    stats = build_helipei_summer_db(Path(args.source_db), Path(args.output_db))
    print(json.dumps(stats.__dict__ if hasattr(stats, "__dict__") else {
        "source_projects": stats.source_projects,
        "summer_programs": stats.summer_programs,
        "sessions": stats.sessions,
        "costs": stats.costs,
        "tags": stats.tags,
        "quality_issues": stats.quality_issues,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
