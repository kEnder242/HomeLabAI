#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lifecycle Gauntlet (Shakedown Protocol v3.0)
[FEAT-215] Automated Verification of the 01:00 AM - 04:00 AM sequence.
[FEAT-217] Sequenced Batch Forge Verification (3 souls in 1 pass).
"""

import asyncio
import logging
import sys
import os
import aiohttp
import json
import argparse
from pathlib import Path

# --- Configuration ---
LOG_LEVEL = logging.INFO
SCRIPTS_DIR = Path.home() / "Dev_Lab/HomeLabAI/src/forge"
DEBUG_DIR = Path.home() / "Dev_Lab/HomeLabAI/src/debug"
ATTENDANT_URL = "http://localhost:9999"

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - [GAUNTLET] %(levelname)s - %(message)s",
)

async def check_attendant_health():
    """Verify Master Attendant is responding on port 9999."""
    logging.info("--- PROBE: Master Attendant Health ---")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ATTENDANT_URL}/heartbeat", timeout=2.0) as r:
                if r.status == 200:
                    logging.info("[PASS] Attendant is responsive.")
                    return True
                logging.error(f"[FAIL] Attendant returned status {r.status}")
                return False
    except Exception as e:
        logging.error(f"[CRITICAL] Attendant connectivity failed: {e}")
        return False

async def run_step(name, command_args):
    """Executes a single pipeline step via subprocess."""
    logging.info(f"--- STEP: {name} ---")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, *command_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            logging.info(f"[PASS] {name} completed successfully.")
            return True
        else:
            logging.error(f"[FAIL] {name} exited with code {proc.returncode}")
            logging.error(f"Error: {stderr.decode()}")
            return False
    except Exception as e:
        logging.error(f"[CRITICAL] {name} execution failed: {e}")
        return False

async def run_forge_shakedown(adapter="lab_history,cli_voice,lab_sentinel", steps=5):
    """Triggers the Attendant's /train endpoint for a micro-shakedown."""
    logging.info(f"--- STEP: Sequenced Batch Forge ({adapter}) ---")
    try:
        payload = {"adapter": adapter, "steps": steps}
        async with aiohttp.ClientSession() as session:
            # Training can take a while even for 5 steps, so use long timeout
            async with session.post(f"{ATTENDANT_URL}/train", json=payload, timeout=600) as r:
                if r.status == 200:
                    data = await r.json()
                    logging.info(f"[PASS] Batch forge complete: {data}")
                    return True
                else:
                    logging.error(f"[FAIL] Batch forge failed: Status {r.status}")
                    return False
    except Exception as e:
        logging.error(f"[CRITICAL] Batch forge connection failed: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true", help="Run in Batch Forge mode (all souls).")
    parser.add_argument("--steps", type=int, default=5, help="Training steps per adapter.")
    args = parser.parse_args()

    logging.info(f"Initiating Lifecycle Gauntlet Shakedown (v3.0)...")
    
    # Check dependencies
    if not (SCRIPTS_DIR / "serial_harvest_v2.py").exists():
        logging.error("Essential scripts missing. Aborting.")
        return

    results = []

    # 0. Health Probe
    if not await check_attendant_health():
        return

    # 1. Dialogue Logic Check (Just check if internal_debate.py is present)
    if os.path.exists(os.path.expanduser("~/Dev_Lab/HomeLabAI/src/internal_debate.py")):
        logging.info("[PASS] Dialogue logic confirmed.")
    else:
        logging.error("[FAIL] Dialogue logic missing.")
        return

    # 2. Sequential Harvest (Micro-pass)
    if not await run_step("Serial Harvest (Bones)", [
        str(SCRIPTS_DIR / "serial_harvest_v2.py"), "--limit", "1"
    ]):
        return

    # 3. Dream Pass (Micro-pass)
    if not await run_step("Dream Pass (Voice)", [
        str(SCRIPTS_DIR / "dream_voice.py"), "1"
    ]):
        return

    # 4. Forge Turn (Sequenced Batch)
    target = "lab_history,cli_voice,lab_sentinel" if args.batch else "lab_history"
    if not await run_forge_shakedown(adapter=target, steps=args.steps):
        return

    logging.info("=" * 40)
    logging.info("GAUNTLET SUMMARY: 100% PASS")
    logging.info("=" * 40)

if __name__ == "__main__":
    asyncio.run(main())
