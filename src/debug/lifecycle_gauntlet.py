#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lifecycle Gauntlet (Shakedown Protocol v1.0)
[FEAT-210] Automated Verification of the 01:00 AM - 04:00 AM sequence.

Executes a 1-sample pass of the entire induction pipeline.
"""

import asyncio
import logging
import sys
from pathlib import Path

# --- Configuration ---
LOG_LEVEL = logging.INFO
SCRIPTS_DIR = Path.home() / "Dev_Lab/HomeLabAI/src/forge"
DEBUG_DIR = Path.home() / "Dev_Lab/HomeLabAI/src/debug"

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - [GAUNTLET] %(levelname)s - %(message)s",
)

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
            if stdout:
                # Log last line of success
                last_line = stdout.decode().strip().split('\n')[-1]
                logging.info(f"Result: {last_line}")
            return True
        else:
            logging.error(f"[FAIL] {name} exited with code {proc.returncode}")
            logging.error(f"Error: {stderr.decode()}")
            return False
    except Exception as e:
        logging.error(f"[CRITICAL] {name} execution failed: {e}")
        return False

async def main():
    logging.info("Initiating Lifecycle Gauntlet Shakedown...")
    
    # Check dependencies
    if not (SCRIPTS_DIR / "serial_harvest.py").exists():
        logging.error("Essential scripts missing. Aborting.")
        return

    results = []

    # 1. Step 1: Nightly Dialogue
    results.append(await run_step("Dialogue (Local Weights)", [
        str(DEBUG_DIR / "shakedown_dialogue.py")
    ]))

    # 2. Step 2: Nightly Recruiter
    # (Omit for gauntlet to save time, or use a mock)

    # 3. Step 3: Hierarchy Refactor
    # (Requires running lab)

    # 4. Step 4: Serial Harvest (1 sample)
    results.append(await run_step("Serial Harvest (Bones)", [
        str(SCRIPTS_DIR / "serial_harvest.py"), "--limit=1"
    ]))

    # 5. Step 5: Dream Pass (1 sample)
    results.append(await run_step("Dream Pass (Voice)", [
        str(SCRIPTS_DIR / "dream_voice.py"), "1"
    ]))

    # Summary
    passed = all(results)
    logging.info("=" * 40)
    logging.info(f"GAUNTLET SUMMARY: {'PASS' if passed else 'FAIL'}")
    logging.info("=" * 40)

if __name__ == "__main__":
    asyncio.run(main())
