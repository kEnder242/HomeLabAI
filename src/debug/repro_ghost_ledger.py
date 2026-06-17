import json
import os
import time
import requests
import subprocess
import sys
import psutil

# [FEAT-322] Shadow Deadlock Reproduction Harness v3 (PORT PERSISTENCE)
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
LEDGER_PATH = os.path.join(LAB_DIR, "run/active_pids.json")
ATTENDANT_URL = "http://127.0.0.1:8765"
LAB_KEY = "92e785ba"

def start_ghost_hub():
    print("[*] Phase 1: Spawning Ghost Port listener...")
    # Use a simple netcat listener to hold the Hub port (8765)
    # This simulates a process that is NOT the Lab but occupies the port.
    proc = subprocess.Popen(["nc", "-l", "8765"], start_new_session=True)
    print(f"[+] Ghost Port Listener (nc) spawned with PID: {proc.pid}")
    return proc

def inject_ghost_ledger(ghost_pid):
    print("[*] Phase 2: Injecting Ghost Ledger...")
    ledger = {
        "authority": {
            "token": "GHOST_TOKEN",
            "timestamp": "2026-01-01 00:00:00",
            "boot_hash": "DEAD"
        },
        "inventory": {
            "hub_pid": ghost_pid,
            "engine_pid": None,
            "engine_mode": "VLLM",
            "family": []
        }
    }
    
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)
    print(f"[+] Ghost Ledger written with Hub PID: {ghost_pid}")

def restart_attendant():
    print("[*] Phase 3: Restarting Lab Attendant Service...")
    subprocess.run(["sudo", "systemctl", "restart", "lab-attendant"])
    print("[+] Service restarted. Waiting for initial boot sequence...")
    time.sleep(10)

def verify_resolution():
    print("[*] Phase 4: Verifying Authority Validation...")
    try:
        r = requests.get(f"{ATTENDANT_URL}/status", headers={"X-Lab-Key": LAB_KEY}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            foyer_up = data.get("foyer_up")
            reason = data.get("reason")
            
            # If the fix works:
            # Attendant should see PID (nc) in ledger, check its cmdline, 
            # find it lacks "acme_lab", WIPE the ledger entry, 
            # and foyer_up should be FALSE (because /heartbeat on nc will fail).
            
            print(f"    [STATUS] Foyer Up: {foyer_up}")
            print(f"    [STATUS] Reason: {reason}")
            
            if not foyer_up:
                print("\n[🏆] SUCCESS: Attendant rejected the Ghost PID and correctly reported foyer DOWN.")
                return True
            else:
                print("\n[!] FAILURE: Attendant accepted the Ghost PID (or netcat actually replied?)")
                return False
    except Exception as e:
        print(f"[!] Error contacting Attendant: {e}")
        return False

if __name__ == "__main__":
    ghost_proc = start_ghost_hub()
    try:
        inject_ghost_ledger(ghost_proc.pid)
        restart_attendant()
        if verify_resolution():
            sys.exit(0)
        else:
            sys.exit(1)
    finally:
        print("[*] Cleaning up ghost process...")
        ghost_proc.terminate()
        try:
            ghost_proc.wait(timeout=2)
        except:
            ghost_proc.kill()
