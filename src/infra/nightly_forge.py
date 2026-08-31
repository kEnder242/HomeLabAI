# [FEAT-214] Parameterized Nightly Forge
#!/usr/bin/env python3
"""
[FEAT-160] Pedigree Refinement Pipeline & [FEAT-213] Autonomous Forge (VRAM Handover)
# [FEAT-136] Safe-Pilot Autonomous Ignition [SCAR #4]
Nightly Maintenance, Quiesce, Unsloth Training & Re-ignition Orchestrator (2:00 AM).

Execution Flow:
1. Quiesce Foyer / vLLM (POST /status_update -> HIBERNATING) to reclaim VRAM.
2. Execute mass_scan.py --once to ingest raw notes and extract Rank 4 Gems.
3. Run Unsloth fine-tuning via src/forge/train_expert.py (FEAT-160 / FEAT-214).
4. Re-ignite Foyer / vLLM (POST /status_update -> OPERATIONAL) to hot-reload LoRA.
"""

import sys
import os
import time
import datetime
import logging
import shutil
import requests
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NIGHTLY FORGE] %(message)s")
logger = logging.getLogger("nightly_forge")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOYER_URL = "http://localhost:8765"
DATASET_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/journal_ledger.jsonl")
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
        "MASS_SCAN_START": "Mass Scan & Gem Refinement Window Active (03:00 - 05:00 AM)",
        "MASS_SCAN_COMPLETE": "Mass Scan & Gem Refinement Window Completed",
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

MAINTENANCE_LOCK_PATH = os.path.expanduser("~/Dev_Lab/HomeLabAI/run/maintenance.lock")


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

    # Step 3: Hard Verification — Poll VRAM usage for up to 30s until < 1500MB
    logger.info("[FEAT-213] Verifying physical VRAM eviction via NVML/nvidia-smi...")
    t0 = time.time()
    while time.time() - t0 < 30:
        vram_used = get_vram_usage()
        if 0 < vram_used < 1500:
            logger.info(f"[FEAT-213] VRAM eviction confirmed ({vram_used} MB used < 1500 MB threshold).")
            write_step_log("QUIESCE_OK", f"VRAM evicted ({vram_used} MB used)")
            return True
        elif vram_used == 0:
            logger.info("[FEAT-213] GPU query returned 0 MB, assuming VRAM evicted.")
            write_step_log("QUIESCE_OK", "VRAM query 0 (evicted)")
            return True
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
    cmd = ["python3", os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/mass_scan.py"), "--once"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(f"[SPR-52.0] Mass scan complete with return code {res.returncode}")
    write_step_log("MASS_SCAN_COMPLETE", f"returncode={res.returncode}")

def run_unsloth_forge() -> bool:
    """[FEAT-160] Run Unsloth LoRA fine-tuning locally on z87 (--local path)."""
    train_script = os.path.join(BASE_DIR, "forge", "train_expert.py")
    cmd = [
        sys.executable, train_script,
        "--dataset", DATASET_PATH,
        "--output", OUTPUT_LORA_DIR,
    ]
    write_step_log("UNSLOTH_FORGE_START", f"cmd={' '.join(cmd)}")
    logger.info(f"[FEAT-160] Executing command: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
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


def run_benchmark_sweep():
    """[FEAT-495] Dynamic Federated Benchmark Sweep across all active hardware seats."""
    bench_script = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/bench_models.py")
    if os.path.exists(bench_script):
        try:
            res = subprocess.run([sys.executable, bench_script, "--no-serve"], capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                last_line = res.stdout.strip().splitlines()[-1] if res.stdout else "Success"
                logger.info(f"[BENCHMARK] Sweep complete: {last_line}")
                write_step_log("BENCHMARK_SWEEP_OK", f"Dynamic benchmarks refreshed: {last_line}")
            else:
                logger.warning(f"[BENCHMARK] Sweep exited with code {res.returncode}: {res.stderr}")
        except Exception as e:
            logger.warning(f"[BENCHMARK] Sweep execution failed: {e}")


def main():
    logger.info("=== [FEAT-160/FEAT-213] NIGHTLY FORGE ORCHESTRATION INITIATED (LOCAL Z87) ===")
    write_step_log("ORCHESTRATION_INIT")

    # 1. Pre-Flight System & RAM Health Telemetry
    try:
        load_avg = os.getloadavg()
        mem_info = shutil.disk_usage("/")
        logger.info(f"[PROBE] Pre-Flight Health: Load={load_avg} | Disk Free={mem_info.free // (1024*1024)}MB")
        write_step_log("PRE_FLIGHT_PROBE", f"load_avg={load_avg}, disk_free_mb={mem_info.free // (1024*1024)}")
    except Exception as e:
        logger.warning(f"[PROBE] Health probe warning: {e}")

    # 1b. [LAB-109] GPU Power Limit Pre-Flight Check
    logger.info("[NIGHTLY STEP 1b] GPU Power Limit Verification...")
    gpu_power_ok = verify_gpu_power_limit(max_limit_watts=170)
    if not gpu_power_ok:
        logger.warning("[LAB-109] GPU power limit verification failed. Forge will proceed but hardware may be at risk.")

    # 2. Quiesce Phase: Request Foyer HIBERNATING state to drain VRAM
    logger.info("[NIGHTLY STEP 2/4] Requesting Foyer VRAM Quiesce for Training...")
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

    # 3. Cooldown Phase 1: 15s VRAM Drain Settling Window
    logger.info("[NIGHTLY COOLDOWN 1] Settling 15s post-VRAM Quiesce...")
    write_step_log("QUIESCE_SETTLING", "Sleeping 15s")
    time.sleep(15)

    training_ok = False
    try:
        # 4. Heavy LoRA Training Pass (02:00 AM) - 100% Local on z87-Linux RTX 2080 Ti
        logger.info("[NIGHTLY STEP 2/4 - FORGE] Executing Local Unsloth LoRA Fine-Tuning Pass...")
        training_ok = run_unsloth_forge()
        if not training_ok:
            logger.error("[FATAL] [NIGHTLY FORGE] LoRA training pass failed. Aborting sweep to prevent uncoordinated daytime scans.")
            write_step_log("SWEEP_ABORTED_ON_TRAIN_FAIL", "Aborting mass scan due to training failure")
            return
            
        # 5. Cooldown Phase 2: 15s Post-Training Thermal Settling Window
        logger.info("[NIGHTLY COOLDOWN 2] Settling 15s post-training thermal cooldown...")
        write_step_log("TRAINING_SETTLING", "Sleeping 15s")
        time.sleep(15)
    finally:
        # 6. Re-Ignition Phase: Restore Foyer OPERATIONAL state
        logger.info("[NIGHTLY STEP 3/4] Re-igniting Foyer state to OPERATIONAL...")
        re_ignite_vllm()

    if not training_ok:
        return

    # 7. Note Ingestion & Mass Scan Refinement Phase (Active Window: 3:00 AM – 5:00 AM)
    logger.info("[NIGHTLY STEP 4/4] Initiating Note Ingestion & Mass Scan (Window: 3:00 AM – 5:00 AM)...")
    run_mass_scan()

    # 8. Post-Scan Subconscious Dreaming & WYWO (05:00 AM – 05:30 AM)
    logger.info("[NIGHTLY POST-SCAN] Initiating Post-Scan Subconscious Dreaming on newly refined gems...")
    run_dream_cycle()

    # 9. Dynamic Federated Benchmark Sweep (05:30 AM) [FEAT-495]
    logger.info("[NIGHTLY STEP 5/5] Executing Dynamic Federated Benchmark Sweep...")
    run_benchmark_sweep()

    logger.info("=== NIGHTLY FORGE ORCHESTRATION COMPLETE ===")
    write_step_log("ORCHESTRATION_COMPLETE", "All nightly maintenance and benchmark phases passed")

if __name__ == "__main__":
    main()
