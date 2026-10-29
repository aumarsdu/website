from datetime import datetime
import json

import pytest

from dianedu_archiver.extend_resource_limit import extend_limit


def make_limits(root):
    (root / "reports").mkdir()
    started_at = "2026-10-14T03:03:34+00:00"
    started = datetime.fromisoformat(started_at).timestamp()
    limits = {"started_at": started_at, "deadline_epoch": started + 21600, "max_bytes": 20000000000, "transferred_bytes": 10857721624}
    (root / "reports/resource_limits.json").write_text(json.dumps(limits))
    (root / "reports/referenced_progress.json").write_text(json.dumps({"status": "stopped", "stop_reason": "time_budget_reached", "blocked_hosts": ["denied.example"], "downloaded": 5343}))
    return limits


def test_extension_uses_original_start_preserves_bytes_denials_and_snapshot(tmp_path):
    before = make_limits(tmp_path)
    after = extend_limit(tmp_path, 12)
    assert after["deadline_epoch"] == before["deadline_epoch"] + 21600
    assert after["started_at"] == before["started_at"]
    assert after["max_bytes"] == before["max_bytes"]
    assert after["transferred_bytes"] == before["transferred_bytes"]
    assert json.loads((tmp_path / "reports/acceptance_6h/resource_limits.json").read_text()) == before
    progress = json.loads((tmp_path / "reports/referenced_progress.json").read_text())
    assert progress["blocked_hosts"] == ["denied.example"]
    assert progress["downloaded"] == 5343
    assert progress["status"] == "resuming"
    assert len(extend_limit(tmp_path, 12)["extensions"]) == 1


def test_extension_does_not_shorten_or_reset_a_batch(tmp_path):
    before = make_limits(tmp_path)
    with pytest.raises(ValueError):
        extend_limit(tmp_path, 3)
    assert json.loads((tmp_path / "reports/resource_limits.json").read_text()) == before


def test_twenty_four_hours_keeps_cumulative_bytes_and_twelve_hour_snapshot(tmp_path):
    make_limits(tmp_path)
    twelve = extend_limit(tmp_path, 12)
    twenty_four = extend_limit(tmp_path, 24)
    assert twenty_four["deadline_epoch"] == twelve["deadline_epoch"] + 12 * 3600
    assert twenty_four["transferred_bytes"] == twelve["transferred_bytes"]
    assert twenty_four["max_bytes"] == 20_000_000_000
    assert json.loads((tmp_path / "reports/acceptance_12h/resource_limits.json").read_text()) == twelve
