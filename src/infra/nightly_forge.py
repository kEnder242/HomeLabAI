#!/usr/bin/env python3
"""
[FEAT-160] Pedigree Refinement Pipeline & [FEAT-213] Autonomous Forge (VRAM Handover)
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
import logging
import requests
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NIGHTLY FORGE] %(message)s")
logger = logging.getLogger("nightly_forge")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOYER_URL = "http://localhost:8765"
DATASET_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/journal_ledger.jsonl")
OUTPUT_LORA_DIR = "/speedy/models/adapters/cli_voice_v1"

def quiesce_vllm():
    """[FEAT-213] Quiesce vLLM & Foyer to free VRAM for Unsloth training."""
    logger.info("[FEAT-213] Requesting Foyer HIBERNATING state to reclaim VRAM...")
    try:
        resp = requests.post(f"{FOYER_URL}/status_update", json={"state": "HIBERNATING"}, timeout=10)
        if resp.status_code == 200:
            logger.info("[FEAT-213] Foyer state updated to HIBERNATING. Settling 10s...")
            time.sleep(10)
            return True
        else:
            logger.warning(f"[FEAT-213] Status update returned HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"[FEAT-213] Could not reach Foyer at {FOYER_URL}: {e}")
    return False

def re_ignite_vllm():
    """[FEAT-213] Re-ignite Foyer & vLLM post-training."""
    logger.info("[FEAT-213] Re-igniting Foyer state to OPERATIONAL...")
    try:
        resp = requests.post(f"{FOYER_URL}/status_update", json={"state": "OPERATIONAL"}, timeout=10)
        if resp.status_code == 200:
            logger.info("[FEAT-213] Foyer re-ignited to OPERATIONAL cleanly.")
            return True
    except Exception as e:
        logger.warning(f"[FEAT-213] Re-ignition request error: {e}")
    return False

def run_mass_scan():
    """Execute note scan & gem distillation."""
    logger.info("Executing mass_scan.py --once...")
    scan_script = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/mass_scan.py")
    try:
        res = subprocess.run([sys.executable, scan_script, "--once"], capture_output=True, text=True)
        logger.info(f"mass_scan.py finished with exit code {res.returncode}")
    except Exception as e:
        logger.error(f"mass_scan.py failed: {e}")

def run_unsloth_forge():
    """[FEAT-160] Run Unsloth fine-tuning pass via train_expert.py."""
    logger.info("[FEAT-160] Initiating Unsloth LoRA fine-tuning pass...")
    train_script = os.path.join(BASE_DIR, "forge", "train_expert.py")
    
    if not os.path.exists(DATASET_PATH):
        logger.warning(f"[FEAT-160] Dataset {DATASET_PATH} not found. Skipping LoRA training pass.")
        return
        
    cmd = [sys.executable, train_script, DATASET_PATH, OUTPUT_LORA_DIR, "60"]
    logger.info(f"[FEAT-160] Executing command: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            logger.info("[FEAT-160] LoRA training pass completed successfully.")
        else:
            logger.error(f"[FEAT-160] LoRA training failed with code {res.returncode}: {res.stderr[-300:]}")
    except Exception as e:
        logger.error(f"[FEAT-160] Error executing train_expert.py: {e}")

def main():
    logger.info("=== [FEAT-160/FEAT-213] NIGHTLY FORGE ORCHESTRATION INITIATED ===")
    
    # 1. Ingest Raw Notes
    run_mass_scan()
    
    # 2. Quiesce VRAM
    quiesced = quiesce_vllm()
    
    try:
        # 3. Train LoRA Adapter
        run_unsloth_forge()
    finally:
        # 4. Re-ignite Foyer
        re_ignite_vllm()
        
    logger.info("=== NIGHTLY FORGE ORCHESTRATION COMPLETE ===")

if __name__ == "__main__":
    main()
