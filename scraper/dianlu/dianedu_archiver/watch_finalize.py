"""Finish the existing bounded batch with local validation and exports."""
import json
from pathlib import Path
import time

from .finalize_completion import main as finalize
from .storage import read_json, write_json
from .utils import utc_now


def main():
    root = Path(__file__).resolve().parents[1] / "task_runs/20261014"
    limits = read_json(root / "reports/resource_limits.json", {})
    deadline = limits.get("deadline_epoch", time.time()) + 300
    while time.time() < deadline:
        try:
            progress = read_json(root / "reports/referenced_progress.json", {})
        except json.JSONDecodeError:
            time.sleep(1)
            continue
        if progress.get("status") in {"finished", "stopped"}:
            finalize()
            from .acceptance_inventory import main as reconcile
            reconcile()
            write_json(root / "reports/batch_finished.json", {"finished_at": utc_now(), "resource_status": progress["status"], "stop_reason": progress.get("stop_reason"), "acceptance_report": str(root / "reports/completion_acceptance.md")})
            return
        time.sleep(50)
    write_json(root / "reports/batch_finished.json", {"finished_at": utc_now(), "resource_status": "unknown", "stop_reason": "watch_deadline_exceeded"})


if __name__ == "__main__":
    main()
