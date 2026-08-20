"""
[Story 3] Live Telemetry Collector & Prometheus Harvester
==========================================================
Lightweight, synchronous operational benchmark collector that fuses three
sources into a single `LiveMetrics` struct for the IgnitionManager vitals loop:

    1. DCGM Prometheus exporter      http://127.0.0.1:9400/metrics
         - live VRAM usage  (DCGM_FI_DEV_FB_USED)
         - VRAM total       (DCGM_FI_DEV_FB_TOTAL)
         - GPU power draw   (DCGM_FI_DEV_POWER_USAGE)
    2. Foyer (Lab Attendant)          http://127.0.0.1:8765/status
         - connected WS clients (Round Table turn activity)
         - active LoRA adapter name (Foyer status / vLLM model list)
    3. Local host kernel              psutil.swap_memory()
         - host swap usage (used / total / percent)

Intended wiring (manager.py -> update_status_file / vitals loop):

    from infra.live_telemetry import merge_live_benchmarks
    ...
    def update_status_file(self):
        payload = self.status.to_dict()
        merge_live_benchmarks(payload)          # injects live_telemetry block
        with open(STATUS_JSON, "w") as f:
            json.dump(payload, f, indent=2)

`merge_live_benchmarks` mutates the manager's own payload in-place BEFORE the
single status.json write, so there is no last-writer-wins race with the 30s
vitals loop. `record_live_benchmarks()` is the standalone merge-write variant
(reads current status.json, merges, atomic write) for use outside the loop.

Design constraints honored:
  - Class-1: only `requests` + `psutil`, both already runtime-safe in the tree.
  - Read-only HTTP, short timeouts, never blocks the loop.
  - Every endpoint failure degrades to a safe default (0 / None), never raises.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

import psutil
import requests

try:
    from infra.atomic_io import atomic_write_json  # atomic .tmp + os.replace
    from infra.telemetry_collector import _parse_prometheus  # shared text parser
except Exception:  # pragma: no cover - allow standalone execution outside package
    atomic_write_json = None  # type: ignore[assignment]
    _parse_prometheus = None  # type: ignore[assignment]

log = logging.getLogger("live_telemetry")

# ---------------------------------------------------------------------------
# Config (all env-overridable for test/CI)
# ---------------------------------------------------------------------------
DCGM_URL = os.environ.get("DCGM_URL", "http://127.0.0.1:9400/metrics")
FOYER_STATUS_URL = os.environ.get("FOYER_STATUS_URL", "http://127.0.0.1:8765/status")
VLLM_MODELS_URL = os.environ.get("VLLM_MODELS_URL", "http://127.0.0.1:8088/v1/models")
BASE_MODEL_IDS = {"unified-base"}  # vLLM adapter discovery excludes these
FETCH_TIMEOUT = 2.0  # seconds — Silicone-friendly, never blocks the loop

# Canonical status document produced by the IgnitionManager/StatusModel.
_DEFAULT_STATUS_JSON = os.path.join(
    os.path.expanduser("~/Dev_Lab/Portfolio_Dev"), "field_notes", "data", "status.json"
)
STATUS_JSON = os.environ.get("LAB_STATUS_JSON", _DEFAULT_STATUS_JSON)


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------
@dataclass
class LiveMetrics:
    """Snapshot of operational silicon benchmarks for one Round Table turn."""

    timestamp: float = field(default_factory=time.time)

    # DCGM Prometheus (:9400)
    vram_used_mb: float = 0.0      # DCGM_FI_DEV_FB_USED   (MiB)
    vram_total_mb: float = 0.0     # DCGM_FI_DEV_FB_TOTAL  (MiB)
    vram_pct: float = 0.0          # derived used/total*100
    gpu_power_w: float = 0.0       # DCGM_FI_DEV_POWER_USAGE (Watts)

    # Foyer (:8765)
    connected_clients: int = 0     # active WS clients (Round Table turn activity)
    round_table_active: bool = False
    active_lora: Optional[str] = None   # active LoRA adapter name (else None=BASE)

    # Local host (psutil)
    swap_used_mb: float = 0.0
    swap_total_mb: float = 0.0
    swap_pct: float = 0.0

    # Connectivity / sanity flags
    dcgm_online: bool = False
    foyer_online: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def enrich(self) -> None:
        """Derive cross-field metrics after the struct is populated."""
        if self.vram_total_mb > 0:
            self.vram_pct = round((self.vram_used_mb / self.vram_total_mb) * 100, 1)


# ---------------------------------------------------------------------------
# Prometheus scalar parser (mirrors telemetry_collector, no extra dep)
# ---------------------------------------------------------------------------
def _parse_scalar(text: str, metric_name: str) -> Optional[float]:
    """
    Minimal single-metric extractor from Prometheus text exposition format.
    Returns the first numeric value whose metric line begins with metric_name.
    """
    if _parse_prometheus is not None:
        return _parse_prometheus(text, metric_name)
# [FEAT-261] Traceable Awakening (Mandatory Reasoning)
    # Local fallback if telemetry_collector is unavailable for some reason.
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith(metric_name):
            parts = line.rsplit(" ", 1)
            if len(parts) == 2:
                try:
                    return float(parts[1])
                except ValueError:
                    continue
    return None


# ---------------------------------------------------------------------------
# Collector — one per process (thread-safe for the vitals loop)
# ---------------------------------------------------------------------------
class LiveTelemetryCollector:
    """
    Pulls a discrete snapshot of live operational benchmarks.

    Safe to call from the IgnitionManager vitals loop / any turn boundary.
    Every sub-read is wrapped so a single dead endpoint never breaks the
    whole snapshot — host swap always survives even if both HTTP sinks are down.
    """

    def __init__(
        self,
        dcgm_url: str = DCGM_URL,
        foyer_url: str = FOYER_STATUS_URL,
        vllm_url: str = VLLM_MODELS_URL,
        status_json: str = STATUS_JSON,
        timeout: float = FETCH_TIMEOUT,
    ) -> None:
        self.dcgm_url = dcgm_url
        self.foyer_url = foyer_url
        self.vllm_url = vllm_url
        self.status_json = status_json
        self.timeout = timeout

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _fetch_text(self, url: str) -> Optional[str]:
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.text
            log.debug(f"[live_telemetry] {url} -> HTTP {resp.status_code}")
        except Exception as exc:
            log.debug(f"[live_telemetry] {url} unreachable: {exc}")
        return None

    def _fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        text = self._fetch_text(url)
        if not text:
            return None
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Source scrapers
    # ------------------------------------------------------------------
    def _scrape_dcgm(self) -> Dict[str, float]:
        raw = self._fetch_text(self.dcgm_url) or ""
        if not raw:
            return {"vram_used_mb": 0.0, "vram_total_mb": 0.0, "gpu_power_w": 0.0}
        used = _parse_scalar(raw, "DCGM_FI_DEV_FB_USED") or 0.0
        # Some exporters expose TOTAL; most expose only USED + FREE -> sum them.
        total = _parse_scalar(raw, "DCGM_FI_DEV_FB_TOTAL")
        if total is None:
            free = _parse_scalar(raw, "DCGM_FI_DEV_FB_FREE") or 0.0
            total = used + free
        return {
            "vram_used_mb": used,
            "vram_total_mb": total,
            "gpu_power_w": _parse_scalar(raw, "DCGM_FI_DEV_POWER_USAGE") or 0.0,
        }

    def _scrape_foyer(self) -> Dict[str, Any]:
        data = self._fetch_json(self.foyer_url) or {}
        clients = int(data.get("connected_clients", 0) or 0)
        # Round Table is active when WS clients are connected to the Foyer.
        round_table_active = bool(clients) or bool(
            data.get("round_table_lock_exists", False)
        )
        return {
            "connected_clients": clients,
            "round_table_active": round_table_active,
            "data": data,
        }

    @staticmethod
    def _vllm_adapters(data: Dict[str, Any]) -> list[str]:
        """Extract candidate LoRA adapter names from a vLLM /v1/models reply."""
        adapters: list[str] = []
        for model in (data.get("data") or []):
            ident = (model.get("id") or "").strip()
            if not ident:
                continue
            # vLLM lists loaded adapters as ``<base/model>/<lora>`` or separate IDs.
            short = ident.rsplit("/", 1)[-1]
            if short in BASE_MODEL_IDS:
                continue
            adapters.append(short)
        return adapters

    def _resolve_active_lora(self, foyer_data: Dict[str, Any]) -> Optional[str]:
        """
        Determine the active LoRA adapter name.

        Resolution order (best-effort, never raises):
          1. Explicit ``active_lora`` / ``lora`` / ``adapter`` keys in Foyer status.
          2. nested ``logical.persona`` or ``mode`` from the Foyer status dict.
          3. vLLM /v1/models loaded-adapter list at :8088 (excl. unified base).
        Returns None when no adapter is identifiable (i.e. BASE model resident).
        """
        # (1) explicit adapter keys — Foyer may expose them in status.
        for key in ("active_lora", "active_adapter", "lora", "adapter"):
            val = foyer_data.get(key) or (foyer_data.get("logical") or {}).get(key)
            sign = (str(val).strip() if val else "")
            if sign and sign.lower() not in ("base", "none", "-", "0", "null"):
                return sign

        # (2) logical persona as a proxy for the resident LoRA
        persona = ((foyer_data.get("logical") or {}).get("persona") or "").strip()
        if persona and persona.lower() != "the shadow":
            return persona

        # (3) vLLM adoptable list
        try:
            vllm = self._fetch_json(self.vllm_url) or {}
            adapters = self._vllm_adapters(vllm)
            if adapters:
                return adapters[0]
        except Exception:
            pass
        return None

    def _scrape_swap(self) -> Dict[str, float]:
        try:
            swap = psutil.swap_memory()
        except Exception as exc:
            log.debug(f"[live_telemetry] swap_memory failed: {exc}")
            return {"swap_used_mb": 0.0, "swap_total_mb": 0.0, "swap_pct": 0.0}
        return {
            "swap_used_mb": round(swap.used / (1024**2), 1) if swap.used else 0.0,
            "swap_total_mb": round(swap.total / (1024**2), 1) if swap.total else 0.0,
            "swap_pct": float(swap.percent or 0.0),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def snapshot(self) -> LiveMetrics:
        """Collect ONE combined live operational benchmark struct."""
        gpu = self._scrape_dcgm()
        foyer = self._scrape_foyer()
        swap = self._scrape_swap()

        sample = LiveMetrics(
            vram_used_mb=gpu["vram_used_mb"],
            vram_total_mb=gpu["vram_total_mb"],
            gpu_power_w=gpu["gpu_power_w"],
            connected_clients=foyer["connected_clients"],
            round_table_active=foyer["round_table_active"],
            active_lora=self._resolve_active_lora(foyer.get("data", {})),
            swap_used_mb=swap["swap_used_mb"],
            swap_total_mb=swap["swap_total_mb"],
            swap_pct=swap["swap_pct"],
            dcgm_online=bool(gpu["vram_used_mb"] or gpu["gpu_power_w"]),
            foyer_online=bool(foyer.get("data")),
        )
        sample.enrich()
        return sample

    def write_record(self, sample: LiveMetrics) -> None:
        """
        Merge a live snapshot into status.json under the ``live_telemetry``
        block (atomic .tmp + os.replace). Reads first, merges, then writes, so
        the manager's existing keys (vram, vitals, nodes, ...) are preserved.
        """
        try:
            existing: Dict[str, Any] = {}
            if os.path.exists(self.status_json):
                with open(self.status_json, "r") as f:
                    parsed = json.load(f)
                    if isinstance(parsed, dict):
                        existing = parsed
            merged = dict(existing)
            merged["live_telemetry"] = sample.to_dict()

            if atomic_write_json is not None:
                atomic_write_json(self.status_json, merged)
            else:  # fallback atomic via temp+replace
                _atomic_fallback_write(self.status_json, merged)
            log.debug(f"[live_telemetry] recorded snapshot -> {self.status_json}")
        except Exception as exc:
            log.warning(f"[live_telemetry] status write failed: {exc}")


def _atomic_fallback_write(path: str, payload: Dict[str, Any]) -> None:
    """Class-1 fallback atomic write (.tmp + os.replace) for standalone use."""
    import tempfile

    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Convenience entry points (for the manager's vitals loop)
# ---------------------------------------------------------------------------
def merge_live_benchmarks(
    payload: Dict[str, Any], collector: Optional[LiveTelemetryCollector] = None
) -> Dict[str, Any]:
    """
    Inject a fresh live benchmark snapshot into an existing status payload
    under the ``live_telemetry`` key (in-place). This is the race-free wiring
    for the manager vitals loop: call it on ``status.to_dict()`` BEFORE the
    manager writes status.json. Returns the same (mutated) dict.
    """
    col = collector or get_collector()
    payload["live_telemetry"] = col.snapshot().to_dict()
    return payload


def record_live_benchmarks(
    collector: Optional[LiveTelemetryCollector] = None,
) -> Dict[str, Any]:
    """
    One-shot: snapshot live silicon => write eventually to status.json.

    Standalone variant (reads status.json, merges, atomic write) for use
    outside the manager's own write path.
    """
    col = collector or get_collector()
    sample = col.snapshot()
    col.write_record(sample)
    return sample.to_dict()


_collector: Optional[LiveTelemetryCollector] = None


def get_collector() -> LiveTelemetryCollector:
    """Idempotent singleton shared by all callers in the process."""
    global _collector
    if _collector is None:
        _collector = LiveTelemetryCollector()
    return _collector


# ---------------------------------------------------------------------------
# Standalone smoke runner: python3 src/infra/live_telemetry.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    snap = record_live_benchmarks()
    print(json.dumps(snap, indent=2))