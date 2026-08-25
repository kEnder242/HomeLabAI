"""Unit tests for maintenance_sweeper satellite (LAB-095/LAB-096/LAB-099/REF-02)."""

from __future__ import annotations

import gc
from pathlib import Path
from unittest.mock import patch

import pytest

from src.v5.foyer.maintenance_sweeper import MaintenanceSweeper


# ========================================================================
# 1. check_cpu_thermal_throttle
# ========================================================================


class TestCheckCpuThermalThrottle:
    """[LAB-099] CPU thermal zone thresholding with sysfs mock fallback."""

    def test_above_threshold_returns_true(self, tmp_path: Path) -> None:
        """Temp >= 78000 millidegrees triggers throttle."""
        zone = tmp_path / "thermal_zone3_temp"
        zone.write_text("82000")
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            thermal_zones=[str(zone)]
        )
        assert exceeded is True
        assert temp_c == pytest.approx(82.0, abs=0.01)

    def test_below_threshold_returns_false(self, tmp_path: Path) -> None:
        """Temp < 78000 millidegrees does not trigger throttle."""
        zone = tmp_path / "thermal_zone0_temp"
        zone.write_text("65000")
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            thermal_zones=[str(zone)]
        )
        assert exceeded is False
        assert temp_c == 0.0

    def test_exact_threshold_returns_true(self, tmp_path: Path) -> None:
        """Temp == 78000 millidegrees (exactly 78.0°C) triggers throttle."""
        zone = tmp_path / "thermal_zone3_temp"
        zone.write_text("78000")
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            thermal_zones=[str(zone)]
        )
        assert exceeded is True
        assert temp_c == pytest.approx(78.0, abs=0.01)

    def test_custom_threshold(self, tmp_path: Path) -> None:
        """Custom threshold of 85000 millidegrees."""
        zone = tmp_path / "thermal_zone3_temp"
        zone.write_text("84000")
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            threshold_milli=85_000, thermal_zones=[str(zone)]
        )
        assert exceeded is False
        assert temp_c == 0.0

    def test_missing_file_graceful_fallback(self) -> None:
        """Non-existent sysfs path returns (False, 0.0) without raising."""
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            thermal_zones=["/nonexistent/thermal_zone99/temp"]
        )
        assert exceeded is False
        assert temp_c == 0.0

    def test_empty_zone_list_returns_false(self) -> None:
        """Empty thermal zone list returns (False, 0.0)."""
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            thermal_zones=[]
        )
        assert exceeded is False
        assert temp_c == 0.0

    def test_non_linux_fallback(self) -> None:
        """On non-Linux (zones default to Linux sysfs), graceful fallback."""
        # Default zones won't exist on macOS/CI
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle()
        assert exceeded is False
        assert temp_c == 0.0

    def test_corrupt_temp_file_handled(self, tmp_path: Path) -> None:
        """Corrupt (non-numeric) temp content is caught gracefully."""
        zone = tmp_path / "thermal_zone3_temp"
        zone.write_text("not_a_number")
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            thermal_zones=[str(zone)]
        )
        assert exceeded is False
        assert temp_c == 0.0

    def test_first_zone_triggers_returns_immediately(self, tmp_path: Path) -> None:
        """If first zone exceeds threshold, returns immediately (no second read)."""
        hot_zone = tmp_path / "hot.txt"
        hot_zone.write_text("90000")
        cool_zone = tmp_path / "cool.txt"
        cool_zone.write_text("50000")
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            thermal_zones=[str(hot_zone), str(cool_zone)]
        )
        assert exceeded is True
        assert temp_c == pytest.approx(90.0, abs=0.01)

    def test_oserror_on_open_returns_false(self, tmp_path: Path) -> None:
        """If open() raises OSError, function continues to next zone."""
        # Create a path that exists as a directory (will fail on open())
        bad_zone = tmp_path / "not_a_file"
        bad_zone.mkdir()
        good_zone = tmp_path / "good.txt"
        good_zone.write_text("50000")
        exceeded, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            thermal_zones=[str(bad_zone), str(good_zone)]
        )
        assert exceeded is False
        assert temp_c == 0.0


# ========================================================================
# 2. run_heap_scavenger
# ========================================================================


class TestRunHeapScavenger:
    """[LAB-096] Heap scavenger returns integer from gc.collect()."""

    def test_returns_integer(self) -> None:
        """run_heap_scavenger() returns an int (gc.collect count)."""
        result = MaintenanceSweeper.run_heap_scavenger()
        assert isinstance(result, int)

    def test_non_negative_count(self) -> None:
        """GC count is >= 0."""
        result = MaintenanceSweeper.run_heap_scavenger()
        assert result >= 0

    def test_gc_collect_called(self) -> None:
        """Verify gc.collect() is actually invoked."""
        with patch.object(gc, "collect", return_value=42) as mock_gc:
            result = MaintenanceSweeper.run_heap_scavenger()
            mock_gc.assert_called_once()
            assert result == 42

    def test_after_creating_garbage(self) -> None:
        """Creating and discarding objects should be collectible."""
        # Create some temporary objects
        for _ in range(1000):
            _ = [i for i in range(10)]
        # Force collect — result is the count of unreachable objects
        count = MaintenanceSweeper.run_heap_scavenger()
        assert isinstance(count, int)


# ========================================================================
# 3. prune_ttl_buffer
# ========================================================================


class TestPruneTtlBuffer:
    """[LAB-095] TTL buffer pruning with expired and active keys."""

    def test_purges_expired_keys(self) -> None:
        """Keys older than max_age_s are removed from both dicts."""
        buffer = {"a": b"data_a", "b": b"data_b", "c": b"data_c"}
        timestamps = {"a": 100.0, "b": 200.0, "c": 250.0}
        purged = MaintenanceSweeper.prune_ttl_buffer(
            buffer, timestamps, max_age_s=30.0, current_time=300.0
        )
        # a: 300-100=200 > 30 → purged; b: 300-200=100 > 30 → purged; c: 300-250=50 > 30 → purged
        assert set(purged) == {"a", "b", "c"}
        assert buffer == {}
        assert timestamps == {}

    def test_keeps_active_keys(self) -> None:
        """Keys within max_age_s are preserved."""
        buffer = {"a": b"data_a", "b": b"data_b"}
        timestamps = {"a": 280.0, "b": 290.0}
        purged = MaintenanceSweeper.prune_ttl_buffer(
            buffer, timestamps, max_age_s=30.0, current_time=300.0
        )
        # a: 300-280=20 ≤ 30 → kept; b: 300-290=10 ≤ 30 → kept
        assert purged == []
        assert "a" in buffer
        assert "b" in buffer
        assert "a" in timestamps
        assert "b" in timestamps

    def test_mixed_expired_and_active(self) -> None:
        """Only expired keys are purged; active keys survive."""
        buffer = {"old": b"old_data", "fresh": b"fresh_data"}
        timestamps = {"old": 100.0, "fresh": 295.0}
        purged = MaintenanceSweeper.prune_ttl_buffer(
            buffer, timestamps, max_age_s=30.0, current_time=300.0
        )
        assert purged == ["old"]
        assert "old" not in buffer
        assert "old" not in timestamps
        assert "fresh" in buffer
        assert "fresh" in timestamps

    def test_empty_dicts(self) -> None:
        """Empty buffer and timestamp dicts return empty purged list."""
        purged = MaintenanceSweeper.prune_ttl_buffer({}, {})
        assert purged == []

    def test_safe_pop_no_keyerror(self) -> None:
        """pop(k, None) ensures no KeyError if buffer is missing the key."""
        # Timestamp exists but buffer does not
        timestamps = {"ghost": 100.0}
        purged = MaintenanceSweeper.prune_ttl_buffer(
            {}, timestamps, max_age_s=30.0, current_time=300.0
        )
        assert purged == ["ghost"]
        assert "ghost" not in timestamps

    def test_current_time_none_uses_real_time(self) -> None:
        """When current_time is None, uses time.time() internally."""
        buffer = {"a": b"data"}
        timestamps = {"a": 0.0}  # epoch — very old
        purged = MaintenanceSweeper.prune_ttl_buffer(
            buffer, timestamps, max_age_s=30.0
        )
        assert purged == ["a"]
        assert "a" not in buffer

    def test_returns_purged_keys_in_order(self) -> None:
        """Purged keys list matches the order of snapshot iteration."""
        buffer = {"z": 1, "a": 2, "m": 3}
        timestamps = {"z": 1.0, "a": 2.0, "m": 3.0}
        purged = MaintenanceSweeper.prune_ttl_buffer(
            buffer, timestamps, max_age_s=1.0, current_time=100.0
        )
        assert purged == ["z", "a", "m"]

    def test_exact_boundary_not_purged(self) -> None:
        """Key at exactly max_age_s is NOT purged (strict > comparison)."""
        buffer = {"x": b"data"}
        timestamps = {"x": 270.0}
        purged = MaintenanceSweeper.prune_ttl_buffer(
            buffer, timestamps, max_age_s=30.0, current_time=300.0
        )
        # 300 - 270 = 30, which is NOT > 30
        assert purged == []
        assert "x" in buffer

    def test_one_over_boundary_purged(self) -> None:
        """Key one second over boundary IS purged."""
        buffer = {"x": b"data"}
        timestamps = {"x": 269.9}
        purged = MaintenanceSweeper.prune_ttl_buffer(
            buffer, timestamps, max_age_s=30.0, current_time=300.0
        )
        # 300 - 269.9 = 30.1 > 30 → purged
        assert purged == ["x"]
        assert "x" not in buffer
