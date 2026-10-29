"""Apply an explicitly authorized total-duration extension without reset."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil

from .storage import read_json, write_json
from .utils import utc_now


def extend_limit(root: Path, total_hours: float) -> dict:
    path = root / "reports/resource_limits.json"
    limits = read_json(path, {})
    started = datetime.fromisoformat(limits["started_at"]).timestamp()
    old_deadline = limits["deadline_epoch"]
    new_deadline = started + total_hours * 3600
    if total_hours <= 0 or new_deadline + 0.001 < old_deadline:
        raise ValueError("This command only extends the existing total duration")
    if abs(new_deadline - old_deadline) < 0.001:
        return limits
    previous_hours = (old_deadline - started) / 3600
    snapshot = root / "reports" / f"acceptance_{previous_hours:g}h"
    snapshot.mkdir(exist_ok=True)
    for name in ("resource_limits.json", "referenced_progress.json", "completion_audit.json", "completion_acceptance.md", "pending_references.json", "pending_references.csv", "failed_references.csv", "batch_finished.json"):
        source = root / "reports" / name
        target = snapshot / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
    limits.setdefault("extensions", []).append({"applied_at": utc_now(), "previous_deadline_epoch": old_deadline, "new_deadline_epoch": new_deadline, "total_hours": total_hours, "max_bytes": limits["max_bytes"], "transferred_bytes_at_extension": limits["transferred_bytes"]})
    limits["deadline_epoch"] = new_deadline
    limits["total_hours"] = total_hours
    temporary = path.with_suffix(".json.tmp")
    write_json(temporary, limits)
    temporary.replace(path)
    progress_path = root / "reports/referenced_progress.json"
    progress = read_json(progress_path, {})
    progress.update(status="resuming", previous_stop_reason=progress.get("stop_reason"), stop_reason=None, updated_at=utc_now())
    write_json(progress_path, progress)
    return limits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total-hours", type=float, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "task_runs/20261014"
    print(extend_limit(root, args.total_hours))


if __name__ == "__main__":
    main()
