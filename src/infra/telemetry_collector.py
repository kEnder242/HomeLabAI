"""
[FEAT-T20.2] Telemetry Collector
Scrapes NVIDIA DCGM Prometheus exporter (port 9400) for GPU silicon metrics.
Provides snapshot reads to embed in token generation traces.
Writes samples to telemetry_ledger.jsonl via atomic_io.

Usage:
    from infra.telemetry_collector import TelemetryCollector
    collector = TelemetryCollector()
    snap = collector.snapshot()  # -> TelemetrySample
"""

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER_PATH = os.path.join(LAB_DIR, "logs", "telemetry_ledger.jsonl")
DCGM_URL = os.environ.get("DCGM_URL", "http://localhost:9400/metrics")
SCRAPE_TIMEOUT = 2.0  # seconds — fast enough to not block token generation

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------
@dataclass
class TelemetrySample:
    timestamp: float = field(default_factory=time.time)
    # GPU Silicon
    gpu_power_w: float = 0.0          # DCGM_FI_DEV_POWER_USAGE
    gpu_temp_c: float = 0.0           # DCGM_FI_DEV_GPU_TEMP
    vram_used_mb: float = 0.0         # DCGM_FI_DEV_FB_USED
    vram_total_mb: float = 0.0        # DCGM_FI_DEV_FB_TOTAL
    sm_clock_mhz: float = 0.0         # DCGM_FI_DEV_SM_CLOCK
    # Token Generation (filled by cognitive_hub)
    ttft_ms: float = 0.0              # time-to-first-token
    total_tokens: int = 0
    duration_s: float = 0.0
    tokens_per_sec: float = 0.0
    # Derived Economics
    joules_per_token: float = 0.0
    tco_usd: float = 0.0              # synthetic cost at $0.10/kWh
    # Context
    node: str = ""
    request_id: str = "default"
    engine_type: str = ""             # VLLM | OLLAMA
    model: str = ""

    def enrich_economics(self) -> None:
        """Compute derived economic signals from raw silicon + token data."""
        if self.total_tokens > 0 and self.duration_s > 0:
            energy_wh = (self.gpu_power_w * self.duration_s) / 3600.0
            self.joules_per_token = (
                (self.gpu_power_w * self.duration_s) / self.total_tokens
                if self.total_tokens > 0
                else 0.0
            )
            # $0.10 per kWh → cost in USD
            self.tco_usd = energy_wh / 1000.0 * 0.10

        if self.duration_s > 0 and self.total_tokens > 0:
            self.tokens_per_sec = self.total_tokens / self.duration_s


# ---------------------------------------------------------------------------
# Prometheus Text Parser (no prometheus_client dependency)
# ---------------------------------------------------------------------------
def _parse_prometheus(text: str, metric_name: str) -> Optional[float]:
    """
    Minimal single-metric extractor from Prometheus text exposition format.
    Returns the first numeric value found for the given metric_name.
    """
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith(metric_name):
            # e.g. DCGM_FI_DEV_POWER_USAGE{...} 78.5
            parts = line.rsplit(" ", 1)
            if len(parts) == 2:
                try:
                    return float(parts[1])
                except ValueError:
                    continue
    return None


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------
class TelemetryCollector:
    """
    [FEAT-T20.2] Lightweight DCGM Prometheus scraper.
    Thread-safe for use from the token relay thread.
    """

    def __init__(self, dcgm_url: str = DCGM_URL, ledger_path: str = LEDGER_PATH):
        self.dcgm_url = dcgm_url
        self.ledger_path = ledger_path
        self._last_raw: str = ""
        self._last_fetch: float = 0.0
        self._fetch_ttl: float = 5.0  # cache raw scrape for 5s
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _fetch_raw(self) -> str:
        """Fetch raw Prometheus text, cached per TTL to reduce DCGM load."""
        now = time.time()
        if now - self._last_fetch < self._fetch_ttl and self._last_raw:
            return self._last_raw
        try:
            resp = requests.get(self.dcgm_url, timeout=SCRAPE_TIMEOUT)
            if resp.status_code == 200:
                self._last_raw = resp.text
                self._last_fetch = now
            else:
                log.warning(f"[telemetry] DCGM returned HTTP {resp.status_code}")
        except Exception as e:
            log.debug(f"[telemetry] DCGM unreachable: {e}")
        return self._last_raw

    def _get_metric(self, name: str) -> float:
        raw = self._fetch_raw()
        if not raw:
            return 0.0
        val = _parse_prometheus(raw, name)
        return val if val is not None else 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def snapshot(self, node: str = "", request_id: str = "default") -> TelemetrySample:
        """
        Synchronous GPU snapshot. Safe to call from async context via
        asyncio.to_thread() or from the telemetry relay thread.
        """
        raw = self._fetch_raw()
        sample = TelemetrySample(
            node=node,
            request_id=request_id,
            gpu_power_w=_parse_prometheus(raw, "DCGM_FI_DEV_POWER_USAGE") or 0.0,
            gpu_temp_c=_parse_prometheus(raw, "DCGM_FI_DEV_GPU_TEMP") or 0.0,
            vram_used_mb=_parse_prometheus(raw, "DCGM_FI_DEV_FB_USED") or 0.0,
            vram_total_mb=_parse_prometheus(raw, "DCGM_FI_DEV_FB_TOTAL") or 0.0,
            sm_clock_mhz=_parse_prometheus(raw, "DCGM_FI_DEV_SM_CLOCK") or 0.0,
        )
        return sample

    def write_ledger(self, sample: TelemetrySample) -> None:
        """
        Append a completed sample to telemetry_ledger.jsonl.
        Uses line-append (atomic enough for single-writer scenarios).
        """
        import json
        try:
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(asdict(sample)) + "\n")
        except Exception as e:
            log.warning(f"[telemetry] Ledger write failed: {e}")


# ---------------------------------------------------------------------------
# Singleton — shared across nodes in the same process
# ---------------------------------------------------------------------------
_collector: Optional[TelemetryCollector] = None


def get_collector() -> TelemetryCollector:
    global _collector
    if _collector is None:
        _collector = TelemetryCollector()
    return _collector
