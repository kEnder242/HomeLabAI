import asyncio
import os
import time
import requests
import json

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
VLLM_LOG = os.path.join(LAB_DIR, "vllm_server.log")
ATTENDANT_URL = "http://127.0.0.1:9999"

async def test_vllm_crash_recovery():
    print("[#] Starting vLLM Crash Recovery Verification [FEAT-308]")
    
    # 1. Capture Initial State
    try:
        hb = requests.get(f"{ATTENDANT_URL}/heartbeat").json()
        initial_recovery_count = hb.get("recovery_attempts", 0)
        print(f"[+] Initial Recovery Count: {initial_recovery_count}")
    except Exception as e:
        print(f"[!] Attendant not reachable: {e}")
        return

    # 2. Inject Fake Traceback
    print("[#] Injecting fake traceback into vllm_server.log...")
    with open(VLLM_LOG, "a") as f:
        f.write("\nTraceback (most recent call last):\n")
        f.write("  File \"vllm/v1/engine/core_client.py\", line 569, in __init__\n")
        f.write("RuntimeError: MOCK ENGINE CRASH FOR TESTING FEAT-308\n")
        f.flush()
        os.fsync(f.fileno())
    
    print("[#] Waiting 10s for Pulse Loop detection (Disk I/O Sync)...")
    await asyncio.sleep(10)
    
    # 3. Verify Trigger
    try:
        hb = requests.get(f"{ATTENDANT_URL}/heartbeat").json()
        new_recovery_count = hb.get("recovery_attempts", 0)
        print(f"[+] New Recovery Count: {new_recovery_count}")
        
        if new_recovery_count > initial_recovery_count:
            print("[+] SUCCESS: Pulse Loop detected the crash and incremented recovery count.")
            
            # 4. Check for Forensic Snip
            crash_logs = [f for f in os.listdir(os.path.join(LAB_DIR, "logs")) if f.startswith("crash_")]
            if crash_logs:
                print(f"[+] SUCCESS: Forensic Snip found: {crash_logs[-1]}")
            else:
                print("[!] FAILURE: No forensic snip found in logs/ directory.")
        else:
            print("[!] FAILURE: Recovery count did not increment.")
            
    except Exception as e:
        print(f"[!] Verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_vllm_crash_recovery())
