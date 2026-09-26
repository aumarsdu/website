from __future__ import annotations

import os
import shutil
from pathlib import Path


def link_or_copy(source: Path, target: Path) -> str:
    """Hard-link source to target, falling back to a copy on failure.

    Returns the action taken ("link" or "copy") so callers can record it.
    """
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
        return "link"
    except OSError:
        shutil.copy2(source, target)
        return "copy"
