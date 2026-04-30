import asyncio
import json
import os
import time
import requests
import sys
from playwright.async_api import async_playwright

# [FEAT-318] Hardened 5x5 Infrastructure
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
ATTENDANT_URL = "http://127.0.0.1:9999"
STATUS_URL = "http://localhost:9001/intercom.html"

# Task 20.4: Auth Stability
# Use the same key used in previous turns
LAB_KEY = "92e785ba"

async def get_lab_status():
    try:
        r = requests.get(f"{ATTENDANT_URL}/status", headers={"X-Lab-Key": LAB_KEY}, timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

async def wait_for_quiescence():
    print("[*] Stability Gate: Waiting for silicon quiescence...")
    while True:
        status = await get_lab_status()
        if status:
            remaining = status.get("quiescence_remaining", 0)
            if remaining <= 0:
                print("[+] Silicon is QUIESCENT. Proceeding.")
                return True
            print(f"    [WAIT] Quiescence window active: {remaining}s remaining...")
        else:
            print("[!] Warning: Attendant unreachable. Retrying...")
        await asyncio.sleep(5)

async def wait_for_engine_ready():
    print("[*] Pre-Flight: Waiting for vLLM engine to become physically vocal (Max 600s)...")
    start_t = time.time()
    while time.time() - start_t < 600:
        try:
            # Check port 8088 directly for vLLM status
            r = requests.get("http://127.0.0.1:8088/v1/models", timeout=2)
            if r.status_code == 200:
                print("[+] Engine is VOCAL.")
                return True
        except Exception:
            pass
        await asyncio.sleep(5)
    return False

async def run_single_check(iteration=1):
    print(f"\n[================ FIVE-BY-FIVE: CHECK {iteration} ================]")
    
    # 0. Pre-Flight Check
    if not await wait_for_engine_ready():
        print("[!] FATAL: Engine never reached vocal state.")
        return False

    # 1. Force Hibernate
    print("[*] Forcing Lab into HIBERNATION...")
    try:
        r = requests.post(f"{ATTENDANT_URL}/hibernate", headers={"X-Lab-Key": LAB_KEY}, json={"reason": "5x5_STRESS_TEST"})
        print(f"[*] Hibernate Request: {r.json().get('message')}")
        # Wait for VRAM to clear
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[!] Failed to hibernate: {e}")
        return False

    # 2. Wait for Stability Window (FEAT-318)
    await wait_for_quiescence()

    # 3. Verify UI State via Playwright
    print("[*] Launching Intercom UI...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Task 20.2: Log Queue Implementation
        log_queue = asyncio.Queue()
        page.on("console", lambda msg: log_queue.put_nowait(msg.text))
        
        await page.goto(STATUS_URL)
        await asyncio.sleep(5) # Let JS connect

        # 4. Trigger Wake from UI
        print("[*] Triggering WAKE intent via UI...")
        await page.fill("#text-input", "[ME] Wake up, we have work.")
        await page.press("#text-input", "Enter")

        # 5. Task 20.3: Progress-Aware Monitoring
        print("[*] Monitoring Intercom for Activity (Dynamic Timeout)...")
        start_t = time.time()
        timeout_limit = 120 # Base 2 minute window
        success = False
        vllm_seen = False
        disconnects = 0
        
        while time.time() - start_t < timeout_limit:
            try:
                # Non-blocking pull from queue
                log = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                
                if "Disconnected" in log or "failed" in log.lower():
                    disconnects += 1
                
                if "[vLLM]" in log or "Application startup complete" in log:
                    if not vllm_seen:
                        print("    [PROGRESS] vLLM Log Stream Detected. Extending timeout...")
                        vllm_seen = True
                        timeout_limit += 30 # Extension for slow silicon
                    print(f"    [UI LOG] {log}")
                
                if "Strategic Sovereignty: PRIMARY" in log or "Mind is OPERATIONAL" in log:
                    print(f"    [UI LOG] {log}")
                    if vllm_seen:
                        success = True
                        break
            except asyncio.TimeoutError:
                continue # No log line this second
            
        await browser.close()
        
        if disconnects > 3: # Relaxed slightly for mobile/proxy latency
            print(f"[!] FAILURE: Flapping detected ({disconnects} disconnects).")
            return False
            
        if not vllm_seen:
            print("[!] FAILURE: Hub survived, but vLLM logs never reached the UI.")
            return False
            
        if not success:
            print("[!] FAILURE: Lab never reached OPERATIONAL state.")
            return False
            
        print(f"[+] WIN {iteration}: Lobby persistent, Logs visible, State OPERATIONAL.")
        return True

async def main():
    print("--- 🏁 Five-By-Five Stability Gauntlet Starting ---")
    wins = 0
    intervals = [300, 600, 900, 1200, 1500] # 5, 10, 15, 20, 25 mins
    
    for i in range(5):
        it = i + 1
        passed = await run_single_check(it)
        
        if passed:
            wins += 1
            if wins == 5:
                print("\n[🏆] GAUNTLET COMPLETE: 5/5 SUCCESS.")
                sys.exit(0)
            
            wait_time = intervals[i]
            print(f"\n[WAIT] Pass {it} successful. Waiting {wait_time}s before next cycle...")
            await asyncio.sleep(wait_time)
        else:
            print(f"\n[!] GAUNTLET FAILED at cycle {it}. Terminating.")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
