import asyncio
import os
import sys
import json
from pathlib import Path

# Add project src to path
sys.path.append(os.path.abspath("HomeLabAI/src"))

PROMPT_FILE = Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/refined_prompts.jsonl"

async def run_integrated_test():
    print("[INIT] Starting Integrated Induction Test...")
    
    # 1. Populate a dummy prompt if empty (or just add one)
    dummy_task = {"prompt": "[INTEGRATION_TEST]: Explain the importance of the Sovereign Silence hardening."}
    with open(PROMPT_FILE, "a") as f:
        f.write(json.dumps(dummy_task) + "\n")
    print(f"[DATA] Injected dummy prompt into {PROMPT_FILE}")

    # 2. Trigger the cycle
    # Since we can't easily hook into the running process's memory, 
    # we'll run a standalone acme_lab instance in TEST mode
    from acme_lab import AcmeLab
    
    # Use a different port to avoid conflict with live lab
    lab = AcmeLab()
    lab.status = "READY"
    lab.engine_ready.set()
    
    print("[EXEC] Calling run_full_induction_cycle()...")
    # This will trigger dream_voice.py
    await lab.run_full_induction_cycle()
    
    print("[DONE] Integrated cycle complete. Check cli_voice_dataset.jsonl for new output.")

if __name__ == "__main__":
    # We must patch os.open to avoid singleton conflict
    from unittest.mock import patch
    with patch('os.open', return_value=999):
        with patch('os.fdopen'):
            asyncio.run(run_integrated_test())
