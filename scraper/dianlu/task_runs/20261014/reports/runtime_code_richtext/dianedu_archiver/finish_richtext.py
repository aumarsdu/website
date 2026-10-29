"""Resume literal rich-text references under the unchanged cumulative budget."""
import asyncio
import logging
from pathlib import Path
import time

from .referenced_archive import ReferencedArchive
from .storage import read_json, write_json
from .utils import utc_now


async def execute():
    root = Path(__file__).resolve().parents[1] / "task_runs/20261014"
    limits = read_json(root / "reports/resource_limits.json", {})
    archive = ReferencedArchive(root, 20, 12, True)
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
        write_json(root / "reports/richtext_finished.json", {"finished_at": utc_now(), "progress": read_json(root / "reports/referenced_progress.json", {})})


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(execute())
