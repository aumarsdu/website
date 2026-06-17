from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    base_url: str = "https://www.openision.com"
    user_agent: str = "AuthorizedOpenisionCrawler/1.0 contact=YOUR_EMAIL_HERE"
    request_min_delay_seconds: float = 0.5
    request_max_delay_seconds: float = 2.0
    concurrency: int = 1
    headless: bool = True
    max_probe_pages: int = 10
    enable_login_state: bool = False
    storage_state_path: Path = Path("data/probe/storage_state.json")
    output_dir: Path = Path("data")
    allowed_domains: tuple[str, ...] = ("www.openision.com", "openision.com")
    initial_paths: tuple[str, ...] = ("/", "/schools?quick_query=may_you_like", "/cases")


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _load_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_list_key:
            data.setdefault(current_list_key, []).append(_parse_scalar(line[4:]))
            continue
        current_list_key = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if value.strip() == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = _parse_scalar(value)
    return data


def load_settings(project_root: Path | None = None) -> Settings:
    root = project_root or Path.cwd()
    config_path = root / "config" / "settings.yaml"
    if not config_path.exists():
        config_path = root / "config" / "settings.example.yaml"
    values = _load_simple_yaml(config_path) if config_path.exists() else {}
    return Settings(
        base_url=str(values.get("base_url", Settings.base_url)),
        user_agent=str(values.get("user_agent", Settings.user_agent)),
        request_min_delay_seconds=float(values.get("request_min_delay_seconds", Settings.request_min_delay_seconds)),
        request_max_delay_seconds=float(values.get("request_max_delay_seconds", Settings.request_max_delay_seconds)),
        concurrency=int(values.get("concurrency", Settings.concurrency)),
        headless=bool(values.get("headless", Settings.headless)),
        max_probe_pages=int(values.get("max_probe_pages", Settings.max_probe_pages)),
        enable_login_state=bool(values.get("enable_login_state", Settings.enable_login_state)),
        storage_state_path=Path(str(values.get("storage_state_path", Settings.storage_state_path))),
        output_dir=Path(str(values.get("output_dir", Settings.output_dir))),
        allowed_domains=tuple(values.get("allowed_domains", Settings.allowed_domains)),
        initial_paths=tuple(values.get("initial_paths", Settings.initial_paths)),
    )
