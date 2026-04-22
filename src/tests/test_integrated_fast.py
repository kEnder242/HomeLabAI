import asyncio
import os
import sys
import json
from pathlib import Path
import subprocess
import time

# Add project src to path
sys.path.append(os.path.abspath("HomeLabAI/src"))

FAST_PROMPT_FILE = Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/refined_prompts_FAST.jsonl"
FAST_DATASET_FILE = Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/cli_voice_dataset_FAST.jsonl"

async def run_fast_integrated_test():
    print("[INIT] Starting FAST Integrated Induction Test...")
    
    # 1. Create a single-item queue
    dummy_task = {"prompt": "[INTEGRATION_TEST]: Explain the importance of the Sovereign Silence hardening."}
    with open(FAST_PROMPT_FILE, "w") as f:
        f.write(json.dumps(dummy_task) + "\n")
    print(f"[DATA] Created fast queue with 1 item: {FAST_PROMPT_FILE}")

    # 2. Clear old test results
    if FAST_DATASET_FILE.exists():
        os.remove(FAST_DATASET_FILE)

    # 3. Create a temporary version of dream_voice.py with the patched paths
    script_path = "HomeLabAI/src/forge/dream_voice_FAST.py"
    with open("HomeLabAI/src/forge/dream_voice.py", "r") as f:
        content = f.read()
    
    patched_content = content.replace(
        'REFINED_PROMPTS = EXPERTISE_DIR / "refined_prompts.jsonl"',
        f'REFINED_PROMPTS = Path("{FAST_PROMPT_FILE}")'
    ).replace(
        'VOICE_DATASET = EXPERTISE_DIR / "cli_voice_dataset.jsonl"',
        f'VOICE_DATASET = Path("{FAST_DATASET_FILE}")'
    )
    
    with open(script_path, "w") as f:
        f.write(patched_content)
    
    print(f"[EXEC] Spawning patched dream_voice_FAST.py...")
    # Add PYTHONPATH to env
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath("HomeLabAI/src")
    
    # Trigger 1 item synthesis
    proc = subprocess.Popen([sys.executable, script_path, "1"], env=env)
    
    print("[WAIT] Waiting for LLM to wake up and generate...")
    # Give it 300 seconds for the LLM to prime and respond
    start = time.time()
    found = False
    while time.time() - start < 300:
        if FAST_DATASET_FILE.exists():
            with open(FAST_DATASET_FILE, "r") as f:
                out = f.read().strip()
                if "[INTEGRATION_TEST]" in out:
                    print("\n[SUCCESS] LLM Output Received:")
                    print(out)
                    found = True
                    break
        time.sleep(5)
    
    proc.terminate()
    if not found:
        print("[FAIL] Timeout waiting for LLM output. Verify that AcmeLab (Port 8765) is running.")

if __name__ == "__main__":
    asyncio.run(run_fast_integrated_test())
