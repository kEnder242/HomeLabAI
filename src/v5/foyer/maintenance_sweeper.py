"""Maintenance Sweeper Satellite (LAB-095/LAB-096/LAB-099/REF-02).

Extracted from router.py:scheduled_tasks_loop (L1437-1530).
Encapsulates CPU thermal monitoring, periodic heap garbage collection,
and TTL buffer cleaning into a testable, stateless module.
"""

from __future__ import annotations

import gc
import os
from typing import Optional


_DEFAULT_THERMAL_ZONES: list[str] = [
    "/sys/class/thermal/thermal_zone3/temp",
    "/sys/class/thermal/thermal_zone0/temp",
]


class MaintenanceSweeper:
    """Stateless maintenance utilities extracted from the foyer router loop."""

    # ------------------------------------------------------------------
    # [LAB-099] CPU Thermal Guard
    # ------------------------------------------------------------------

    @staticmethod
    def check_cpu_thermal_throttle(
        threshold_milli: int = 78_000,
        thermal_zones: Optional[list[str]] = None,
    ) -> tuple[bool, float]:
        """Read Linux sysfs thermal zones; return (exceeded, temp_celsius).

        On non-Linux hosts, missing files, or read errors the function
        degrades gracefully to ``(False, 0.0)`` — never raising.
        """
        zones = thermal_zones if thermal_zones is not None else _DEFAULT_THERMAL_ZONES
        for tz_path in zones:
            try:
                if not os.path.exists(tz_path):
                    continue
                with open(tz_path, "r") as fh:
                    t_milli = int(fh.read().strip())
                if t_milli >= threshold_milli:
                    return (True, t_milli / 1000.0)
            except (OSError, ValueError):
                continue
        return (False, 0.0)

    # ------------------------------------------------------------------
    # [LAB-096] Heap Scavenger
    # ------------------------------------------------------------------

    @staticmethod
    def run_heap_scavenger() -> int:
        """Force a full GC cycle and return the unreachable object count."""
        return gc.collect()

    # ------------------------------------------------------------------
    # [LAB-095] TTL Buffer Pruner
    # ------------------------------------------------------------------

    @staticmethod
    def prune_ttl_buffer(
        buffer_dict: dict,
        timestamp_dict: dict,
        max_age_s: float = 30.0,
        current_time: Optional[float] = None,
    ) -> list[str]:
        """Evict stale entries whose age exceeds *max_age_s*.

        Iterates over a snapshot of *timestamp_dict* so mutations are safe.
        Returns the list of purged keys.
        """
        now = current_time if current_time is not None else __import__("time").time()
        purged: list[str] = []
        for k, ts in list(timestamp_dict.items()):
            if now - ts > max_age_s:
                buffer_dict.pop(k, None)
                timestamp_dict.pop(k, None)
                purged.append(k)
        return purged
