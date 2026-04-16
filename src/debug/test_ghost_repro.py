import asyncio
import subprocess
import json
import os
import psutil
import time

# --- Paths ---
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
LEDGER_PATH = os.path.join(LAB_DIR, "run/active_pids.json")

async def reproduce_ghost():
    print("[*] Starting Ghost Reproduction Test...")
    
    # 1. Clean Slate
    print("[*] Performing baseline cleanup...")
    subprocess.run(["sudo", "systemctl", "stop", "lab-attendant.service"])
    subprocess.run(["sudo", "fuser", "-k", "8088/tcp", "8765/tcp", "11434/tcp"], stderr=subprocess.DEVNULL)
    
    # 2. Create the "Ghost"
    # We'll spawn a fake process that holds a port or just exists
    print("[*] Spawning the Ghost process (Ollama)...")
    ghost_proc = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5) # Allow it to bind
    print(f"[*] Ghost spawned with PID: {ghost_proc.pid}")
    
    # 3. Corrupt the Ledger (Make Attendant blind)
    print("[*] Corrupting the PID ledger...")
    with open(LEDGER_PATH, "w") as f:
        json.dump({"hub_pid": 99999, "engine_pid": 88888, "engine_mode": "VLLM"}, f)
        
    # 4. Start the Attendant
    print("[*] Starting Lab Attendant with blind state...")
    subprocess.run(["sudo", "systemctl", "start", "lab-attendant.service"])
    
    # 5. Monitor for Watchdog intervention
    print("[*] Monitoring for autonomous Watchdog recovery (waiting 30s)...")
    for i in range(12):
        time.sleep(5)
        # Check if the ghost PID is still alive
        if not psutil.pid_exists(ghost_proc.pid):
            print("[+] SUCCESS: Watchdog detected and reaped the Ghost process!")
            return True
        print(f"    - Attempt {i+1}/12: Ghost {ghost_proc.pid} still alive...")
        
    print("[-] FAILURE: Watchdog failed to reap the ghost in time.")
    return False

if __name__ == "__main__":
    asyncio.run(reproduce_ghost())
