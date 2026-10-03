# [FEAT-619 / BKM-066] Unit Tests for Standalone Morning Accountability Watchdog
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from infra.standalone_accountability_watchdog import (
    audit_and_emit_digest,
    check_foyer_and_vram,
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
         patch("infra.standalone_accountability_watchdog.check_morning_round_table", return_value={"name": "Probe", "passed": True, "detail": "OK"}):

        digest = audit_and_emit_digest(run_live_probe=False)
        assert digest["overall_status"] == "PASS"
        assert digest["passed_checks"] == 7
        # [Story 971] Single canonical home: digest AND ledger live only under field_notes/data
        assert (out_dir / "daily_accountability_digest.json").exists()
        assert (out_dir / "accountability_ledger.jsonl").exists()
        ledger_entry = json.loads((out_dir / "accountability_ledger.jsonl").read_text().strip())
        assert ledger_entry["overall_status"] == "PASS"
        assert ledger_entry["passed_checks"] == 7 and ledger_entry["total_checks"] == 7
        assert ledger_entry["discrepancies"] == []
        assert not (tmp_path / "www_deploy").exists()
