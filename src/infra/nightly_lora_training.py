#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [FEAT-160] / [FEAT-213] / [Story 83.7] Discrete Multi-LoRA Nightly Training Pipeline
"""
[Story 83.7] Discrete Multi-LoRA Nightly Training Pipeline.

Refactors the training stage of the incumbent ``nightly_forge.py`` orchestrator
into a clean, discrete multi-adapter pipeline. Sequentially trains one LoRA
adapter per curriculum target, saving each into
``/speedy/models/adapters/<adapter_name>``:

    ADAPTER_TARGETS = ['cli_voice_v1', 'lab_history_v1', 'triage_v1', 'reviewer_v1']

Isolation & memory guarantees:
  1. Every adapter is trained in its OWN ``train_expert.py`` subprocess, so the
     CUDA context is fully destroyed between passes (primary leak guard).
  2. The parent process additionally enforces ``torch.cuda.empty_cache()`` +
     ``gc.collect()`` between passes (secondary fragmentation guard).
  3. A VRAM drain verification gate MUST pass before each adapter training run
     ("non-zero VRAM draining verification").

Execution Flow:
  1. Acquire the nightly mutex (defer to a recent winner unless --force).
  2. Pre-flight GPU power limit check [LAB-109].
  3. Quiesce Foyer / vLLM to evict resident models and reclaim VRAM.
  4. For each adapter: verify VRAM drained -> train in isolated subprocess.
  5. Re-ignite Foyer / vLLM to OPERATIONAL.

CLI:
    PYTHONPATH=HomeLabAI/src python3 -m infra.nightly_lora_training \
        [--adapters cli_voice_v1 triage_v1] [--steps N] [--force] [--list]

Emits exactly one structured JSON line on stdout and exits 0 on success:
    {"adapters_trained": [...], "status": "SUCCESS", "duration_s": 123.4}
"""

import argparse
import datetime
import fcntl
import gc
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:  # [Story 83.7 Anchor 1] torch is required for the CUDA purge guard; degrade gracefully.
    import torch
except ImportError:  # pragma: no cover - non-GPU / stripped environment
    torch = None  # type: ignore[assignment]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [NIGHTLY LORA] %(message)s",
)
logger = logging.getLogger("nightly_lora_training")

# --- [Story 83.7 Anchor 2] Path discovery anchored on __file__ -----------------
BASE_DIR = Path(__file__).resolve().parent          # HomeLabAI/src/infra
SRC_DIR = BASE_DIR.parent                            # HomeLabAI/src
HOMELAB_DIR = SRC_DIR.parent                         # HomeLabAI
LAB_ROOT = HOMELAB_DIR.parent                        # Dev_Lab
CONFIG_PATH = HOMELAB_DIR / "config" / "infrastructure.json"
EXPERTISE_DIR = SRC_DIR / "forge" / "expertise"
TRAIN_EXPERT_SCRIPT = SRC_DIR / "forge" / "train_expert.py"
BUILD_DATASETS_SCRIPT = SRC_DIR / "forge" / "build_lora_datasets.py"
VENV_PYTHON = HOMELAB_DIR / ".venv" / "bin" / "python3"
STEP_LOG_PATH = Path("/tmp/nightly_lora_training_step.log")

# --- [Story 83.7 Anchor 3] Exact adapter signature -----------------------------
ADAPTER_TARGETS = ['cli_voice_v1', 'lab_history_v1', 'triage_v1', 'reviewer_v1']

# Default curriculum per adapter (override via infrastructure.json -> forge.adapter_datasets).
ADAPTER_DATASET_MAP = {
    "cli_voice_v1": "cli_voice_training.jsonl",
    "lab_history_v1": "lab_history_training.jsonl",
    "triage_v1": "lab_sentinel_training.jsonl",
    "reviewer_v1": "master_forge_curriculum.jsonl",
}
FALLBACK_DATASET = "master_forge_curriculum.jsonl"

DEFAULT_ADAPTER_BASE_DIR = "/speedy/models/adapters"
DEFAULT_VRAM_THRESHOLD_MB = 1500
DEFAULT_STEPS = 150
DEFAULT_PACING_DELAY_S = 5.0
DEFAULT_FOYER_URL = "http://localhost:8765"
VRAM_DRAIN_TIMEOUT_S = 30

LOCK_PATH = HOMELAB_DIR / "run" / "nightly_lora_training.lock"
STATE_PATH = HOMELAB_DIR / "run" / "nightly_lora_training_state.json"
MAINTENANCE_LOCK_PATH = HOMELAB_DIR / "run" / "maintenance.lock"

try:  # Preserve Neural Pager milestone broadcasting (mirrors nightly_forge).
    from infra.pager_relay import trigger_pager
except ImportError:
    try:
        from src.infra.pager_relay import trigger_pager
    except ImportError:
        def trigger_pager(message, severity="INFO", source="System"):
            pass


# ----------------------------------------------------------------------------- #
# Configuration
# ----------------------------------------------------------------------------- #
def load_config() -> dict:
    """Load infrastructure.json as the single source of truth ({} on failure)."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r") as fh:
                return json.load(fh)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"[CONFIG] Could not parse {CONFIG_PATH}: {exc}")
    return {}


CFG = load_config()
FORGE_CFG = CFG.get("forge", {})
ADAPTER_BASE_DIR = str(FORGE_CFG.get("adapter_base_dir", DEFAULT_ADAPTER_BASE_DIR))
VRAM_THRESHOLD_MB = int(FORGE_CFG.get("vram_eviction_threshold_mb", DEFAULT_VRAM_THRESHOLD_MB))
DEFAULT_STEPS = int(FORGE_CFG.get("default_steps", DEFAULT_STEPS))
DEFAULT_PACING_DELAY_S = float(FORGE_CFG.get("pacing_delay_sec", DEFAULT_PACING_DELAY_S))
FOYER_URL = str(CFG.get("foyer_url", DEFAULT_FOYER_URL)).rstrip("/")
ADAPTER_STEPS = FORGE_CFG.get("adapter_steps", {}) or {}

# Merge config-level dataset overrides (name -> filename|path).
ADAPTER_DATASETS = dict(ADAPTER_DATASET_MAP)
for _name, _rel in (FORGE_CFG.get("adapter_datasets", {}) or {}).items():
    ADAPTER_DATASETS[_name] = _rel


# ----------------------------------------------------------------------------- #
# Observability
# ----------------------------------------------------------------------------- #
def write_step_log(step_name: str, details: str = "", severity: str = "INFO") -> None:
    """[BKM-014] Append an atomic step marker and broadcast milestones to the pager."""
    timestamp = datetime.datetime.now().isoformat()
    try:
        with open(STEP_LOG_PATH, "a") as fh:
            fh.write(f"[{timestamp}] [{step_name}] {details}\n")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Failed to write step log: {exc}")

    milestones = {
        "ADAPTER_TRAIN_START": "Discrete Multi-LoRA Pipeline: adapter training pass started",
        "ADAPTER_TRAIN_COMPLETE": "Discrete Multi-LoRA Pipeline: adapter trained successfully",
        "ADAPTER_TRAIN_FAILED": f"Discrete Multi-LoRA Pipeline: adapter training failed ({details})",
        "PIPELINE_COMPLETE": "Discrete Multi-LoRA Pipeline completed successfully",
    }
    if step_name in milestones:
        sev = "WARNING" if ("FAIL" in step_name or "ERROR" in step_name) else severity
        trigger_pager(milestones[step_name], severity=sev, source="Nightly LoRA")


def _post(path: str, payload: dict | None = None, timeout: float = 10.0) -> bool:
    """Fire-and-forget JSON POST to the Foyer daemon (stdlib only, Class 1)."""
    url = f"{FOYER_URL}{path}"
    data = json.dumps(payload if payload is not None else {}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except Exception as exc:
        logger.warning(f"[FOYER] POST {path} unreachable: {exc}")
        return False


# ----------------------------------------------------------------------------- #
# Hardware / VRAM probing
# ----------------------------------------------------------------------------- #
def get_vram_usage() -> int | None:
    """Return used VRAM in MB, or None when nvidia-smi is unavailable."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode == 0:
            lines = [ln.strip() for ln in res.stdout.strip().splitlines() if ln.strip()]
            if lines:
                return int(float(lines[0]))
    except Exception:
        pass
    return None


def wait_for_vram_drain(
    timeout_s: int = VRAM_DRAIN_TIMEOUT_S,
    threshold_mb: int = VRAM_THRESHOLD_MB,
    baseline_mb: int | None = None,
) -> bool:
    """
    [Story 83.7 Anchor 3] Require non-zero VRAM draining verification.

    Polls until used VRAM drops below ``threshold_mb``. When a ``baseline_mb`` is
    supplied, the confirmed drain delta is logged. Returns True once drained, or
    when the host exposes no GPU telemetry (cannot verify -> non-fatal).
    """
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        used = get_vram_usage()
        if used is None:
            logger.warning("[VRAM] nvidia-smi unavailable; skipping drain verification (non-GPU host).")
            return True
        if used < threshold_mb:
            drained_delta = (baseline_mb - used) if baseline_mb is not None else None
            detail = f"used={used}MB threshold={threshold_mb}MB"
            if drained_delta is not None:
                detail += f" drained_delta={drained_delta}MB"
                if drained_delta <= 0:
                    logger.warning(f"[VRAM] No observed drain vs baseline ({baseline_mb}MB -> {used}MB); already evicted.")
            logger.info(f"[VRAM] Drain verified: {detail}")
            write_step_log("VRAM_DRAIN_VERIFIED", detail)
            return True
        time.sleep(2)

    used = get_vram_usage()
    logger.critical(f"[VRAM] Drain TIMEOUT: {used}MB still allocated (>= {threshold_mb}MB).")
    write_step_log("VRAM_DRAIN_FAILED", f"used={used}MB threshold={threshold_mb}MB")
    return False


def verify_gpu_power_limit(max_limit_watts: int = 170) -> bool:
    """[LAB-109] Pre-flight GPU power-limit check; clamp to 165W when able."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.limit", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode != 0:
            logger.warning("[LAB-109] nvidia-smi power query failed; skipping power limit check.")
            return True
        lines = [ln.strip() for ln in res.stdout.strip().splitlines() if ln.strip()]
        if not lines:
            logger.warning("[LAB-109] No GPU detected; skipping power limit check.")
            return True
        current_limit = float(lines[0])
        logger.info(f"[LAB-109] GPU power limit: {current_limit}W (max {max_limit_watts}W)")
        if current_limit <= max_limit_watts:
            return True
        logger.warning(f"[LAB-109] Power limit {current_limit}W exceeds {max_limit_watts}W; clamping to 165W...")
        write_step_log("GPU_POWER_CAP_WARNING", f"current={current_limit}W exceeds {max_limit_watts}W")
        clamp = subprocess.run(["sudo", "nvidia-smi", "-pl", "165"], capture_output=True, text=True, timeout=10)
        if clamp.returncode == 0:
            logger.info("[LAB-109] GPU power limit clamped to 165W.")
            write_step_log("GPU_POWER_CAP_APPLIED", "clamped to 165W")
            return True
        logger.warning(f"[LAB-109] Failed to clamp power limit: {clamp.stderr.strip()[:200]}")
        write_step_log("GPU_POWER_CAP_FAILED", clamp.stderr.strip()[:200])
        return False
    except Exception as exc:
        logger.warning(f"[LAB-109] Power limit verification error: {exc}")
        return True


# ----------------------------------------------------------------------------- #
# Foyer quiesce / re-ignite  ([FEAT-213] VRAM handover)
# ----------------------------------------------------------------------------- #
def quiesce_vllm() -> bool:
    """Evict resident models and drain VRAM for exclusive training use."""
    baseline_mb = get_vram_usage()
    logger.info(f"[FEAT-213] Quiescing Foyer / vLLM for VRAM handover (baseline={baseline_mb}MB)...")
    write_step_log("QUIESCE_START", f"baseline={baseline_mb}MB")

    try:
        MAINTENANCE_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MAINTENANCE_LOCK_PATH, "w") as fh:
            fh.write(f"pid={os.getpid()}\ntimestamp={time.time()}\nservice=nightly_lora_training\n")
    except Exception as exc:
        logger.warning(f"[MAINTENANCE] Failed to write lockfile: {exc}")

    _post("/release_nodes")
    _post("/sleep")
    _post("/shutdown")
    _post("/status_update", {"state": "SHUTDOWN"})

    t0 = time.time()
    while time.time() - t0 < 30:
        used = get_vram_usage()
        if used is None or used < VRAM_THRESHOLD_MB:
            logger.info(f"[FEAT-213] VRAM eviction confirmed ({used}MB < {VRAM_THRESHOLD_MB}MB).")
            write_step_log("QUIESCE_OK", f"used={used}MB")
            return True

        if time.time() - t0 > 5:  # Targeted eviction if the daemon is unresponsive.
            logger.info(f"[FEAT-213] VRAM still held ({used}MB); enforcing vLLM process eviction...")
            _evict_vllm_processes()
        time.sleep(2)

    used = get_vram_usage()
    logger.critical(f"[FEAT-213] VRAM eviction timed out! Current usage: {used}MB.")
    write_step_log("QUIESCE_FAILED", f"used={used}MB")
    return False


def _evict_vllm_processes() -> None:
    """Force-evict residual vLLM processes holding VRAM."""
    try:
        pid_file = HOMELAB_DIR / "run" / "vllm.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                subprocess.run(["kill", "-9", str(pid)], check=False)
                pid_file.unlink(missing_ok=True)
            except Exception:
                pass
        subprocess.run(["pkill", "-9", "-f", "vllm.entrypoints.openai.api_server"], check=False)
        subprocess.run(["pkill", "-9", "-f", "VLLM::EngineCore"], check=False)
    except Exception as exc:
        logger.warning(f"[FEAT-213] Process eviction warning: {exc}")


def re_ignite_vllm() -> bool:
    """Restore Foyer to OPERATIONAL and release the maintenance lock."""
    logger.info("[FEAT-213] Re-igniting Foyer state to OPERATIONAL...")
    write_step_log("RE_IGNITE_START")
    try:
        if MAINTENANCE_LOCK_PATH.exists():
            MAINTENANCE_LOCK_PATH.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning(f"[MAINTENANCE] Error removing lockfile: {exc}")

    woke = _post("/wake")
    operational = _post("/status_update", {"state": "OPERATIONAL"})
    if woke or operational:
        logger.info("[FEAT-213] Foyer state restored to OPERATIONAL.")
        write_step_log("RE_IGNITE_OK")
        return True
    write_step_log("RE_IGNITE_END", "Foyer unreachable")
    return False


# ----------------------------------------------------------------------------- #
# CUDA memory hygiene
# ----------------------------------------------------------------------------- #
def purge_cuda_memory() -> None:
    """
    [Story 83.7 Anchor 3] Secondary leak guard between isolated subprocess passes.

    Subprocess isolation already tears down the CUDA context; this additionally
    flushes the Python GC and the parent-side CUDA caching allocator.
    """
    collected = gc.collect()
    freed = False
    if torch is not None and getattr(torch, "cuda", None) is not None:
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                freed = True
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"[CUDA] empty_cache warning: {exc}")
    logger.info(f"[CUDA] purge_cuda_memory: gc_collected={collected} cache_cleared={freed}")


# ----------------------------------------------------------------------------- #
# Dataset resolution
# ----------------------------------------------------------------------------- #
def _resolve_dataset_path(value: str) -> Path:
    """Resolve a dataset reference as an absolute path or an expertise-relative name."""
    p = Path(value)
    return p if p.is_absolute() else (EXPERTISE_DIR / value)


def dataset_for_adapter(adapter: str) -> Path:
    """Return the curriculum path for an adapter, falling back to the master curriculum."""
    candidate = _resolve_dataset_path(ADAPTER_DATASETS.get(adapter, FALLBACK_DATASET))
    if candidate.exists() and candidate.stat().st_size > 0:
        return candidate
    fallback = EXPERTISE_DIR / FALLBACK_DATASET
    logger.warning(f"[DATASET] '{adapter}' dataset {candidate} unavailable; using {fallback}.")
    return fallback


def ensure_datasets(force: bool = False) -> None:
    """[Story 864] Auto-build the dataset foundation when the master curriculum is missing.

    ``force=True`` bypasses the fallback-existence shortcut so the dataset builder
    always reruns (e.g. after curriculum composition changes), mirroring the
    ``--force`` CLI semantics that already bypass the 12-hour debounce gate.
    """
    fallback = EXPERTISE_DIR / FALLBACK_DATASET
    if not force and fallback.exists() and fallback.stat().st_size > 0:
        return
    reason = "Force-rebuild requested" if force else "Master curriculum missing"
    logger.info(f"[DATASET] {reason}; auto-building via build_lora_datasets.py...")
    py_bin = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    if not BUILD_DATASETS_SCRIPT.exists():
        logger.warning(f"[DATASET] {BUILD_DATASETS_SCRIPT} not found; cannot auto-build.")
        return
    try:
        subprocess.run([str(py_bin), str(BUILD_DATASETS_SCRIPT)], check=True, timeout=120)
    except Exception as exc:
        logger.warning(f"[DATASET] Auto-build warning: {exc}")


# ----------------------------------------------------------------------------- #
# Adapter training (isolated subprocess)
# ----------------------------------------------------------------------------- #
def _trainer_env() -> dict:
    """Environment for train_expert.py, preloading the venv CUDA 13 runtime libs."""
    env = os.environ.copy()
    cu13_dir = HOMELAB_DIR / ".venv" / "lib" / "python3.12" / "site-packages" / "nvidia" / "cu13" / "lib"
    if cu13_dir.exists():
        env["LD_LIBRARY_PATH"] = f"{cu13_dir}:{env.get('LD_LIBRARY_PATH', '')}"
    return env


def run_adapter_training(adapter: str, dataset: Path, steps: int, pacing_delay: float) -> bool:
    """
    Train a single adapter in an ISOLATED subprocess (primary CUDA leak guard).

    The child process owns its own CUDA context; on exit the context is destroyed
    and VRAM is returned to the driver before the next adapter begins.
    """
    output_dir = Path(ADAPTER_BASE_DIR) / adapter
    py_bin = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    cmd = [
        str(py_bin), str(TRAIN_EXPERT_SCRIPT),
        "--dataset", str(dataset),
        "--output", str(output_dir),
        "--steps", str(steps),
        "--pacing-delay", str(pacing_delay),
    ]
    write_step_log("ADAPTER_TRAIN_START", f"adapter={adapter} dataset={dataset.name} steps={steps}")
    logger.info(f"[TRAIN] Adapter '{adapter}' -> {output_dir} :: {' '.join(cmd)}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, env=_trainer_env())
    except Exception as exc:
        logger.error(f"[TRAIN] Adapter '{adapter}' subprocess error: {exc}")
        write_step_log("ADAPTER_TRAIN_FAILED", f"adapter={adapter} error={exc}")
        return False

    if res.returncode == 0:
        logger.info(f"[TRAIN] Adapter '{adapter}' trained successfully (returncode=0).")
        write_step_log("ADAPTER_TRAIN_COMPLETE", f"adapter={adapter}")
        return True

    logger.error(f"[TRAIN] Adapter '{adapter}' failed (code {res.returncode}): {res.stderr[-300:]}")
    write_step_log("ADAPTER_TRAIN_FAILED", f"adapter={adapter} returncode={res.returncode}")
    return False


def train_adapters(adapters: list[str], steps: int, pacing_delay: float) -> list[str]:
    """
    Sequentially train each adapter, gating every pass on VRAM drain verification
    and purging CUDA memory between passes.
    """
    trained: list[str] = []
    for idx, adapter in enumerate(adapters):
        baseline_mb = get_vram_usage()
        purge_cuda_memory()

        # [Anchor 3] Hard gate: non-zero VRAM drain verification before training.
        if not wait_for_vram_drain(baseline_mb=baseline_mb):
            logger.critical(f"[TRAIN] VRAM not drained before adapter '{adapter}'; halting pipeline.")
            write_step_log("PIPELINE_HALTED", f"vram not drained before {adapter}")
            break

        adapter_steps = int(ADAPTER_STEPS.get(adapter, steps))
        dataset = dataset_for_adapter(adapter)
        logger.info(f"[TRAIN] Pass {idx + 1}/{len(adapters)} :: {adapter} ({adapter_steps} steps)")
        if run_adapter_training(adapter, dataset, adapter_steps, pacing_delay):
            trained.append(adapter)

    # Final hygiene pass so the host is left in a recoverable state.
    purge_cuda_memory()
    return trained


# ----------------------------------------------------------------------------- #
# Nightly mutex ([FEAT-213] / SCAR-036 Wait & Defer to Winner)
# ----------------------------------------------------------------------------- #
def check_and_acquire_lock(force: bool = False):
    """Acquire the nightly training mutex, deferring to a recent winner unless forced."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info(f"[MUTEX] Acquired nightly_lora_training lock (PID {os.getpid()}).")
    except (BlockingIOError, IOError):
        logger.info("[MUTEX] Another instance holds the lock; waiting for winner...")
        write_step_log("MUTEX_WAITING")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        logger.info(f"[MUTEX] Lock released by winner; acquired (PID {os.getpid()}).")

    if not force and STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text())
            last = state.get("last_completed_timestamp", 0)
            elapsed_h = (time.time() - last) / 3600.0
            if state.get("status") == "COMPLETED" and elapsed_h < 12.0:
                logger.info(f"[DEFER] Sweep completed {elapsed_h:.1f}h ago by PID {state.get('winner_pid')}; exiting cleanly.")
                write_step_log("DEFERRED_TO_WINNER", f"completed_by={state.get('winner_pid')}")
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
                return None
        except Exception as exc:
            logger.warning(f"[MUTEX] Could not inspect state ledger: {exc}")

    try:
        STATE_PATH.write_text(json.dumps({
            "status": "RUNNING",
            "winner_pid": os.getpid(),
            "started_at": time.time(),
            "started_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }, indent=2))
    except Exception as exc:
        logger.warning(f"[MUTEX] Could not write running state: {exc}")
    return lock_fd


def record_completion(lock_fd, status: str = "COMPLETED") -> None:
    """Record terminal status in the state ledger and release the mutex."""
    try:
        STATE_PATH.write_text(json.dumps({
            "status": status,
            "winner_pid": os.getpid(),
            "last_completed_timestamp": time.time() if status == "COMPLETED" else 0,
            "completed_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }, indent=2))
    except Exception as exc:
        logger.warning(f"[MUTEX] Could not record completion state: {exc}")
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass


# ----------------------------------------------------------------------------- #
# CLI
# ----------------------------------------------------------------------------- #
def _emit(payload: dict) -> None:
    """[Story 83.7 Anchor 4] Emit the structured stdout summary line."""
    print(json.dumps(payload))


def build_plan(adapters: list[str]) -> dict:
    """Resolve the adapter -> dataset plan (used by --list for dry validation)."""
    return {
        a: {"dataset": str(dataset_for_adapter(a)), "output": str(Path(ADAPTER_BASE_DIR) / a)}
        for a in adapters
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discrete Multi-LoRA Nightly Training Pipeline")
    parser.add_argument("--adapters", nargs="*", default=ADAPTER_TARGETS,
                        help="Subset of adapters to train (default: all ADAPTER_TARGETS)")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="Default training steps per adapter")
    parser.add_argument("--pacing-delay", type=float, default=DEFAULT_PACING_DELAY_S,
                        help="Hardware settling delay (seconds) per optimization step")
    parser.add_argument("--force", action="store_true", help="Bypass the 12-hour debounce check")
    parser.add_argument("--list", action="store_true", help="Print the resolved adapter plan and exit")
    args = parser.parse_args(argv)

    adapters = [a for a in (args.adapters or ADAPTER_TARGETS) if a]
    unknown = [a for a in adapters if a not in ADAPTER_TARGETS]
    if unknown:
        logger.error(f"[CLI] Unknown adapter(s): {unknown}. Known: {ADAPTER_TARGETS}")
        _emit({"adapters_trained": [], "status": "FAILED", "duration_s": 0.0})
        return 2

    if args.list:
        _emit({"adapters": build_plan(adapters)})
        return 0

    started = time.monotonic()
    lock_fd = check_and_acquire_lock(force=args.force)
    if lock_fd is None:
        _emit({"adapters_trained": [], "status": "SUCCESS", "duration_s": 0.0})
        return 0

    trained: list[str] = []
    status = "FAILED"
    try:
        logger.info("=== [Story 83.7] DISCRETE MULTI-LORA NIGHTLY TRAINING INITIATED ===")
        write_step_log("ORCHESTRATION_INIT", f"adapters={adapters}")

        verify_gpu_power_limit(max_limit_watts=170)
        ensure_datasets(force=args.force)  # [Story 864] --force reruns the dataset builder.

        if not quiesce_vllm():
            logger.critical("[FATAL] VRAM not evicted; aborting to protect host stability.")
            write_step_log("PIPELINE_ABORTED", "quiesce failed")
            return 1

        try:
            trained = train_adapters(adapters, args.steps, args.pacing_delay)
        finally:
            re_ignite_vllm()

        if len(trained) == len(adapters):
            status = "SUCCESS"
        elif trained:
            status = "PARTIAL"
        logger.info(f"=== PIPELINE COMPLETE: trained={trained} status={status} ===")
        write_step_log("PIPELINE_COMPLETE", f"trained={trained} status={status}")
    except Exception as exc:
        logger.error(f"[FATAL] Unhandled pipeline exception: {exc}")
        write_step_log("PIPELINE_ERROR", str(exc))
        status = "FAILED"
    finally:
        record_completion(lock_fd, status="COMPLETED" if status == "SUCCESS" else status)

    duration_s = round(time.monotonic() - started, 2)
    _emit({"adapters_trained": trained, "status": status, "duration_s": duration_s})
    return 0 if status == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
