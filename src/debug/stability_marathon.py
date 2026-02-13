import asyncio
import aiohttp
import time
import sys
import subprocess
import os

ATTENDANT_URL = "http://localhost:9999"
STABILITY_GOAL = 300 

async def run_soak():
    async with aiohttp.ClientSession() as session:
        while True:
            print(f"\n--- 🏃 Starting Stability Marathon (Goal: {STABILITY_GOAL}s) ---")
            
            print("[MARATHON] Resetting silicon...")
            await session.post(f"{ATTENDANT_URL}/hard_reset")
            await asyncio.sleep(5)
            
            print("[MARATHON] Triggering Full-Stack Mind...")
            start_payload = {"engine": "vLLM", "disable_ear": False}
            await session.post(f"{ATTENDANT_URL}/start", json=start_payload)
            
            print("[MARATHON] Awaiting [READY] event (Timeout 180s)...")
            try:
                async with session.get(f"{ATTENDANT_URL}/wait_ready?timeout=180") as resp:
                    if resp.status != 200:
                        print(f"[MARATHON] Boot failed or timed out. Status: {resp.status}")
                        continue
                    print("[MARATHON] Mind is ONLINE. Beginning soak...")
            except Exception as e:
                print(f"[MARATHON] Connection error during wait: {e}")
                continue

            soak_start = time.time()
            stable = True
            while time.time() - soak_start < STABILITY_GOAL:
                elapsed = int(time.time() - soak_start)
                print(f"\r[SOAK] {elapsed}/{STABILITY_GOAL}s stable...", end="", flush=True)
                
                try:
                    async with session.get(f"{ATTENDANT_URL}/status") as s_resp:
                        status = await s_resp.json()
                        if not status.get("lab_server_running") or status.get("last_error"):
                            err = status.get("last_error", "Unknown Crash")
                            print(f"\n[FATAL] Mind collapsed after {elapsed}s! Error: {err}")
                            stable = False
                            break
                except:
                    pass
                
                await asyncio.sleep(10)
            
            if stable:
                print(f"\n[SUCCESS] Lab reached {STABILITY_GOAL}s of continuous stability!")
                break
            else:
                print("[MARATHON] Rinsing and repeating...")

async def final_validation():
    print("\n[MARATHON] Running Final Sanity Test (Pi Flow)...")
    test_path = "/home/jallred/Dev_Lab/HomeLabAI/src/debug/test_pi_flow.py"
    # Ensure PYTHONPATH is set so nodes can be imported correctly
    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/jallred/Dev_Lab/HomeLabAI/src"
    
    res = subprocess.run(["/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3", test_path], 
                         capture_output=True, text=True, env=env)
    if res.returncode == 0:
        print("[PASS] Golden Path verified.")
    else:
        print(f"[FAIL] Golden Path failed:\n{res.stdout}\n{res.stderr}")

if __name__ == "__main__":
    asyncio.run(run_soak())
    asyncio.run(final_validation())
