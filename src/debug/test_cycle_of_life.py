import asyncio
import subprocess
import os
import psutil
import time
import requests

# --- Paths ---
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    import hashlib
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def run_cycle_test():
    print("[*] Starting formal Cycle of Life Test...")
    key = get_key()
    base_url = "http://localhost:9999"
    
    # 1. Ensure Online
    print("[*] Stage 1: Ensuring Lab is ONLINE...")
    requests.post(f"{base_url}/start?key={key}", json={"engine": "OLLAMA", "model": "MEDIUM"})
    time.sleep(10)
    
    # 2. Hibernate
    print("[*] Stage 2: Triggering Hibernation...")
    requests.post(f"{base_url}/hibernate?key={key}")
    time.sleep(15)
    used_vram = int(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).strip())
    print(f"    - used VRAM: {used_vram}MB")
    
    # 3. Restart Attendant
    print("[*] Stage 3: Restarting Attendant (Service Continuity Test)...")
    subprocess.run(["sudo", "systemctl", "restart", "lab-attendant.service"])
    time.sleep(5)
    
    # 4. Verify Adoption
    print("[*] Stage 4: Verifying State Adoption...")
    res = requests.get(f"{base_url}/heartbeat").json()
    print(f"    - Adopted Mode: {res.get('mode')}")
    
    # 5. Wake and Vocal Check
    print("[*] Stage 5: Waking and Vocal Verification...")
    requests.post(f"{base_url}/start?key={key}", json={"engine": "OLLAMA", "model": "MEDIUM"})
    time.sleep(10)
    
    # Run query
    proc = subprocess.run([
        "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3", 
        "/home/jallred/Dev_Lab/HomeLabAI/src/debug/test_ws_query.py", 
        "Respond with SUCCESS"
    ], capture_output=True, text=True)
    
    if "SUCCESS" in proc.stdout or "OPERATIONAL" in proc.stdout:
        print("[+] SUCCESS: Cycle of Life completed and verified vocal.")
        return True
    else:
        print("[-] FAILURE: Lab failed to become vocal after cycle.")
        print(proc.stdout)
        return False

if __name__ == "__main__":
    asyncio.run(run_cycle_test())
