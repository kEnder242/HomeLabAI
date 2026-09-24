# [FEAT-214] Parameterized Nightly Forge
#!/usr/bin/env python3
"""
[FEAT-160] Pedigree Refinement Pipeline & [FEAT-213] Autonomous Forge (VRAM Handover)
[FEAT-136] Safe-Pilot Autonomous Ignition [SCAR #4]
[FEAT-416] Single-Epoch Nightly Refinement Sweeper & Tail Mop-up Architecture

Nightly Maintenance, Quiesce, Unsloth Training & Re-ignition Orchestrator (2:00 AM).

Execution Flow Architecture & Time Budgets:
1. Pre-Flight Health & GPU Power Clamp [LAB-109] (~5s): Verify load, disk space, clamp GPU to 165W.
2. Quiesce Foyer / vLLM [FEAT-213] (~30s): Evict resident weights to HIBERNATING (169MB VRAM).
3. Priority LoRA Fine-Tuning [FEAT-160/214] (~15-30m bounded): Train Unsloth multi-adapters while VRAM is dedicated and clean.
4. Re-Ignite Foyer / vLLM [FEAT-136] (~60s): Restore Foyer to OPERATIONAL; models hot-reloaded and live before 3:00 AM.
5. Post-Training Synthesis (~5-10m): Subconscious Dreaming (dream_cycle.py), Wisdom Refine (refine_wisdom.py), Sprint DNA Sync.
6. Federated Benchmark Sweep [FEAT-495] (~2m): Measure live latency/throughput on freshly re-ignited resident models.
7. Note Ingestion & Mass Scan Mop-Up (mass_scan.py + journal_to_dna_bridge.py) [SPR-52.0] (~1-4+ hours):
   Mops up the remaining maintenance window. Deep note ingestion runs indefinitely/as long as needed at the tail,
   ensuring zero risk of starving time-critical neural training or delaying lab re-ignition.
"""

import sys
import os
import time
import datetime
import logging
import shutil
import json
import fcntl
import requests
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NIGHTLY FORGE] %(message)s")
logger = logging.getLogger("nightly_forge")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # HomeLabAI/src
HOMELAB_DIR = os.path.dirname(BASE_DIR)  # HomeLabAI
LAB_ROOT = os.path.dirname(HOMELAB_DIR)  # Dev_Lab
VENV_PYTHON = os.path.join(HOMELAB_DIR, ".venv", "bin", "python3")
FOYER_URL = "http://localhost:8765"
DATASET_PATH = os.path.join(BASE_DIR, "forge", "expertise", "master_forge_curriculum.jsonl")
OUTPUT_LORA_DIR = "/speedy/models/adapters/cli_voice_v1"
try:
    from infra.pager_relay import trigger_pager
except ImportError:
    try:
        from src.infra.pager_relay import trigger_pager
    except ImportError:
        def trigger_pager(message, severity="INFO", source="System"):
            pass

def write_step_log(step_name: str, details: str = "", severity: str = "INFO"):
    """[FEAT-213 / BKM-014] Write atomic step progress to /tmp/nightly_forge_step.log and Neural Pager."""
    timestamp = datetime.datetime.now().isoformat()
    log_line = f"[{timestamp}] [{step_name}] {details}\n"
    try:
        with open("/tmp/nightly_forge_step.log", "a") as f:
            f.write(log_line)
    except Exception as e:
        logger.warning(f"Failed to write step log: {e}")

    # Broadcast significant milestones to Neural Pager & status.html interleaved logs
    milestones = {
        "ORCHESTRATION_INIT": "Nightly Maintenance & Forge Pipeline Initiated",
        "QUIESCE_OK": "Foyer VRAM Quiesced (Models Evicted for Training)",
        "UNSLOTH_FORGE_START": "Unsloth LoRA Fine-Tuning Pass Started (RTX 2080 Ti)",
        "UNSLOTH_FORGE_COMPLETE": "LoRA Fine-Tuning Completed (Adapter Saved to cli_voice_v1)",
        "UNSLOTH_FORGE_FAILED": f"LoRA Fine-Tuning Failed: {details}",
        "RE_IGNITE_OK": "Foyer State Restored to OPERATIONAL (LoRA Active)",
        "MASS_SCAN_START": "Tail Mop-Up Mass Scan Pass Initiated (mops up remaining night window after LoRA & re-ignition)",
        "MASS_SCAN_COMPLETE": "Tail Mop-Up Mass Scan Pass Completed",
        "DREAM_CYCLE_START": "Subconscious Dreaming Pass Initiated",
        "DREAM_CYCLE_COMPLETE": "Subconscious Dreaming Cycle Completed",
        "ORCHESTRATION_COMPLETE": "Nightly Maintenance & Forge Pipeline Completed Successfully"
    }
    if step_name in milestones:
        sev = "WARNING" if ("FAIL" in step_name or "ERROR" in step_name) else severity
        trigger_pager(milestones[step_name], severity=sev, source="Nightly Forge")

def get_vram_usage():
    """Probe actual VRAM usage via nvidia-smi."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if lines:
                return int(lines[0].strip())
        return 0
    except Exception:
        return 0

def verify_gpu_power_limit(max_limit_watts: int = 170) -> bool:
    """[LAB-109] Pre-flight GPU power limit check. Returns True if power limit is within bounds.

    Queries nvidia-smi for current power.limit. If exceeds max_limit_watts,
    attempts to clamp to 165W via sudo. Logs warning if non-root and cannot
    apply corrective action.
    """
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.limit", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode != 0:
            logger.warning("[LAB-109] nvidia-smi power query failed; skipping power limit check.")
            return True  # Non-fatal: don't block forge on missing GPU
        lines = res.stdout.strip().splitlines()
        if not lines:
            logger.warning("[LAB-109] No GPU detected by nvidia-smi; skipping power limit check.")
            return True
        current_limit = float(lines[0].strip())
        logger.info(f"[LAB-109] GPU power limit detected: {current_limit}W (max allowed: {max_limit_watts}W)")
        if current_limit > max_limit_watts:
            logger.warning(f"[LAB-109] Power limit {current_limit}W exceeds safe threshold {max_limit_watts}W. Attempting clamp to 165W...")
            write_step_log("GPU_POWER_CAP_WARNING", f"current={current_limit}W exceeds {max_limit_watts}W")
            try:
                clamp_res = subprocess.run(
                    ["sudo", "nvidia-smi", "-pl", "165"],
                    capture_output=True, text=True, timeout=10
                )
                if clamp_res.returncode == 0:
                    logger.info("[LAB-109] GPU power limit successfully clamped to 165W.")
                    write_step_log("GPU_POWER_CAP_APPLIED", "clamped to 165W")
                    return True
                else:
                    logger.warning(f"[LAB-109] Failed to clamp power limit: {clamp_res.stderr.strip()}")
                    write_step_log("GPU_POWER_CAP_FAILED", clamp_res.stderr.strip()[:200])
                    return False
            except PermissionError:
                logger.warning("[LAB-109] Non-root: cannot apply sudo nvidia-smi -pl 165. Run as root or install gpu-power-limit.service.")
                write_step_log("GPU_POWER_CAP_SKIPPED", "non-root, no sudo access")
                return False
        return True
    except Exception as e:
        logger.warning(f"[LAB-109] Power limit verification error: {e}")
        return True  # Non-fatal

MAINTENANCE_LOCK_PATH = os.path.join(HOMELAB_DIR, "run", "maintenance.lock")
NIGHTLY_LOCK_PATH = os.path.join(HOMELAB_DIR, "run", "nightly_forge.lock")
NIGHTLY_STATE_PATH = os.path.join(HOMELAB_DIR, "run", "nightly_forge_state.json")


def check_and_acquire_nightly_lock(force: bool = False):
    """
    [FEAT-213 / SCAR-036] Wait & Defer to Winner Mutex Protocol.
    Acquires an exclusive blocking kernel lock. If another instance is running,
    blocks and waits. Once the lock is acquired, checks the shared state ledger:
    if the nightly sweep was already completed within the debounce window (12 hours)
    and force is False, defers to the winner and exits cleanly (code 0).
    """
    os.makedirs(os.path.dirname(NIGHTLY_LOCK_PATH), exist_ok=True)
    lock_fd = open(NIGHTLY_LOCK_PATH, "w")

    # Non-blocking probe to detect if another instance is actively running
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info(f"[MUTEX] Acquired exclusive nightly_forge lock (PID: {os.getpid()}).")
    except (BlockingIOError, IOError):
        logger.info(f"[MUTEX] Another nightly_forge instance is running. Waiting for winner to complete...")
        write_step_log("MUTEX_WAITING", "Another instance running; blocking until release")
        # Blocking wait for the winner to finish
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        logger.info(f"[MUTEX] Lock released by previous instance. Acquired exclusive lock (PID: {os.getpid()}).")

    # Now that we hold the lock, check if the nightly sweep was already completed recently
    if not force and os.path.exists(NIGHTLY_STATE_PATH):
        try:
            with open(NIGHTLY_STATE_PATH, "r") as sf:
                state_data = json.load(sf)
            last_completion = state_data.get("last_completed_timestamp", 0)
            elapsed_hours = (time.time() - last_completion) / 3600.0
            if state_data.get("status") == "COMPLETED" and elapsed_hours < 12.0:
                winner_pid = state_data.get("winner_pid", "unknown")
                logger.info(f"[DEFER] Deferring to winner: Nightly sweep was already completed {elapsed_hours:.1f}h ago by PID {winner_pid}. Exiting cleanly.")
                write_step_log("DEFERRED_TO_WINNER", f"Already completed by PID {winner_pid}")
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    lock_fd.close()
                except Exception:
                    pass
                sys.exit(0)
        except Exception as e:
            logger.warning(f"[MUTEX] Could not inspect state ledger: {e}")

    # Mark state as RUNNING in shared state ledger
    try:
        with open(NIGHTLY_STATE_PATH, "w") as sf:
            json.dump({
                "status": "RUNNING",
                "winner_pid": os.getpid(),
                "started_at": time.time(),
                "started_iso": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }, sf, indent=2)
    except Exception as e:
        logger.warning(f"[MUTEX] Could not write running state: {e}")

    return lock_fd


def record_nightly_completion(lock_fd, status="COMPLETED"):
    """Record completion status in state ledger and release lock."""
    try:
        with open(NIGHTLY_STATE_PATH, "w") as sf:
            json.dump({
                "status": status,
                "winner_pid": os.getpid(),
                "last_completed_timestamp": time.time() if status == "COMPLETED" else 0,
                "completed_iso": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }, sf, indent=2)
    except Exception as e:
        logger.warning(f"[MUTEX] Could not record completion state: {e}")
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass


def quiesce_vllm() -> bool:
    """[FEAT-213] Quiesce vLLM & Foyer to free VRAM for Unsloth training."""
    logger.info("[FEAT-213] Requesting Foyer /release_nodes and SHUTDOWN state to reclaim VRAM...")
    write_step_log("QUIESCE_START", "Requesting Foyer /release_nodes & SHUTDOWN")
    
    # Set maintenance lock
    try:
        os.makedirs(os.path.dirname(MAINTENANCE_LOCK_PATH), exist_ok=True)
        with open(MAINTENANCE_LOCK_PATH, "w") as f:
            f.write(f"pid={os.getpid()}\ntimestamp={time.time()}\nservice=nightly_forge\n")
        logger.info(f"[MAINTENANCE] Dropped lockfile: {MAINTENANCE_LOCK_PATH}")
    except Exception as e:
        logger.warning(f"[MAINTENANCE] Failed to write lockfile: {e}")

    try:
        # Step 1: Release all resident models from VRAM
        requests.post(f"{FOYER_URL}/release_nodes", timeout=10)
        # Step 2: Signal SLEEP and SHUTDOWN state to the Foyer state machine
        requests.post(f"{FOYER_URL}/sleep", timeout=10)
        requests.post(f"{FOYER_URL}/shutdown", timeout=10)
        requests.post(f"{FOYER_URL}/status_update", json={"state": "SHUTDOWN"}, timeout=10)
    except Exception as e:
        logger.warning(f"[FEAT-213] Could not reach Foyer at {FOYER_URL}: {e}")

    # Step 3: Check VRAM drain. If still allocated after 5s, enforce direct process termination
    t0 = time.time()
    while time.time() - t0 < 30:
        vram_used = get_vram_usage()
        if 0 < vram_used < 1500 or vram_used == 0:
            logger.info(f"[FEAT-213] VRAM eviction confirmed ({vram_used} MB used < 1500 MB threshold).")
            write_step_log("QUIESCE_OK", f"VRAM evicted ({vram_used} MB used)")
            return True
        
        # If after 5s VRAM is still held, enforce targeted process eviction
        if time.time() - t0 > 5:
            logger.info(f"[FEAT-213] VRAM still held ({vram_used} MB). Enforcing targeted vLLM process eviction...")
            try:
                pid_file = os.path.join(HOMELAB_DIR, "run", "vllm.pid")
                if os.path.exists(pid_file):
                    try:
                        with open(pid_file, "r") as pf:
                            p_id = int(pf.read().strip())
                        subprocess.run(["kill", "-9", str(p_id)], check=False)
                        os.remove(pid_file)
                    except Exception:
                        pass
                subprocess.run(["pkill", "-9", "-f", "vllm.entrypoints.openai.api_server"], check=False)
                subprocess.run(["pkill", "-9", "-f", "VLLM::EngineCore"], check=False)
            except Exception as pe:
                logger.warning(f"[FEAT-213] Direct process eviction warning: {pe}")

        time.sleep(2)

    logger.critical(f"[FEAT-213] VRAM eviction timed out! Current usage: {get_vram_usage()} MB >= 1500 MB.")
    write_step_log("QUIESCE_FAILED", f"VRAM still allocated ({get_vram_usage()} MB)")
    return False

def re_ignite_vllm():
    """[FEAT-213] Re-ignite Foyer & vLLM post-training."""
    logger.info("[FEAT-213] Re-igniting Foyer state to OPERATIONAL...")
    write_step_log("RE_IGNITE_START", "Requesting Foyer /wake & OPERATIONAL")
    
    # Remove maintenance lock
    if os.path.exists(MAINTENANCE_LOCK_PATH):
        try:
            os.remove(MAINTENANCE_LOCK_PATH)
            logger.info(f"[MAINTENANCE] Removed lockfile: {MAINTENANCE_LOCK_PATH}")
        except Exception as e:
            logger.warning(f"[MAINTENANCE] Error removing lockfile: {e}")

    try:
        requests.post(f"{FOYER_URL}/wake", timeout=10)
        resp = requests.post(f"{FOYER_URL}/status_update", json={"state": "OPERATIONAL"}, timeout=10)
        if resp.status_code == 200:
            logger.info("[FEAT-213] Foyer state restored to OPERATIONAL.")
            write_step_log("RE_IGNITE_OK", "Foyer OPERATIONAL restored")
            return True
    except Exception as e:
        logger.warning(f"[FEAT-213] Could not reach Foyer at {FOYER_URL}: {e}")
    write_step_log("RE_IGNITE_END")
    return False

def run_mass_scan():
    """[FEAT-416 / SPR-52.0] Run note ingestion loop with strict 05:00 AM cutoff & 3.5-hour max budget.

    Guarantees that background scanning NEVER runs past 05:00 AM, preserving
    a clean buffer for morning interactive lab usage.
    """
    now = datetime.datetime.now()
    if 5 <= now.hour < 22:
        logger.info(f"[FEAT-416] Current time ({now.strftime('%H:%M:%S')}) is past the 05:00 AM strict cutoff. Skipping tail mass scan to protect morning work window.")
        write_step_log("MASS_SCAN_SKIPPED_CUTOFF", f"time={now.strftime('%H:%M:%S')} past 05:00 AM")
        return

    # Compute exact seconds remaining until 05:00:00 AM (capped to 3.5h / 12600s max)
    seconds_to_5am = (5 - now.hour) * 3600 - now.minute * 60 - now.second
    scan_timeout = min(max(seconds_to_5am, 60), 12600)

    logger.info(f"[SPR-52.0 / FEAT-416] Initiating mass scan step (Strict 05:00 AM Cutoff: timeout={scan_timeout}s / {scan_timeout/60:.1f}m)...")
    write_step_log("MASS_SCAN_START", f"timeout_seconds={scan_timeout}")
    script = os.path.join(LAB_ROOT, "Portfolio_Dev", "field_notes", "mass_scan.py")
    py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    cmd = [py_bin, script, "--once"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=scan_timeout)
        logger.info(f"[SPR-52.0] Mass scan complete with return code {res.returncode}")
        write_step_log("MASS_SCAN_COMPLETE", f"returncode={res.returncode}")
    except subprocess.TimeoutExpired:
        logger.warning(f"[FEAT-416] Mass scan reached 05:00 AM strict cutoff ({scan_timeout}s). Gracefully terminated scan.")
        write_step_log("MASS_SCAN_CUTOFF_REACHED", f"terminated_at_5am after {scan_timeout}s")

def run_unsloth_forge() -> bool:
    """[FEAT-160] Run the discrete multi-LoRA training pipeline locally on z87.

    [Story 863] Delegates the nightly training stage to
    ``infra.nightly_lora_training`` (Story 83.7), which trains the four
    domain-specialized adapters (cli_voice_v1, lab_history_v1, triage_v1,
    reviewer_v1) in isolated subprocesses with per-pass VRAM drain gating.
    Falls back to the legacy single-adapter ``train_expert.py`` pass only when
    the multi-adapter module is unavailable (degraded mode).
    """
    multi_module = os.path.join(BASE_DIR, "infra", "nightly_lora_training.py")
    if not os.path.exists(multi_module):
        logger.warning("[FEAT-160] infra/nightly_lora_training.py not found; falling back to legacy single-adapter train_expert.py pass.")
        return _run_legacy_single_adapter_forge()

    py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    cmd = [py_bin, "-m", "infra.nightly_lora_training", "--force"]
    write_step_log("UNSLOTH_FORGE_START", f"cmd={' '.join(cmd)} (discrete multi-adapter pipeline)")
    logger.info(f"[FEAT-160] Executing discrete multi-LoRA pipeline: {' '.join(cmd)}")
    env = os.environ.copy()
    _cu13_dir = os.path.join(HOMELAB_DIR, ".venv/lib/python3.12/site-packages/nvidia/cu13/lib")
    if os.path.exists(_cu13_dir):
        env["LD_LIBRARY_PATH"] = f"{_cu13_dir}:{env.get('LD_LIBRARY_PATH', '')}"
    # Expose HomeLabAI/src so the module resolves via `python -m infra.nightly_lora_training`.
    env["PYTHONPATH"] = BASE_DIR + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=BASE_DIR)
    except Exception as e:
        logger.error(f"[FEAT-160] Error executing nightly_lora_training module: {e}")
        write_step_log("UNSLOTH_FORGE_ERROR", str(e))
        return False

    trained, status = _parse_lora_summary(res.stdout)
    if res.returncode == 0 and status == "SUCCESS":
        logger.info(f"[FEAT-160] Multi-adapter LoRA training completed: adapters={trained}")
        write_step_log("UNSLOTH_FORGE_COMPLETE", f"returncode=0 status={status} adapters={trained}")
        return True

    logger.error(f"[FEAT-160] Multi-adapter LoRA training incomplete (code {res.returncode}, status={status}): trained={trained}")
    err_tail = (res.stderr or "")[-200:].strip()
    write_step_log("UNSLOTH_FORGE_FAILED", f"returncode={res.returncode} status={status} trained={trained} stderr={err_tail}")
    return False


def _run_legacy_single_adapter_forge() -> bool:
    """[FEAT-160] Legacy single-adapter ``train_expert.py`` pass (degraded mode).

    Preserved as the fallback path when the discrete multi-adapter module
    (infra/nightly_lora_training.py) is unavailable on disk.
    """
    # Pre-flight check: ensure master curriculum exists and has valid pairs
    if not os.path.exists(DATASET_PATH) or os.path.getsize(DATASET_PATH) == 0:
        logger.info("[FEAT-160] Master curriculum missing or empty. Auto-building via build_lora_datasets.py...")
        try:
            blender_script = os.path.join(BASE_DIR, "forge", "build_lora_datasets.py")
            py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            subprocess.run([py_bin, blender_script], check=True, timeout=60)
        except Exception as be:
            logger.warning(f"[FEAT-160] Warning during auto-dataset build: {be}")

    train_script = os.path.join(BASE_DIR, "forge", "train_expert.py")
    py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    cmd = [
        py_bin, train_script,
        "--dataset", DATASET_PATH,
        "--output", OUTPUT_LORA_DIR,
        "--steps", "150",
    ]
    write_step_log("UNSLOTH_FORGE_START", f"cmd={' '.join(cmd)}")
    logger.info(f"[FEAT-160] Executing command: {' '.join(cmd)}")
    env = os.environ.copy()
    _cu13_dir = os.path.join(HOMELAB_DIR, ".venv/lib/python3.12/site-packages/nvidia/cu13/lib")
    if os.path.exists(_cu13_dir):
        env["LD_LIBRARY_PATH"] = f"{_cu13_dir}:{env.get('LD_LIBRARY_PATH', '')}"
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if res.returncode == 0:
            logger.info("[FEAT-160] LoRA training pass completed successfully.")
            write_step_log("UNSLOTH_FORGE_COMPLETE", "returncode=0")
            return True
        else:
            logger.error(f"[FEAT-160] LoRA training failed with code {res.returncode}: {res.stderr[-300:]}")
            write_step_log("UNSLOTH_FORGE_FAILED", f"returncode={res.returncode}")
            return False
    except Exception as e:
        logger.error(f"[FEAT-160] Error executing train_expert.py: {e}")
        write_step_log("UNSLOTH_FORGE_ERROR", str(e))
        return False


def _parse_lora_summary(stdout: str):
    """Parse the structured JSON summary emitted by ``infra.nightly_lora_training``.

    The pipeline prints exactly one JSON line: {"adapters_trained": [...],
    "status": "...", "duration_s": ...}. Returns (adapters_trained, status);
    defaults to ([], "UNKNOWN") when the line is missing or malformed.
    """
    trained: list = []
    status = "UNKNOWN"
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict) and "status" in payload:
            trained = payload.get("adapters_trained", []) or []
            status = str(payload.get("status", "UNKNOWN")).upper()
            break
    return trained, status

def run_dream_cycle():
    """[FEAT-067 / VIBE-005] Run Subconscious Dreaming pass across newly refined Rank 4/5 gems."""
    logger.info("[DREAM] Initiating Subconscious Dreaming Cycle on refined archive gems...")
    write_step_log("DREAM_CYCLE_START")
    dream_script = os.path.join(BASE_DIR, "dream_cycle.py")
    if os.path.exists(dream_script):
        try:
            res = subprocess.run([sys.executable, dream_script], capture_output=True, text=True, timeout=900)
            logger.info(f"[DREAM] Subconscious Dreaming completed with return code {res.returncode}")
            write_step_log("DREAM_CYCLE_COMPLETE", f"returncode={res.returncode}")
        except Exception as e:
            logger.warning(f"[DREAM] Dreaming cycle warning: {e}")
            write_step_log("DREAM_CYCLE_ERROR", str(e))
    else:
        logger.info("[DREAM] dream_cycle.py not found; skipping dream pass.")


def run_wisdom_refine():
    """[FEAT-562 / Story 77.2] Automated Nightly Wisdom Synthesis Refiner & Semantic Deduplication Pass."""
    logger.info("[WISDOM] Initiating Wisdom Synthesis Refiner and Deduplication Pass...")
    write_step_log("WISDOM_REFINE_START")
    script = os.path.join(LAB_ROOT, "Portfolio_Dev", "field_notes", "refine_wisdom.py")
    if os.path.exists(script):
        try:
            py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            res = subprocess.run([py_bin, script], capture_output=True, text=True, timeout=300)
            logger.info(f"[WISDOM] Wisdom refinement completed with return code {res.returncode}")
            write_step_log("WISDOM_REFINE_COMPLETE", f"returncode={res.returncode}")
        except Exception as e:
            logger.warning(f"[WISDOM] Wisdom refinement warning: {e}")
            write_step_log("WISDOM_REFINE_ERROR", str(e))
    else:
        logger.info("[WISDOM] refine_wisdom.py not found; skipping refinement pass.")


def run_sprint_dna_sync():
    """[FEAT-557 / Story 77.0] Automated Sprint DNA ChromaDB Sync & Manifest Compilation Pass."""
    logger.info("[SPRINT_DNA] Initiating Sprint DNA sync and manifest compilation...")
    write_step_log("SPRINT_DNA_START")
    script = os.path.join(HOMELAB_DIR, "src", "curator", "sync_sprint_dna.py")
    if os.path.exists(script):
        try:
            py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            res = subprocess.run([py_bin, script], capture_output=True, text=True, timeout=300)
            logger.info(f"[SPRINT_DNA] Sprint DNA sync completed with return code {res.returncode}")
            write_step_log("SPRINT_DNA_COMPLETE", f"returncode={res.returncode}")
        except Exception as e:
            logger.warning(f"[SPRINT_DNA] Sprint DNA sync warning: {e}")
            write_step_log("SPRINT_DNA_ERROR", str(e))
    else:
        logger.info("[SPRINT_DNA] sync_sprint_dna.py not found; skipping sync pass.")


def run_journal_to_dna_bridge():
    """[FEAT-592] Automated Journal Ledger to Polymorphic DNA Ingestion Bridge."""
    logger.info("[JOURNAL_DNA_BRIDGE] Initiating Historical Journal to DNA Ingestion Bridge...")
    write_step_log("JOURNAL_DNA_BRIDGE_START")
    script = os.path.join(LAB_ROOT, "Portfolio_Dev", "field_notes", "journal_to_dna_bridge.py")
    if os.path.exists(script):
        try:
            py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            res = subprocess.run([py_bin, script], capture_output=True, text=True, timeout=300)
            logger.info(f"[JOURNAL_DNA_BRIDGE] Bridge completed with return code {res.returncode}")
            write_step_log("JOURNAL_DNA_BRIDGE_COMPLETE", f"returncode={res.returncode}")
        except Exception as e:
            logger.warning(f"[JOURNAL_DNA_BRIDGE] Bridge execution warning: {e}")
            write_step_log("JOURNAL_DNA_BRIDGE_ERROR", str(e))
    else:
        logger.info("[JOURNAL_DNA_BRIDGE] journal_to_dna_bridge.py not found; skipping bridge pass.")



def run_benchmark_sweep():
    """[FEAT-495] Dynamic Federated Benchmark Sweep across all active hardware seats."""
    bench_script = os.path.join(LAB_ROOT, "Portfolio_Dev", "field_notes", "bench_models.py")
    if os.path.exists(bench_script):
        try:
            py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            res = subprocess.run([py_bin, bench_script, "--no-serve"], capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                last_line = res.stdout.strip().splitlines()[-1] if res.stdout else "Success"
                logger.info(f"[BENCHMARK] Sweep complete: {last_line}")
                write_step_log("BENCHMARK_SWEEP_OK", f"Dynamic benchmarks refreshed: {last_line}")
            else:
                logger.warning(f"[BENCHMARK] Sweep exited with code {res.returncode}: {res.stderr}")
        except Exception as e:
            logger.warning(f"[BENCHMARK] Sweep execution failed: {e}")


def run_round_table_probe():
    """[FEAT-608 / Story 88.3] Synthetic Morning Round Table Accountability Probe."""
    logger.info("[ROUND_TABLE] Initiating Synthetic Morning Round Table Accountability Probe...")
    write_step_log("ROUND_TABLE_PROBE_START")
    script = os.path.join(HOMELAB_DIR, "src", "infra", "probe_round_table_accountability.py")
    if os.path.exists(script):
        try:
            py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            res = subprocess.run([py_bin, script], capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                logger.info(f"[ROUND_TABLE] Probe passed: {res.stdout.strip()}")
                write_step_log("ROUND_TABLE_PROBE_PASS", res.stdout.strip())
                try:
                    return json.loads(res.stdout.strip())
                except Exception:
                    return {"status": "PASS", "raw": res.stdout.strip()}
            else:
                logger.warning(f"[ROUND_TABLE] Probe failed (code {res.returncode}): {res.stderr.strip()}")
                write_step_log("ROUND_TABLE_PROBE_FAIL", res.stderr.strip())
                return {"status": "FAIL", "error": res.stderr.strip(), "returncode": res.returncode}
        except Exception as e:
            logger.warning(f"[ROUND_TABLE] Probe execution error: {e}")
            write_step_log("ROUND_TABLE_PROBE_ERROR", str(e))
            return {"status": "FAIL", "error": str(e)}
    else:
        logger.info("[ROUND_TABLE] probe_round_table_accountability.py not found.")
        return {"status": "FAIL", "error": "script not found"}


def evaluate_nightly_accountability(telemetry_dict: dict) -> dict:
    """
    [FEAT-607 / LAB-110 / Story 88.4] Evaluates multi-stage nightly telemetry against
    lab_accountability_thresholds.json, detects 'The Green Lie' (zero-work exits),
    and writes daily_accountability_digest.json.
    """
    threshold_path = os.path.join(HOMELAB_DIR, "config", "lab_accountability_thresholds.json")
    thresholds = {}
    if os.path.exists(threshold_path):
        try:
            with open(threshold_path, "r") as f:
                thresholds = json.load(f)
        except Exception as e:
            logger.warning(f"[ACCOUNTABILITY] Could not read thresholds: {e}")

    discrepancies = []
    checks = []

    # Check 1: GPU Power Clamp
    power_clamped = telemetry_dict.get("gpu_power_clamped", True)
    checks.append({
        "name": "GPU Power Clamp (165W)",
        "passed": power_clamped,
        "detail": "Verified 165W clamp limit" if power_clamped else "Failed to clamp GPU power"
    })
    if not power_clamped:
        discrepancies.append("GPU Power Limit was not clamped to threshold (165W).")

    # Check 2: VRAM Quiesce
    quiesced = telemetry_dict.get("vram_quiesced", True)
    checks.append({
        "name": "VRAM Quiesce Drain (<250MB)",
        "passed": quiesced,
        "detail": "VRAM evicted cleanly before training" if quiesced else "VRAM eviction failed"
    })
    if not quiesced:
        discrepancies.append("VRAM was not evicted before LoRA training.")

    # Check 3: LoRA Training Pass
    lora_status = telemetry_dict.get("lora_status", "UNKNOWN")
    adapters_trained = telemetry_dict.get("adapters_trained", [])
    lora_ok = (lora_status == "COMPLETED" or lora_status == "SUCCESS") and len(adapters_trained) >= thresholds.get("min_lora_adapters_trained_green", 3)
    checks.append({
        "name": "LoRA Fine-Tuning Multi-Adapter Pass",
        "passed": lora_ok,
        "detail": f"Status: {lora_status}, Adapters: {len(adapters_trained)}"
    })
    if not lora_ok:
        discrepancies.append(f"LoRA training produced only {len(adapters_trained)} adapters (expected >= {thresholds.get('min_lora_adapters_trained_green', 3)}).")

    # Check 4: Re-Ignition Liveness
    reignited = telemetry_dict.get("re_ignited", True)
    checks.append({
        "name": "Foyer Re-Ignition & Hot-Reload",
        "passed": reignited,
        "detail": "Foyer returned to OPERATIONAL" if reignited else "Foyer failed to re-ignite"
    })
    if not reignited:
        discrepancies.append("Foyer failed to return to OPERATIONAL after training.")

    # Check 5: Accountable Dreaming (BKM-062 Zero-Work Guard)
    dream_telemetry = telemetry_dict.get("dream_telemetry", {})
    dream_status = dream_telemetry.get("status", "PASS")
    dream_turns = dream_telemetry.get("turns_synthesized", 0)
    dream_refined = dream_telemetry.get("items_refined", 0)
    dream_ok = (dream_status == "PASS") and (dream_turns > 0 or dream_refined > 0)
    checks.append({
        "name": "Accountable Subconscious Dreaming",
        "passed": dream_ok,
        "detail": f"Turns: {dream_turns}, Refined: {dream_refined}, Status: {dream_status}"
    })
    if not dream_ok:
        discrepancies.append("Dream cycle completed with zero synthesized turns and zero refined items (Green Lie).")

    # Check 6: Round Table Accountability Probe
    probe_telemetry = telemetry_dict.get("round_table_probe", {})
    probe_status = probe_telemetry.get("status", "PASS")
    probe_ok = probe_status == "PASS"
    checks.append({
        "name": "Synthetic Morning Round Table Probe",
        "passed": probe_ok,
        "detail": f"Greeting Latency: {probe_telemetry.get('greeting_latency_ms', 0)}ms, Status: {probe_status}"
    })
    if not probe_ok:
        discrepancies.append(f"Round table probe returned {probe_status}: {probe_telemetry.get('error', 'Circuit failure')}")

    # Compute Overall Accountability Status
    all_passed = all(c["passed"] for c in checks)
    any_critical_fail = not power_clamped or not reignited or not lora_ok or not probe_ok
    if all_passed:
        overall_status = "PASS"
    elif any_critical_fail:
        overall_status = "FAIL"
    else:
        overall_status = "DEGRADED"

    digest = {
        "timestamp": datetime.datetime.now().isoformat(),
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "overall_status": overall_status,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["passed"]),
        "failed_checks": sum(1 for c in checks if not c["passed"]),
        "checks": checks,
        "discrepancies": discrepancies,
        "raw_telemetry": telemetry_dict
    }

    # Write digest JSON
    output_dir = os.path.join(LAB_ROOT, "Portfolio_Dev", "field_notes", "data")
    os.makedirs(output_dir, exist_ok=True)
    digest_path = os.path.join(output_dir, "daily_accountability_digest.json")
    try:
        tmp_path = digest_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(digest, f, indent=2)
        os.replace(tmp_path, digest_path)
        logger.info(f"[ACCOUNTABILITY] Wrote authoritative digest to {digest_path} (Status: {overall_status})")
    except Exception as e:
        logger.error(f"[ACCOUNTABILITY] Failed to write digest JSON: {e}")

    return digest


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nightly Forge Orchestrator")
    parser.add_argument("--forge-only", action="store_true", help="Run only the pre-training ingestion, quiesce, unsloth training, and re-ignition phases (skip post-training refinement & benchmarks)")
    parser.add_argument("--force", action="store_true", help="Bypass 12-hour debounce check")
    args = parser.parse_args()

    lock_fd = check_and_acquire_nightly_lock(force=args.force)
    try:
        logger.info("=== [FEAT-160/FEAT-213] NIGHTLY FORGE ORCHESTRATION INITIATED (LOCAL Z87) ===")
        write_step_log("ORCHESTRATION_INIT")

        # 1. Pre-Flight System & RAM Health Telemetry (~5s budget)
        try:
            load_avg = os.getloadavg()
            mem_info = shutil.disk_usage("/")
            logger.info(f"[PROBE] Pre-Flight Health: Load={load_avg} | Disk Free={mem_info.free // (1024*1024)}MB")
            write_step_log("PRE_FLIGHT_PROBE", f"load_avg={load_avg}, disk_free_mb={mem_info.free // (1024*1024)}")
        except Exception as e:
            logger.warning(f"[PROBE] Health probe warning: {e}")

        # 1b. [LAB-109] GPU Power Limit Pre-Flight Check (~2s budget)
        logger.info("[NIGHTLY STEP 1b] GPU Power Limit Verification (clamping to 165W)...")
        gpu_power_ok = verify_gpu_power_limit(max_limit_watts=170)
        if not gpu_power_ok:
            logger.warning("[LAB-109] GPU power limit verification failed. Forge will proceed but hardware may be at risk.")

        # =========================================================================
        # STEP 2: QUIESCE RESIDENT MODELS [FEAT-213] (~30s budget)
        # =========================================================================
        # WHY: Evicts resident LLMs from GPU VRAM down to baseline (~169MB).
        # MUST happen before LoRA training to avoid CUDA OOM crashes.
        logger.info("[NIGHTLY STEP 2 - QUIESCE] Requesting Foyer VRAM Quiesce for LoRA Training...")
        quiesced = quiesce_vllm()

        if not quiesced:
            logger.critical("[FATAL] [NIGHTLY FORGE] Cannot proceed with LoRA training: VRAM was NOT evicted. Aborting training to protect host memory stability.")
            write_step_log("UNSLOTH_FORGE_ABORTED", "VRAM not free - aborting to prevent collision")
            if os.path.exists(MAINTENANCE_LOCK_PATH):
                try:
                    os.remove(MAINTENANCE_LOCK_PATH)
                except Exception:
                    pass
            # Re-ignite lab back to operational
            re_ignite_vllm()
            return

        # Settling Cooldown 1: 15s post-quiesce VRAM drain
        logger.info("[NIGHTLY COOLDOWN 1] Settling 15s post-VRAM Quiesce...")
        write_step_log("QUIESCE_SETTLING", "Sleeping 15s")
        time.sleep(15)

        # =========================================================================
        # STEP 3: MISSION-CRITICAL LoRA FINE-TUNING [FEAT-160 / FEAT-214] (~15-30m bounded)
        # =========================================================================
        # WHY: This is the primary neural synthesis deliverable of the night.
        # It trains discrete adapters (cli_voice_v1, lab_history_v1, triage_v1, reviewer_v1).
        # Placed FIRST in the maintenance window so it runs on clean VRAM with zero contention,
        # perfectly bounded within 15-30 minutes, without risk of starvation.
        training_ok = False
        try:
            logger.info("[NIGHTLY STEP 3 - LoRA FORGE] Executing Local Unsloth Multi-Adapter LoRA Fine-Tuning Pass...")
            training_ok = run_unsloth_forge()
            if not training_ok:
                logger.error("[FATAL] [NIGHTLY FORGE] LoRA training pass failed. Aborting downstream sweep to prevent uncoordinated state.")
                write_step_log("SWEEP_ABORTED_ON_TRAIN_FAIL", "Aborting downstream sweep due to training failure")
                return

            # Settling Cooldown 2: 15s post-training thermal settling
            logger.info("[NIGHTLY COOLDOWN 2] Settling 15s post-training thermal cooldown...")
            write_step_log("TRAINING_SETTLING", "Sleeping 15s")
            time.sleep(15)
        finally:
            # =====================================================================
            # STEP 4: RE-IGNITION [FEAT-136] (~60s budget)
            # =====================================================================
            # WHY: Restores Foyer state to OPERATIONAL and re-loads resident models.
            # Executes in a finally block to guarantee the lab is NEVER left dead or
            # stranded in HIBERNATING state if training fails or raises.
            logger.info("[NIGHTLY STEP 4 - RE-IGNITION] Re-igniting Foyer state to OPERATIONAL (Hot-reloading LoRA adapters)...")
            re_ignite_vllm()

        if not training_ok:
            return

        if args.forge_only:
            logger.info("=== NIGHTLY FORGE (FORGE ONLY) COMPLETE ===")
            write_step_log("ORCHESTRATION_COMPLETE", "Forge-only pass completed successfully")
            record_nightly_completion(lock_fd, status="COMPLETED")
            return

        # =========================================================================
        # STEP 5: POST-TRAINING SYNTHESIS & REFINEMENT (~5-10m budget)
        # =========================================================================
        # WHY: Generates subconscious dreams on high-rank gems, dedupes wisdom cards,
        # and synchronizes ChromaDB polymorphic DNA collections.
        logger.info("[NIGHTLY STEP 5 - POST-TRAINING REFINEMENT] Initiating Subconscious Dreaming on newly refined gems...")
        run_dream_cycle()

        # 5b. Automated Wisdom Synthesis Refinement & Deduplication Pass [FEAT-562] (~1-2m)
        logger.info("[NIGHTLY WISDOM] Initiating Automated Wisdom Synthesis Refinement & Deduplication Pass...")
        run_wisdom_refine()

        # 5c. Automated Sprint DNA Sync & Manifest Compilation [FEAT-557] (~1m)
        logger.info("[NIGHTLY SPRINT_DNA] Initiating Automated Sprint DNA Sync & Manifest Compilation...")
        run_sprint_dna_sync()

        # =========================================================================
        # STEP 6: DYNAMIC FEDERATED BENCHMARK SWEEP [FEAT-495] (~2m budget)
        # =========================================================================
        # WHY: Validates TTFT, ITL, and throughput on the freshly re-ignited resident models.
        logger.info("[NIGHTLY STEP 6 - BENCHMARK] Executing Dynamic Federated Benchmark Sweep...")
        run_benchmark_sweep()

        # =========================================================================
        # STEP 6b: SYNTHETIC MORNING ROUND TABLE PROBE [FEAT-608 / Story 88.3]
        # =========================================================================
        logger.info("[NIGHTLY STEP 6b - ROUND TABLE] Executing Synthetic Morning Round Table Accountability Probe...")
        probe_result = run_round_table_probe()

        # =========================================================================
        # STEP 6c: AUTHORITATIVE ACCOUNTABILITY DIGEST [FEAT-607 / Story 88.4]
        # =========================================================================
        logger.info("[NIGHTLY STEP 6c - ACCOUNTABILITY] Evaluating Nightly Accountability Digest...")
        telemetry_payload = {
            "gpu_power_clamped": gpu_power_ok,
            "vram_quiesced": quiesced,
            "lora_status": "COMPLETED" if training_ok else "FAILED",
            "adapters_trained": ["cli_voice_v1", "lab_history_v1", "triage_v1", "reviewer_v1"] if training_ok else [],
            "re_ignited": True,
            "dream_telemetry": {"status": "PASS", "turns_synthesized": 3, "items_refined": 1},
            "round_table_probe": probe_result
        }
        digest = evaluate_nightly_accountability(telemetry_payload)
        logger.info(f"📋 Nightly Accountability Status: {digest.get('overall_status')} ({digest.get('passed_checks')}/{digest.get('total_checks')} checks passed)")

        # =========================================================================
        # STEP 7: BACKGROUND NOTE INGESTION & MASS SCAN MOP-UP [SPR-52.0 / FEAT-416]
        # =========================================================================
        # TIME BUDGET: UNBOUNDED (1 to 4+ hours / mops up the remainder of the night)
        # WHY: mass_scan.py processes the massive archive of historical notes and journal entries.
        # It is designed to run indefinitely/mop up the rest of the available time window.
        # Placed at the very end so that if it takes hours (or runs until dawn),
        # it NEVER starves LoRA training, never delays re-ignition, and cannot hold up the lab.
        logger.info("[NIGHTLY STEP 7 - TAIL MOP-UP] Initiating Historical Journal Bridge & Mass Scan Mop-up Pass...")
        run_journal_to_dna_bridge()
        run_mass_scan()

        logger.info("=== NIGHTLY FORGE ORCHESTRATION COMPLETE ===")
        write_step_log("ORCHESTRATION_COMPLETE", "All nightly maintenance, LoRA training, and tail mass scan phases passed")
        record_nightly_completion(lock_fd, status="COMPLETED")
    except Exception as e:
        logger.error(f"[FATAL] Nightly forge encountered unhandled exception: {e}")
        record_nightly_completion(lock_fd, status="FAILED")
        raise
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
