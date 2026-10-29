from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"YAML must contain a mapping: {path}")
    return value


def load_domains(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    return load_yaml(root / "config" / "domains.yaml")


def load_crawl_config(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    return load_yaml(root / "config" / "crawl.yaml")


def load_extraction_config(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    return load_yaml(root / "config" / "extraction.yaml")
