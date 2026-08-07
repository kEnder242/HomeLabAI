"""
[Story 3.5] WebSocket PCM Streaming RSS Memory Profiler
=======================================================
psutil-based resident-set-size (RSS) harness that measures the lab-attendant
process footprint BEFORE, DURING, and AFTER a WebSocket PCM (16kHz mono
Int16) streaming session — so unbounded browser-heap growth from the
intercom mic downsampling path can be caught at the OS level.

Purpose:
    - BEFORE   : baseline RSS sampled before the WS loop/connection starts.
    - DURING   : in-loop sampler called once per received audio event;
                 records peak RSS and cumulative growth vs baseline.
    - AFTER    : teardown RSS sampled after close; if more than
                 RETAINED_BLOAT_MB (default 4 MiB) is retained past
                 baseline, a "retained/bloat" note is flagged.

Usage:
    from infra.profile_ws_memory import WsMemoryProfiler

    profiler = WsMemoryProfiler()
    profiler.sample_baseline()      # BEFORE streaming
    ...                             # WS receive loop:
    profiler.sample()               #   DURING streaming (per audio event)
    profiler.teardown()             # AFTER close
    print(profiler.report())        # -> JSON-serializable dict

CLI (primary shared venv, no new one):
    /home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3 profile_ws_memory.py \
        --pid 1234 --duration 15

Design constraints honored:
  - Class-1: only stdlib + `psutil`, both already runtime-safe in the tree.
  - Safe defaults: dead PID / failed lookup degrades to 0 bytes + warning —
    this harness never raises.
  - Stateless and read-only with respect to the WS server: no transactions,
    no writes beyond logging and the stdout report.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

import psutil

# ---------------------------------------------------------------------------
# Config (all env-overridable for test/CI)
# ---------------------------------------------------------------------------
DEFAULT_DURATION_S = float(os.environ.get("PROFILE_DURATION_S", "10"))
DEFAULT_SAMPLE_INTERVAL_S = float(os.environ.get("PROFILE_SAMPLE_INTERVAL_S", "1.0"))
RETAINED_BLOAT_MB = float(os.environ.get("PROFILE_RETAINED_BLOAT_MB", "4.0"))

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------
@dataclass
class MemoryProfile:
    """One RSS sample of the profiled process."""

    pid: int
    label: str
    rss_bytes: int
    rss_mb: float
    timestamp: float = field(default_factory=time.time)
    heap_growth_mb: Optional[float] = None  # delta vs baseline (during/teardown)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# RSS sampling (safe-default, never raises)
# ---------------------------------------------------------------------------
def sample_rss(pid: Optional[int] = None) -> int:
    """
    Return the resident set size in bytes for `pid` (None => current process).

    Degrades to 0 bytes with a warning when the process is gone or the PID
    lookup fails (NoSuchProcess / AccessDenied / ZombieProcess / OSError).
    """
    try:
        return int(psutil.Process(pid).memory_info().rss)
    except Exception as exc:
        log.warning(f"[profile_ws_memory] RSS sample failed for pid={pid}: {exc}")
        return 0


# ---------------------------------------------------------------------------
# Profiler — BEFORE / DURING / AFTER a WS PCM streaming session
# ---------------------------------------------------------------------------
class WsMemoryProfiler:
    """
    Measures the lab-attendant RSS footprint around a WebSocket PCM stream.

    Wire into the WS receive loop:

        profiler.sample_baseline()      # BEFORE: before connection/loop start
        ...                             # DURING: per audio event
        profiler.sample()
        ...                             # AFTER: after ws.close()
        profiler.teardown()
        profiler.report()               # -> JSON-serializable dict
    """

    def __init__(self, pid: Optional[int] = None, label: str = "ws-pcm-stream") -> None:
        self.pid = pid if pid is not None else os.getpid()
        self.label = label
        self.baseline: Optional[MemoryProfile] = None
        self.peak: Optional[MemoryProfile] = None
        self.final: Optional[MemoryProfile] = None
        self.samples: list[MemoryProfile] = []
        self.bloat_note: str = ""

    def sample_baseline(self) -> MemoryProfile:
        """BEFORE streaming: RSS sampled before the WS loop/connection starts."""
        self.baseline = self._record("baseline")
        self.peak = self.baseline
        log.debug(
            f"[profile_ws_memory] {self.label} baseline "
            f"{self.baseline.rss_mb} MiB (pid={self.pid})"
        )
        return self.baseline

    def sample(self) -> MemoryProfile:
        """DURING streaming: call once per PCM audio event in the receive loop."""
        current = self._record("during")
        if self.peak is None or current.rss_bytes > self.peak.rss_bytes:
            self.peak = current
        self.samples.append(current)
        return current

    def teardown(self) -> MemoryProfile:
        """AFTER streaming: RSS after close; flags retained bloat past threshold."""
        self.final = self._record("teardown")
        if self.baseline is not None:
            retained_mb = self.final.rss_mb - self.baseline.rss_mb
            self.final.heap_growth_mb = round(retained_mb, 2)
            if retained_mb > RETAINED_BLOAT_MB:
                self.bloat_note = (
                    f"retained {retained_mb:.2f} MiB past baseline "
                    f"(>{RETAINED_BLOAT_MB:.1f} MiB threshold) — retained/bloat"
                )
                log.warning(f"[profile_ws_memory] {self.label}: {self.bloat_note}")
        return self.final

    def _record(self, label: str) -> MemoryProfile:
        rss_bytes = sample_rss(self.pid)
        growth: Optional[float] = None
        if self.baseline is not None and self.baseline.rss_bytes > 0:
            growth = round((rss_bytes - self.baseline.rss_bytes) / (1024 * 1024), 2)
        return MemoryProfile(
            pid=self.pid,
            label=label,
            rss_bytes=rss_bytes,
            rss_mb=round(rss_bytes / (1024 * 1024), 2),
            heap_growth_mb=growth,
        )

    def report(self) -> Dict[str, Any]:
        """JSON-serializable annotated summary of the streaming session."""
        if self.baseline is None or self.final is None:
            return {"label": self.label, "pid": self.pid, "complete": False}
        return {
            "label": self.label,
            "pid": self.pid,
            "complete": True,
            "baseline": self.baseline.to_dict(),
            "peak": self.peak.to_dict() if self.peak else None,
            "final": self.final.to_dict(),
            "samples": [sample.to_dict() for sample in self.samples],
            "bloat_note": self.bloat_note,
        }


# ---------------------------------------------------------------------------
# Orchestration — full BEFORE / DURING / AFTER profile run
# ---------------------------------------------------------------------------
def memory_profile(
    duration: float = DEFAULT_DURATION_S,
    pid: Optional[int] = None,
    sample_interval: float = DEFAULT_SAMPLE_INTERVAL_S,
) -> Dict[str, Any]:
    """
    Run a complete RSS profile around a streaming window.

    `duration` simulates the sustained WS PCM streaming phase: `sample()` is
    driven repeatedly (DURING) until the window elapses, then teardown
    records whether RSS returned toward baseline or retained bloat.
    """
    profiler = WsMemoryProfiler(pid=pid)
    profiler.sample_baseline()  # BEFORE streaming
    deadline = time.time() + max(0.0, duration)
    while time.time() < deadline:  # DURING streaming (sustained sampling)
        profiler.sample()
        time.sleep(max(0.05, sample_interval))
    profiler.teardown()  # AFTER streaming
    return profiler.report()


run_streaming_profile = memory_profile  # importable wiring alias (live_telemetry)


# ---------------------------------------------------------------------------
# Standalone runner:
#   python3 profile_ws_memory.py [--pid N] [--duration N]
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="WebSocket PCM streaming RSS memory profiler")
    parser.add_argument("--pid", type=int, default=None, help="target process PID (default: self)")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S, help="DURING streaming window in seconds")
    args = parser.parse_args()

    result = memory_profile(duration=args.duration, pid=args.pid)
    print(f"\n[profile_ws_memory] {result['label']} pid={result['pid']} complete={result['complete']}")
    if result["complete"]:
        baseline = result["baseline"]
        peak = result["peak"]
        final = result["final"]
        print(f"  BEFORE  baseline : {baseline['rss_mb']:>8.2f} MiB  ({baseline['rss_bytes']} B)")
        print(f"  DURING  peak     : {peak['rss_mb']:>8.2f} MiB  (growth {(peak.get('heap_growth_mb') or 0.0):+.2f} MiB)")
        print(f"  AFTER   teardown : {final['rss_mb']:>8.2f} MiB  (retained {(final.get('heap_growth_mb') or 0.0):+.2f} MiB)")
        note = result["bloat_note"]
        print(f"  NOTE    {note if note else 'no retained bloat — RSS returned toward baseline'}")