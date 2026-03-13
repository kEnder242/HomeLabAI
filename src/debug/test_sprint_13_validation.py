import asyncio
import aiohttp
import json
import os
import psutil
import time

ATTENDANT_URL = "http://localhost:9999"
STATUS_JSON = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/status.json"
PAGER_ACTIVITY_FILE = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json"

async def check_ledger(message_substring):
    if not os.path.exists(PAGER_ACTIVITY_FILE):
        return False
    with open(PAGER_ACTIVITY_FILE, "r") as f:
        ledger = json.load(f)
    for event in reversed(ledger):
        if message_substring in event["message"]:
            return True
    return False

async def validate_sprint_13():
    print("\n--- 🚀 Sprint [SPR-13.0] Validation Gauntlet ---")
    async with aiohttp.ClientSession() as session:
        # 1. Start Lab (Master)
        print("[TEST 1] Lab Ignition (Unified)...")
        payload = {"engine": "VLLM", "model": "UNIFIED", "op_mode": "SERVICE_UNATTENDED"}
        async with session.post(f"{ATTENDANT_URL}/start", json=payload) as r:
            assert r.status == 200
        
        print("Waiting for boot...")
        await asyncio.sleep(10)
        
        # 2. Check Forensic Ledger
        print("[TEST 2] Forensic Ledger Entry...")
        if await check_ledger("Lab Ignition"):
            print("[PASS] Ignition recorded.")
        else:
            print("[FAIL] Ignition missing from ledger.")

        # 3. Check Split Status
        print("[TEST 3] Split Status Model...")
        with open(STATUS_JSON, "r") as f:
            status = json.load(f)
        assert "physical" in status
        assert "logical" in status
        print("[PASS] Status bifurcated.")

        # 4. Auto-Restart Test
        print("[TEST 4] Auto-Restart (Physical Kill)...")
        # Find Hub PID
        hub_pid = None
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = " ".join(proc.info['cmdline'] or [])
                if "acme_lab" in cmdline and "python" in cmdline:
                    hub_pid = proc.info['pid']
                    break
            except: continue
        
        if hub_pid:
            print(f"Killing Hub (PID: {hub_pid})...")
            os.kill(hub_pid, 15)
            print("Waiting for watchdog (15s)...")
            await asyncio.sleep(15)
            
            if await check_ledger("Restarting"):
                print("[PASS] Watchdog detected crash and logged restart.")
            else:
                print("[FAIL] Watchdog silent after kill.")
        else:
            print("[SKIP] Hub not found.")

    print("\n--- ✅ Validation Complete ---")

if __name__ == "__main__":
    asyncio.run(validate_sprint_13())
