import asyncio
import os
import subprocess
import time
import sys

# [Task 5.4] The Babysitter: Executes the 5x5 Gauntlet and polls output
# This prevents the AI CLI from timing out during the 75-minute wait.

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
VENV_PYTHON = f"{LAB_DIR}/.venv/bin/python3"
TEST_SCRIPT = f"{LAB_DIR}/src/debug/uber_5x5_v5.py"

async def run_and_monitor():
    print("🍼 INITIATING V5 BABYSITTER...")
    
    # 1. Restart the Lab via Systemd
    print("[SYSTEMD] Restarting services (Clean Slate)...")
    os.environ["LAB_SKIP_AUDIT"] = "1"
    subprocess.run(["sudo", "systemctl", "restart", "field-notes.service", "lab-attendant.service"])
    print("[SYSTEMD] Services restarted. Giving Foyer time to bind...")
    await asyncio.sleep(5)
    
    # 2. Launch the 5x5 as a subprocess
    print(f"[BABYSITTER] Launching {TEST_SCRIPT}...")
    process = await asyncio.create_subprocess_exec(
        VENV_PYTHON, TEST_SCRIPT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=LAB_DIR
    )
    
    # 3. Stream output back to the terminal
    while True:
        try:
            line = await process.stdout.readline()
            if line:
                print(line.decode().rstrip(), flush=True)
            elif process.stdout.at_eof():
                break
        except Exception as e:
            print(f"[Babysitter] Stream error: {e}")
            break

                
    await process.wait()
    print(f"\n[BABYSITTER] Gauntlet finished with return code {process.returncode}.")

if __name__ == "__main__":
    asyncio.run(run_and_monitor())
