"""[FEAT-639] Story 97.3 — Dead-Lock Reaping, VRAM Status Clean-up & Queue Hardening.

Test suite verifying:
1. Lock PID parsing and kernel PID liveness probing.
2. Dead-lock reaping logic (dead PID reap, live PID retention, age fallback).
3. LabStatus state string mapping (zero bogus 'Lab Hibernating' for offline/maintenance).
4. Training subprocess watchdog hard ceiling (60m).
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.v5.common.types import LabStatus
from src.v5.foyer.router import (
    TRAIN_HARD_TIMEOUT_S,
    communicate_with_watchdog,
    is_pid_alive,
    parse_lock_pid,
    reap_stale_maintenance_lock,
)


# ============================================================================
# 1. Lock Parsing & PID Liveness Probes
# ============================================================================


def test_parse_lock_pid_structured(tmp_path):
    """Parses standard nightly_lora_training / ignition structured lock format."""
    lock_file = tmp_path / "maintenance.lock"
    lock_file.write_text("pid=45678\ntimestamp=1791020000\nservice=nightly_lora\n")
    pid = parse_lock_pid(str(lock_file))
    assert pid == 45678


def test_parse_lock_pid_bare(tmp_path):
    """Parses bare integer PID format."""
    lock_file = tmp_path / "maintenance.lock"
    lock_file.write_text("12345\n")
    pid = parse_lock_pid(str(lock_file))
    assert pid == 12345


def test_parse_lock_pid_invalid_or_missing(tmp_path):
    """Returns None for non-existent, empty, or corrupted lock files."""
    assert parse_lock_pid(str(tmp_path / "non_existent.lock")) is None

    empty_lock = tmp_path / "empty.lock"
    empty_lock.write_text("")
    assert parse_lock_pid(str(empty_lock)) is None

    corrupted_lock = tmp_path / "corrupt.lock"
    corrupted_lock.write_text("corrupted_no_digits\n")
    assert parse_lock_pid(str(corrupted_lock)) is None


def test_is_pid_alive():
    """Current process PID is alive; astronomically high PID is dead."""
    current_pid = os.getpid()
    assert is_pid_alive(current_pid) is True

    # 4194304 is the default max PID on 64-bit Linux (PID_MAX_LIMIT)
    dead_pid = 4194300
    assert is_pid_alive(dead_pid) is False
    assert is_pid_alive(None) is False
    assert is_pid_alive("invalid") is False


# ============================================================================
# 2. Dead-Lock Reaping Scenarios
# ============================================================================


def test_reap_stale_maintenance_lock_dead_pid(tmp_path):
    """A lock with a dead PID must be reaped immediately."""
    lock_file = tmp_path / "maintenance.lock"
    dead_pid = 4194300
    lock_file.write_text(f"pid={dead_pid}\ntimestamp=1000\nservice=nightly_forge\n")

    result = reap_stale_maintenance_lock(str(lock_file))
    assert result["reaped"] is True
    assert f"dead_pid:{dead_pid}" in result["reason"]
    assert not lock_file.exists()


def test_reap_stale_maintenance_lock_live_pid(tmp_path):
    """A lock with an actively running process must NOT be reaped."""
    lock_file = tmp_path / "maintenance.lock"
    live_pid = os.getpid()
    lock_file.write_text(f"pid={live_pid}\ntimestamp=1000\nservice=active_training\n")

    result = reap_stale_maintenance_lock(str(lock_file))
    assert result["reaped"] is False
    assert f"pid_alive:{live_pid}" in result["reason"]
    assert lock_file.exists()


def test_reap_stale_maintenance_lock_no_pid_old(tmp_path):
    """A PID-less lock older than 12h must be reaped."""
    lock_file = tmp_path / "maintenance.lock"
    lock_file.write_text("stale legacy lock\n")

    # Mock file modification time to 13 hours ago
    stale_mtime = time.time() - (13 * 3600)
    os.utime(str(lock_file), (stale_mtime, stale_mtime))

    result = reap_stale_maintenance_lock(str(lock_file))
    assert result["reaped"] is True
    assert "pidless_lock_age_s:" in result["reason"]
    assert not lock_file.exists()


def test_reap_stale_maintenance_lock_no_pid_recent(tmp_path):
    """A PID-less lock created recently (<12h) must NOT be reaped."""
    lock_file = tmp_path / "maintenance.lock"
    lock_file.write_text("recent lock\n")

    result = reap_stale_maintenance_lock(str(lock_file))
    assert result["reaped"] is False
    assert "recent" in result["reason"]
    assert lock_file.exists()


# ============================================================================
# 3. LabStatus Message Mapping
# ============================================================================


def test_types_lab_status_genuine_state_messages():
    """Verify that LabStatus.to_dict() emits genuine per-state strings."""
    op_status = LabStatus(state="OPERATIONAL", timestamp=time.time())
    assert op_status.to_dict()["message"] == "Systems Nominal"

    hib_status = LabStatus(state="HIBERNATING", timestamp=time.time())
    assert hib_status.to_dict()["message"] == "Standby (Scale-to-Zero)"

    maint_status = LabStatus(state="MAINTENANCE", timestamp=time.time())
    assert maint_status.to_dict()["message"] == "Maintenance"

    off_status = LabStatus(state="OFFLINE", timestamp=time.time())
    assert off_status.to_dict()["message"] == "Lab Offline"

    unknown_status = LabStatus(state="DEGRADED", timestamp=time.time())
    assert unknown_status.to_dict()["message"] == "Lab Offline"


# ============================================================================
# 4. Training Process Watchdog Timeout
# ============================================================================


@pytest.mark.asyncio
async def test_communicate_with_watchdog_timeout():
    """Watchdog aborts and kills a process exceeding the specified timeout."""
    # Spawn a sleep subprocess that exceeds a 0.2s timeout
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time; time.sleep(5)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr, timed_out = await communicate_with_watchdog(proc, timeout_s=0.2)
    assert timed_out is True
    # Verify process terminated
    assert proc.returncode is not None
