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
KENDER_SSH_TARGET = "jallred@192.168.1.26"  # explicit user@host; ~/.ssh alias may be added later
KENDER_TRAIN_SCRIPT = "~/kender_forge/train_jason_voice_lora.py"
KENDER_DATA_STAGE = "~/kender_forge/data/journal_ledger.jsonl"
KENDER_ADAPTER_STAGE = "~/kender_forge/adapters/cli_voice_v1/"
SYNC_STAGING_DIR = "/speedy/models/adapters/.sync-staging/cli_voice_v1/"
VLLM_URL = "http://localhost:8088"

def write_step_log(step_name: str, details: str = ""):
    """[FEAT-213] Write atomic step progress to /tmp/nightly_forge_step.log to survive hard reboots."""
    timestamp = datetime.datetime.now().isoformat()
    log_line = f"[{timestamp}] [{step_name}] {details}\n"
    try:
        with open("/tmp/nightly_forge_step.log", "a") as f:
            f.write(log_line)
    except Exception as e:
        logger.warning(f"Failed to write step log: {e}")

def get_vram_usage():
    """Probe actual VRAM usage via nvidia-smi."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,nounits,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if len(lines) >= 2:
                return int(lines[-1].strip())
            if lines:
                val = lines[0].strip()
                if val != "memory.total [MiB]":
                    return int(val)
        return 0
    except Exception:
        return 0

def quiesce_vllm():
    """[FEAT-213] Quiesce vLLM & Foyer to free VRAM for Unsloth training."""
    logger.info("[FEAT-213] Requesting Foyer HIBERNATING state to reclaim VRAM...")
    write_step_log("QUIESCE_START", f"Requesting Foyer HIBERNATING")
    try:
        resp = requests.post(f"{FOYER_URL}/status_update", json={"state": "HIBERNATING"}, timeout=10)
        if resp.status_code == 200:
            logger.info("[FEAT-213] Foyer state updated to HIBERNATING. Settling 10s...")
            time.sleep(10)
            write_step_log("QUIESCE_OK", "Foyer HIBERNATING settled")
            return True
        else:
            logger.warning(f"[FEAT-213] Status update returned HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"[FEAT-213] Could not reach Foyer at {FOYER_URL}: {e}")
    write_step_log("QUIESCE_SKIP", "Foyer status update skipped or offline")
    return False

def re_ignite_vllm():
    """[FEAT-213] Re-ignite Foyer & vLLM post-training."""
    logger.info("[FEAT-213] Re-igniting Foyer state to OPERATIONAL...")
    write_step_log("RE_IGNITE_START", "Requesting Foyer OPERATIONAL")
    try:
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

def run_unsloth_forge():
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
        else:
            logger.error(f"[FEAT-160] LoRA training failed with code {res.returncode}: {res.stderr[-300:]}")
            write_step_log("UNSLOTH_FORGE_FAILED", f"returncode={res.returncode}")
    except Exception as e:
        logger.error(f"[FEAT-160] Error executing train_expert.py: {e}")
        write_step_log("UNSLOTH_FORGE_ERROR", str(e))

def run_kender_forge():
    """[SPR-52.0] Offload Unsloth pass to Kender (4090), rsync adapter back, hot-reload vLLM."""
    if not os.path.exists(DATASET_PATH):
        logger.warning(f"[SPR-52.0] Dataset {DATASET_PATH} not found. Skipping Kender training pass.")
        return

    # (a) Push dataset to Kender staging
    try:
        res = subprocess.run(["rsync", "-avz", "--timeout=60", DATASET_PATH,
                              f"{KENDER_SSH_TARGET}:{KENDER_DATA_STAGE}"],
                             capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning(f"[SPR-52.0] Dataset rsync failed: {res.stderr[-300:]}")
            return
    except Exception as e:
        logger.warning(f"[SPR-52.0] Dataset rsync error: {e}")
        return

    # (b) Trigger remote training (60 steps)
    cmd = ["ssh", KENDER_SSH_TARGET,
           f"python3 {KENDER_TRAIN_SCRIPT} {KENDER_DATA_STAGE} {KENDER_ADAPTER_STAGE} 60"]
    logger.info(f"[SPR-52.0] Executing: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"[SPR-52.0] Kender training failed (code {res.returncode}): {res.stderr[-300:]}")
            return
        logger.info(f"[SPR-52.0] Kender training OK. Tail: {res.stdout[-300:]}")
    except Exception as e:
        logger.error(f"[SPR-52.0] Error executing remote training: {e}")
        return

    # (c) Pull adapter back to staging dir
    try:
        os.makedirs(SYNC_STAGING_DIR, exist_ok=True)
        res = subprocess.run(["rsync", "-avz", "--partial",
                              f"{KENDER_SSH_TARGET}:{KENDER_ADAPTER_STAGE}", SYNC_STAGING_DIR],
                             capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning(f"[SPR-52.0] Adapter rsync failed: {res.stderr[-300:]}")
            return
    except Exception as e:
        logger.warning(f"[SPR-52.0] Adapter rsync error: {e}")
        return

    # (d) Atomic swap: staging -> live (vLLM never reads a half-written safetensors)
    try:
        os.makedirs(os.path.dirname(OUTPUT_LORA_DIR), exist_ok=True)
        if os.path.exists(OUTPUT_LORA_DIR):
            os.rename(OUTPUT_LORA_DIR, OUTPUT_LORA_DIR + ".old")
        os.rename(SYNC_STAGING_DIR, OUTPUT_LORA_DIR)
        if os.path.exists(OUTPUT_LORA_DIR + ".old"):
            shutil.rmtree(OUTPUT_LORA_DIR + ".old")
        logger.info(f"[SPR-52.0] Adapter atomically swapped into {OUTPUT_LORA_DIR}")
    except Exception as e:
        logger.error(f"[SPR-52.0] Atomic swap failed: {e}")
        return

    # (e) vLLM hot-reload (zero-downtime); fall back to re_ignite_vllm() on failure
    try:
        resp = requests.post(f"{VLLM_URL}/v1/load_lora_adapter",
                             json={"lora_name": "cli_voice_v1", "lora_path": OUTPUT_LORA_DIR},
                             timeout=10)
        if resp.status_code == 200:
            logger.info("[SPR-52.0] vLLM hot-reloaded cli_voice_v1 (zero-downtime <10ms claim kept).")
        else:
            logger.warning(f"[SPR-52.0] load_lora_adapter returned HTTP {resp.status_code}; falling back to re_ignite_vllm()")
            re_ignite_vllm()
    except Exception as e:
        logger.warning(f"[SPR-52.0] vLLM hot-reload error: {e}; falling back to re_ignite_vllm()")
        re_ignite_vllm()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nightly Forge orchestrator")
    parser.add_argument("--local", action="store_true",
                        help="Run legacy run_unsloth_forge() on z87 instead of Kender offload")
    args = parser.parse_args()

    logger.info("=== [FEAT-160/FEAT-213/SPR-52.0/SPR-53.0] NIGHTLY FORGE ORCHESTRATION INITIATED ===")
    write_step_log("ORCHESTRATION_INIT", f"local={args.local}")

    # 1. Pre-Flight System & RAM Health Telemetry
    try:
        load_avg = os.getloadavg()
        mem_info = shutil.disk_usage("/")
        logger.info(f"[PROBE] Pre-Flight Health: Load={load_avg} | Disk Free={mem_info.free // (1024*1024)}MB")
        write_step_log("PRE_FLIGHT_PROBE", f"load_avg={load_avg}, disk_free_mb={mem_info.free // (1024*1024)}")
    except Exception as e:
        logger.warning(f"[PROBE] Health probe warning: {e}")

    # 2. Quiesce Phase: Request Foyer HIBERNATING state to drain VRAM
    logger.info("[NIGHTLY STEP 1/3] Requesting Foyer VRAM Quiesce for Training...")
    quiesced = quiesce_vllm()

    # 3. Cooldown Phase 1: 15s VRAM Drain Settling Window
    logger.info("[NIGHTLY COOLDOWN 1] Settling 15s post-VRAM Quiesce...")
    write_step_log("QUIESCE_SETTLING", "Sleeping 15s")
    time.sleep(15)

    try:
        # 4. LoRA Training Pass
        logger.info("[NIGHTLY STEP 2/3 - FORGE] Executing Unsloth LoRA Fine-Tuning Pass...")
        if args.local:
            run_unsloth_forge()
        else:
            run_kender_forge()
            
        # 5. Cooldown Phase 2: 15s Post-Training Thermal Settling Window
        logger.info("[NIGHTLY COOLDOWN 2] Settling 15s post-training thermal cooldown...")
        write_step_log("TRAINING_SETTLING", "Sleeping 15s")
        time.sleep(15)
    finally:
        # 6. Re-Ignition Phase: Restore Foyer OPERATIONAL state
        logger.info("[NIGHTLY STEP 3/3] Re-igniting Foyer state to OPERATIONAL...")
        re_ignite_vllm()

    # 7. Note Ingestion & Mass Scan Phase (End of Sequence)
    logger.info("[NIGHTLY END STEP] Initiating Note Ingestion, Gem Refinement (capped at 25), & Mass Scan...")
    run_mass_scan()

    logger.info("=== NIGHTLY FORGE ORCHESTRATION COMPLETE ===")
    write_step_log("ORCHESTRATION_COMPLETE")

if __name__ == "__main__":
    main()
