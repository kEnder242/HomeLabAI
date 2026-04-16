import asyncio
import subprocess
import os
import psutil
import time
import requests

# --- Paths ---
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    import hashlib
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

def run_race_test():
    print("[*] Starting Asynchronous Shutdown Race Test...")
    key = get_key()
    
    # 1. Ensure a clean slate
    print("[*] Cleaning environment...")
    subprocess.run(["sudo", "systemctl", "stop", "lab-attendant.service"])
    subprocess.run(["sudo", "fuser", "-k", "8088/tcp", "8765/tcp", "11434/tcp"], stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "systemctl", "start", "lab-attendant.service"])
    time.sleep(5)

    # 2. Trigger Ignition
    print("[*] Triggering VLLM Ignition...")
    url = f"http://localhost:9999/start?key={key}"
    try:
        requests.post(url, json={"engine": "VLLM", "model": "MEDIUM", "reason": "RACE_TEST"}, timeout=2)
    except requests.exceptions.ReadTimeout:
        pass # Expected if it blocks
    
    # 3. IMMEDIATELY Restart the Attendant (The Race)
    print("[*] IMMEDIATELY restarting lab-attendant.service...")
    subprocess.run(["sudo", "systemctl", "restart", "lab-attendant.service"])
    
    # 4. Audit for Ghosts
    print("[*] Auditing for survivors (waiting 10s for service to settle)...")
    time.sleep(10)
    
    # Check if any vLLM process exists
    survivors = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        cmd = " ".join(proc.info['cmdline'] or []).lower()
        if "vllm" in cmd and "python" in cmd:
            survivors.append(proc.info['pid'])
            
    if survivors:
        print(f"[!] GHOST DETECTED: Engine processes {survivors} survived the Attendant restart.")
        print("[!] This proves the Asynchronous Shutdown Race (Scenario 1).")
        return True
    else:
        print("[+] No ghosts found. The shutdown was clean.")
        return False

if __name__ == "__main__":
    run_race_test()
