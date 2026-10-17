# [FEAT-619 / BKM-066] Unit Tests for Standalone Morning Accountability Watchdog
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from infra.standalone_accountability_watchdog import (
    audit_and_emit_digest,
    check_foyer_and_vram,
    check_subconscious_dreaming,
    check_gpu_power_clamp,
    check_nightly_forge_liveness,
    check_stale_locks,
)


def test_gpu_power_clamp_check():
    """Test GPU power clamp validation logic."""
    with patch("subprocess.run") as mock_run:
        # Case 1: Valid 165W
        mock_run.return_value = MagicMock(returncode=0, stdout="165.0\n")
        res = check_gpu_power_clamp()
        assert res["passed"] is True
        assert res["val"] == 165.0

        # Case 2: Exceeded 250W
        mock_run.return_value = MagicMock(returncode=0, stdout="250.0\n")
        res = check_gpu_power_clamp()
        assert res["passed"] is False


def test_stale_locks_detection(tmp_path):
    """Test detection of stale lock files."""
    lock_file = tmp_path / "nightly_forge.lock"
    lock_file.write_text("12345")

    # Set old timestamp (>30m ago)
    old_time = 1000000.0
    os.utime(lock_file, (old_time, old_time))

    with patch("infra.standalone_accountability_watchdog.FORGE_LOCK", lock_file):
        with patch("infra.standalone_accountability_watchdog.MAINTENANCE_LOCK", tmp_path / "m.lock"):
            with patch("infra.standalone_accountability_watchdog.LORA_LOCK", tmp_path / "l.lock"):
                res = check_stale_locks()
                assert res["passed"] is False
                assert "nightly_forge.lock" in res["detail"]


def test_nightly_forge_liveness_missing(tmp_path):
    """Test detection of missing nightly forge state file."""
    fake_state = tmp_path / "non_existent_state.json"
    with patch("infra.standalone_accountability_watchdog.NIGHTLY_FORGE_STATE", fake_state):
        res = check_nightly_forge_liveness()
        assert res["passed"] is False
        assert res["status"] == "MISSING"


def test_audit_and_emit_digest(tmp_path):
    """Test full decoupled audit digest compilation and emission."""
    out_dir = tmp_path / "field_notes" / "data"

    with patch("infra.standalone_accountability_watchdog.OUTPUT_DIR", out_dir), \
         patch("infra.standalone_accountability_watchdog.check_gpu_power_clamp", return_value={"name": "GPU", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_foyer_and_vram", return_value={"name": "Foyer", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_stale_locks", return_value={"name": "Locks", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_nightly_forge_liveness", return_value={"name": "Forge", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_lora_training", return_value={"name": "LoRA", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_subconscious_dreaming", return_value={"name": "Dreams", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_morning_round_table", return_value={"name": "Probe", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_swap_pressure", return_value={"name": "Swap", "passed": True, "detail": "OK", "swap_utilization_pct": 10.0, "swap_peak_mb": 100.0, "swap_current_mb": 10.0}):

        digest = audit_and_emit_digest(run_live_probe=False)
        assert digest["overall_status"] == "PASS"
        assert digest["passed_checks"] == 8
        # [Story 971] Single canonical home: digest AND ledger live only under field_notes/data
        assert (out_dir / "daily_accountability_digest.json").exists()
        assert (out_dir / "accountability_ledger.jsonl").exists()
        ledger_entry = json.loads((out_dir / "accountability_ledger.jsonl").read_text().strip())
        assert ledger_entry["overall_status"] == "PASS"
        assert ledger_entry["passed_checks"] == 8 and ledger_entry["total_checks"] == 8
        assert ledger_entry["discrepancies"] == []
        assert not (tmp_path / "www_deploy").exists()


def test_swap_telemetry(tmp_path):
    """[Story 101.12 / LAB-110] Test cgroup swap telemetry reading, fallback, and >80% threshold logic."""
    from infra.standalone_accountability_watchdog import check_swap_pressure

    # Case 1: Valid cgroup v2 paths
    peak_file = tmp_path / "memory.swap.peak"
    curr_file = tmp_path / "memory.swap.current"
    max_file = tmp_path / "memory.swap.max"

    peak_file.write_text("104857600\n")  # 100 MB in KB
    curr_file.write_text("52428800\n")   # 50 MB in KB
    max_file.write_text("209715200\n")   # 200 MB in KB (25% utilization)

    with patch("infra.standalone_accountability_watchdog.CGROUP_SWAP_PEAK", peak_file), \
         patch("infra.standalone_accountability_watchdog.CGROUP_SWAP_CURRENT", curr_file), \
         patch("infra.standalone_accountability_watchdog.CGROUP_SWAP_MAX", max_file):
        res = check_swap_pressure()
        assert res["passed"] is True
        assert res["swap_peak_mb"] == 102400.0
        assert res["swap_current_mb"] == 51200.0
        assert res["swap_utilization_pct"] == 25.0

    # Case 2: Fallback to /proc/meminfo
    meminfo_file = tmp_path / "meminfo"
    meminfo_file.write_text("SwapTotal:       1048576 kB\nSwapFree:         524288 kB\n")

    with patch("infra.standalone_accountability_watchdog.CGROUP_SWAP_PEAK", tmp_path / "missing_peak"), \
         patch("infra.standalone_accountability_watchdog.PROC_MEMINFO", meminfo_file):
        res = check_swap_pressure()
        assert res["passed"] is True
        assert res["swap_current_mb"] == 512.0
        assert res["swap_utilization_pct"] == 50.0

    # Case 3: High swap pressure (>80%) triggers warning in digest
    with patch("infra.standalone_accountability_watchdog.OUTPUT_DIR", tmp_path / "fn_data"), \
         patch("infra.standalone_accountability_watchdog.check_gpu_power_clamp", return_value={"name": "GPU", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_foyer_and_vram", return_value={"name": "Foyer", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_stale_locks", return_value={"name": "Locks", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_nightly_forge_liveness", return_value={"name": "Forge", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_lora_training", return_value={"name": "LoRA", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_subconscious_dreaming", return_value={"name": "Dreams", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_morning_round_table", return_value={"name": "Probe", "passed": True, "detail": "OK"}), \
         patch("infra.standalone_accountability_watchdog.check_swap_pressure", return_value={"name": "Swap", "passed": True, "detail": "High swap", "swap_utilization_pct": 85.0, "swap_peak_mb": 900.0, "swap_current_mb": 850.0}), \
         patch("infra.standalone_accountability_watchdog.logger.warning") as mock_warn:

        digest = audit_and_emit_digest(run_live_probe=False)
        assert digest["overall_status"] == "PASS"
        assert digest["passed_checks"] == 8
        assert mock_warn.called
        assert "Swap utilization at %.1f%%" in mock_warn.call_args[0][0]
        assert mock_warn.call_args[0][1] == 85.0


def test_subconscious_dreaming_freshness(tmp_path):
    """STORY 105.8: stale gems (>30h) fail, fresh gems (<30h) pass, empty gems fail."""
    import time

    gems_path = tmp_path / "latest_synthesis_gems.json"

    # Case 1: Fresh gems (<30h, default mtime=now) -> pass
    gems_path.write_text(json.dumps({"gems": [{"id": "g1"}, {"id": "g2"}]}))
    with patch("infra.standalone_accountability_watchdog.OUTPUT_DIR", tmp_path):
        res = check_subconscious_dreaming()
        assert res["passed"] is True
        assert res["count"] == 2

    # Case 2: Stale gems (>30h) -> fail
    old = time.time() - 110000  # ~30.5h ago
    os.utime(gems_path, (old, old))
    with patch("infra.standalone_accountability_watchdog.OUTPUT_DIR", tmp_path):
        res = check_subconscious_dreaming()
        assert res["passed"] is False
        assert "Stale" in res["detail"]

    # Case 3: Empty gems -> fail
    gems_path.write_text(json.dumps({"gems": []}))
    with patch("infra.standalone_accountability_watchdog.OUTPUT_DIR", tmp_path):
        res = check_subconscious_dreaming()
        assert res["passed"] is False
        assert res["count"] == 0
