from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sou_crawler.pbl_audit import verify_pbl_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the structured output of one HIREP PBL crawl batch.")
    parser.add_argument("--output-dir", required=True, help="PBL output directory to verify.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any required output is incomplete.")
    args = parser.parse_args()

    result = verify_pbl_output(resolve_path(args.output_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and not result["valid"] else 0


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
