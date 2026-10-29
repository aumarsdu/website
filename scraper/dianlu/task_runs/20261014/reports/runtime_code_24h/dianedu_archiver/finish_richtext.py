"""Resume literal rich-text references under the unchanged cumulative budget."""
import asyncio
import logging
from pathlib import Path
import time
import hashlib
import shutil
import os

from .referenced_archive import ReferencedArchive
from .storage import read_json, write_json
from .utils import utc_now


async def execute():
    root = Path(__file__).resolve().parents[1] / "task_runs/20261014"
    limits = read_json(root / "reports/resource_limits.json", {})
    hours = limits.get("total_hours", 12)
    runtime = root / "reports" / f"runtime_code_{hours:g}h"
    code_dir = runtime / "dianedu_archiver"
    code_dir.mkdir(parents=True, exist_ok=True)
    hashes = []
    for name in ("referenced_archive.py", "public_transport.py", "robots_policy.py", "finish_richtext.py"):
        source = Path(__file__).resolve().parent / name
        shutil.copy2(source, code_dir / name)
        hashes.append(f"{hashlib.sha256(source.read_bytes()).hexdigest()}  dianedu_archiver/{name}\n")
    (runtime / "runtime.sha256").write_text("".join(hashes), encoding="utf-8")
    write_json(root / "reports/resource_runtime_current.json", {"started_at": utc_now(), "pid": os.getpid(), "snapshot": str(runtime.relative_to(root)), "deadline_epoch": limits["deadline_epoch"]})
    archive = ReferencedArchive(root, 20, hours, True)
    try:
        await asyncio.wait_for(archive.run(), max(0, limits["deadline_epoch"] - time.time()))
    except TimeoutError:
        archive.save("stopped", "time_budget_reached")
    except Exception as exc:
        archive.save("stopped", str(exc))
    finally:
        await archive.client.aclose()
        from .finalize_completion import main as finalize
        from .acceptance_inventory import main as reconcile
        finalize()
        reconcile()
        write_json(root / "reports/richtext_finished.json", {"finished_at": utc_now(), "deadline_epoch": limits["deadline_epoch"], "progress": read_json(root / "reports/referenced_progress.json", {})})


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(execute())
