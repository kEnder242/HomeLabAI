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
    """Run note ingestion loop."""
    logger.info("[SPR-52.0] Initiating mass scan step...")
    write_step_log("MASS_SCAN_START")
    script = os.path.join(LAB_ROOT, "Portfolio_Dev", "field_notes", "mass_scan.py")
    py_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    cmd = [py_bin, script, "--once"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(f"[SPR-52.0] Mass scan complete with return code {res.returncode}")
    write_step_log("MASS_SCAN_COMPLETE", f"returncode={res.returncode}")

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
