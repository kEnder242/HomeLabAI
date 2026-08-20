"""[Story 5] Real-Time Audio Streaming Memory Benchmark
=======================================================
# [FEAT-429] Foyer Disconnect Memory Reclaim Sentinel
# [FEAT-188] Resonant Memory (Bicameral Momentum)
# [FEAT-059] Real-Time PCM Audio Streaming
# [FEAT-056] MIB Memory Wipe (Neuralyzer)
Live-fire memory profile of the Foyer server's WebSocket audio uplink
(ws://127.0.0.1:8765/): streams ~60 s of simulated real-time PCM audio
# [FEAT-102] Nuclear Cache Busting
# [FEAT-063] Cache-Busting Deployment
(Float32 440 Hz sine -> Signed Int16, 4096 samples @ 16 kHz) as BINARY
frames and profiles process RSS, system swap/RAM, and (optionally) vLLM
VRAM/KV-cache allocation via pynvml + /metrics before/during/after.

Wire protocol (FEAT-feature-426 handshake auth):
    1. GET http://127.0.0.1:8765/status  ->  session_token
    2. websockets.connect(ws://127.0.0.1:8765/)  ->  consume the
       server-pushed initial status TEXT message (read/ignore)
    3. send TEXT {"type": "handshake", "lab_key": "<session_token>"}
       (a missing/invalid lab_key is refused with close code 1008)
    4. consume the TEXT status ack {"type":"status","state":"connected",...}
    5. stream BINARY frames of little-endian Signed Int16 PCM (16 kHz mono)
       paced to real time: await asyncio.sleep(chunk_size / sample_rate)

Requires an ALREADY-RUNNING Foyer server on 127.0.0.1:8765 (booted via
src/acme_lab.py). No EarNode/hearing event is required: the benchmark only
needs the socket to stay open for the stream window.

Run standalone:
    python3 src/tests/test_live_audio_memory_benchmark.py
Collected by pytest as well (pytest.ini sets asyncio_mode = auto); the
test is skipped at collection when the server is unreachable.

Report: a compact JSON line with rss_baseline_mb / rss_peak_mb /
rss_after_mb / swap_mb / ram_pct / vrma_delta_mb and a boolean `pass` =
rss_peak_mb <= RSS_CEILING_MB (env RSS_CEILING_MB, default 2000 MiB).
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import socket
import sys
import time
import urllib.request
from typing import Any, Dict, List, NamedTuple, Optional

import numpy as np
import psutil
import websockets

# ---------------------------------------------------------------------------
# sys.path shim (mirrors test_vllm_connection_resilience.py / test_triage_retrospective.py):
# insert src/ so `from infra.profile_ws_memory import ...` resolves when run
# standalone; harmless under pytest where pythonpath = . already covers src.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:  # reuse the repo's RSS sampler; degrade to inline psutil if missing
    from infra.profile_ws_memory import sample_rss

    HAVE_PROFILER = True
except ImportError:
    HAVE_PROFILER = False

    def sample_rss() -> int:  # type: ignore[no-redef]
        """Inline fallback RSS sampler (bytes) for the current process."""
        try:
            return int(psutil.Process().memory_info().rss)
        except Exception as exc:
            print(f"[bench] WARN: RSS sample failed: {exc}")
            return 0


# ---------------------------------------------------------------------------
# Config (module-level constants; bounds are env-overridable for the orchestrator)
# ---------------------------------------------------------------------------
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765
WS_URI = f"ws://{SERVER_HOST}:{SERVER_PORT}/"
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
VLLM_METRICS_URL = "http://127.0.0.1:8088/metrics"

SAMPLE_RATE = 16000  # Hz, production EarNode rate
CHUNK_SIZE = 4096  # WS chunk size used by the web binary uplink
TONE_HZ = 440.0  # simulated audio tone

DURATION_S = float(os.environ.get("BENCH_DURATION_S", "60.0"))
if not (math.isfinite(DURATION_S) and DURATION_S > 0.0):
    DURATION_S = 60.0
SAMPLE_INTERVAL_S = float(os.environ.get("BENCH_SAMPLE_INTERVAL_S", "2.0"))
SAMPLE_INTERVAL_S = SAMPLE_INTERVAL_S if math.isfinite(SAMPLE_INTERVAL_S) and SAMPLE_INTERVAL_S > 0.0 else 2.0

RSS_CEILING_MB = float(os.environ.get("RSS_CEILING_MB", "2000"))  # sane leak ceiling
TOTAL_FRAMES = int(DURATION_S * SAMPLE_RATE / CHUNK_SIZE)  # frames to reach 60 s of audio

MB = 1024 * 1024

# ---------------------------------------------------------------------------
# Optional GPU/VRAM sampling (pynvml may be absent -> non-fatal)
# ---------------------------------------------------------------------------
def _sample_vram_mb() -> Optional[float]:
    """VRAM used (MiB) on GPU 0, or None when pynvml is unavailable/failed."""
    try:
        import pynvml  # guarded: pynvml may not be installed

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return round(info.used / MB, 2)
    except Exception as exc:
        print(f"[bench] WARN: pynvml sample failed: {exc}")
        return None


def _probe_vllm_kv_tokens() -> Optional[int]:
    """Best-effort vLLM `num_cached_tokens` scrape; non-fatal on any failure."""
    try:
        with urllib.request.urlopen(VLLM_METRICS_URL, timeout=2) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        match = re.search(r"(?:^|\n)(?:vllm:)?num_cached_tokens\s+(\d+)", text)
        return int(match.group(1)) if match else None
    except Exception:
        return None


def _fetch_status_token() -> Optional[str]:
    """GET /status on the REST port and return the session_token field."""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/status", timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        token = body.get("session_token")
        return str(token) if token else None
    except Exception as exc:
        print(f"[bench] WARN: GET /status failed: {exc}")
        return None


def _foyer_reachable(timeout: float = 3.0) -> bool:
    """TCP probe of the Foyer server port (module-level skip gate)."""
    try:
        with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


# ---------------------------------------------------------------------------
# Fallback profiler (used only when infra.profile_ws_memory cannot be imported)
# ---------------------------------------------------------------------------
class _RssSample(NamedTuple):
    """Fallback sample record mirroring infra MemoryProfile's rss fields."""

    rss_bytes: int
    rss_mb: float


class _InlineProfiler:
    """Minimal BEFORE/DURING/AFTER RSS profiler mirroring WsMemoryProfiler's API."""

    def __init__(self) -> None:
        self.baseline: Optional[_RssSample] = None
        self.peak: Optional[_RssSample] = None
        self.final: Optional[_RssSample] = None

    def sample_baseline(self) -> _RssSample:
        self.baseline = self.peak = self._now()
        return self.baseline

    def sample(self) -> _RssSample:
        current = self._now()
        if self.peak is None or current.rss_bytes > self.peak.rss_bytes:
            self.peak = current
        return current

    def teardown(self) -> _RssSample:
        self.final = self._now()
        return self.final

    @staticmethod
    def _now() -> _RssSample:
        rss = sample_rss()
        return _RssSample(rss_bytes=rss, rss_mb=round(rss / MB, 2))


def _make_profiler() -> Any:
    """Return the repo WsMemoryProfiler, or the inline fallback."""
    if HAVE_PROFILER:
        from infra.profile_ws_memory import WsMemoryProfiler

        return WsMemoryProfiler(label="live-audio-bench")
    return _InlineProfiler()


async def _drain(ws: Any) -> None:
    """Best-effort drain of server-pushed TEXT messages (heartbeats/status) so the
    client receive buffer stays steady-state during the stream."""
    while True:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.05)
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            return


# ---------------------------------------------------------------------------
# Benchmark core
# ---------------------------------------------------------------------------
async def run_benchmark(
    duration_s: float = DURATION_S,
    sample_interval_s: float = SAMPLE_INTERVAL_S,
) -> Dict[str, Any]:
    """Stream simulated real-time PCM for `duration_s` and profile memory.

    Returns a JSON-serializable report; `pass` is True when the peak RSS
    stays under RSS_CEILING_MB. Never raises for network teardown; real
    stream errors are collected into the report's `error` field.
    """
    report: Dict[str, Any] = {
        "total_s": duration_s,
        "pass": False,
        "handshake_ack": False,
        "stream_complete": False,
        "error": None,
    }
    profiler = _make_profiler()
    profiler.sample_baseline()  # BEFORE connect

    swap = psutil.swap_memory()
    report["swap_mb"] = round(swap.used / MB, 2)
    report["ram_pct"] = psutil.virtual_memory().percent

    vram_before = await asyncio.to_thread(_sample_vram_mb)
    kv_before = await asyncio.to_thread(_probe_vllm_kv_tokens)
    session_token = await asyncio.to_thread(_fetch_status_token)
    if not session_token:
        print("[bench] WARN: no session_token from /status; handshake may be refused (close 1008)")

    samples: List[Dict[str, Any]] = []
    ws: Any = None
    t0 = time.monotonic()
    total_samples = 0
    frame = 0
    next_sample_at = t0
    try:
        ws = await websockets.connect(WS_URI, open_timeout=10)

        # 1. Consume the server-pushed initial status TEXT message.
        try:
            await asyncio.wait_for(ws.recv(), timeout=5)
        except (asyncio.TimeoutError, websockets.ConnectionClosed) as exc:
            print(f"[bench] note: initial status message not received ({type(exc).__name__})")

        # 2. Handshake with lab_key == session_token (required, else close 1008).
        await ws.send(json.dumps({"type": "handshake", "lab_key": session_token}))
        try:
            ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            report["handshake_ack"] = bool(ack.get("type") == "status")
            print(f"[bench] handshake ack: {json.dumps(ack)[:120]}")
        except (asyncio.TimeoutError, websockets.ConnectionClosed, json.JSONDecodeError) as exc:
            print(f"[bench] WARN: handshake ack not received ({type(exc).__name__})")

        # 3. Optional mic_state marker (server logs it; harmless).
        await ws.send(json.dumps({"type": "mic_state", "active": True}))

        # 4. Stream BINARY Signed Int16 PCM frames paced to real time.
        total_frames = int(duration_s * SAMPLE_RATE / CHUNK_SIZE)
        while frame < total_frames:
            samples_float32 = (
                np.sin(2 * np.pi * TONE_HZ * (np.arange(CHUNK_SIZE) + total_samples) / SAMPLE_RATE) * 0.9
            )
            binary = (samples_float32 * 32767).astype(np.int16).tobytes()  # Float32 -> Signed Int16
            await ws.send(binary)
            total_samples += CHUNK_SIZE
            frame += 1

            now = time.monotonic()
            if now >= next_sample_at:  # DURING sampling every sample_interval_s
                current = profiler.sample()
                swap_now = psutil.swap_memory()
                samples.append(
                    {
                        "elapsed_s": round(now - t0, 2),
                        "rss_mb": current.rss_mb,
                        "swap_mb": round(swap_now.used / MB, 2),
                        "ram_pct": psutil.virtual_memory().percent,
                    }
                )
                print(
                    f"[bench] t={now - t0:6.1f}s frame={frame}/{total_frames} "
                    f"rss={current.rss_mb:8.1f} MiB swap={swap_now.used / MB:7.1f} MiB "
                    f"ram={psutil.virtual_memory().percent:5.1f}%"
                )
                next_sample_at = now + sample_interval_s
                await _drain(ws)  # keep the receive buffer steady-state

            await asyncio.sleep(CHUNK_SIZE / SAMPLE_RATE)  # real-time pacing (~3.9 Hz frames)

        report["stream_complete"] = True
        print(f"[bench] stream finished: {frame} frames / {total_samples} samples in {time.monotonic() - t0:.1f}s")
    except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(f"[bench] WARN: stream aborted: {report['error']}")
    finally:
        if ws is not None:
            try:
                await ws.close()
            except Exception as exc:
                print(f"[bench] note: ws.close() failed: {exc}")
        profiler.teardown()  # AFTER close

    vram_after = await asyncio.to_thread(_sample_vram_mb)
    kv_after = await asyncio.to_thread(_probe_vllm_kv_tokens)

    rss_baseline_mb = float(profiler.baseline.rss_mb)
    rss_peak_mb = float(profiler.peak.rss_mb)
    rss_after_mb = float(profiler.final.rss_mb)
    report.update(
        {
            "rss_baseline_mb": rss_baseline_mb,
            "rss_peak_mb": rss_peak_mb,
            "rss_after_mb": rss_after_mb,
            "rss_leak_mb": round(rss_after_mb - rss_baseline_mb, 2),
            "stream_frames": frame,
            "n_samples": len(samples),
            "samples": samples,
            "vram_before_mb": vram_before,
            "vram_after_mb": vram_after,
            "vrma_delta_mb": (
                round(vram_after - vram_before, 2)
                if vram_before is not None and vram_after is not None
                else None
            ),
            "kv_cache_before": kv_before,
            "kv_cache_after": kv_after,
        }
    )
    report["pass"] = rss_peak_mb <= RSS_CEILING_MB
    summary = {key: value for key, value in report.items() if key != "samples"}
    print("[BENCH-REPORT] " + json.dumps(summary, default=str))
    return report


async def test_live_audio_memory_benchmark() -> bool:
    """[Story 5] Real-Time Audio Streaming Memory Benchmark (pytest-collected)."""
    report = await run_benchmark()
    assert report["pass"], (
        f"RSS peak {report['rss_peak_mb']} MiB exceeded ceiling {RSS_CEILING_MB} MiB "
        f"(baseline {report['rss_baseline_mb']} MiB, after {report['rss_after_mb']} MiB)"
    )
    return True


if __name__ == "__main__":
    if not _foyer_reachable():
        print("SKIP: Foyer server not reachable on 127.0.0.1:8765")
        sys.exit(0)
    bench_report = asyncio.run(run_benchmark())
    verdict = "PASS" if bench_report["pass"] else "FAIL"
    print(f"{verdict}: peak RSS {bench_report['rss_peak_mb']} MiB "
          f"(ceiling {RSS_CEILING_MB} MiB), leak {bench_report['rss_leak_mb']} MiB")
    sys.exit(0 if bench_report["pass"] else 1)
