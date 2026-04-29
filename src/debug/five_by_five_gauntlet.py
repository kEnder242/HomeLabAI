import asyncio
import json
import websockets
import os
import time
import requests
import sys
from playwright.async_api import async_playwright

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
WS_URL = "ws://127.0.0.1:8765"
HB_URL = "http://127.0.0.1:9999/heartbeat"
STATUS_URL = "http://localhost:9001/intercom.html"

async def get_style_key():
    import hashlib
    with open("/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css", "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def wait_for_engine_ready():
    print("[*] Pre-Flight: Waiting for vLLM engine to become physically vocal (Max 600s)...")
    start_t = time.time()
    while time.time() - start_t < 600:
        try:
            r = requests.get("http://127.0.0.1:8088/v1/models", timeout=2)
            if r.status_code == 200:
                print("[+] Engine is VOCAL. Proceeding with gauntlet.")
                return True
        except Exception:
            pass
        await asyncio.sleep(5)
    return False

async def run_single_check(iteration=1):
    print(f"\n[================ FIVE-BY-FIVE: CHECK {iteration} ================]")
    if not await wait_for_engine_ready():
        print("[!] FATAL: Engine never reached vocal state.")
        return False

    style_key = await get_style_key()
    
    # 1. Force Hibernate (Honest Wait)
    print("[*] Forcing Lab into HIBERNATION (Waiting 30s for VRAM offload)...")
    try:
        r = requests.post("http://127.0.0.1:9999/hibernate", headers={"X-Lab-Key": style_key}, json={"reason": "5x5_TEST"})
        print(f"[*] Hibernate Request: {r.json().get('message')}")
        await asyncio.sleep(30)
    except Exception as e:
        print(f"[!] Failed to hibernate: {e}")

    # 2. Verify UI State via Playwright
    print("[*] Launching Intercom UI...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        js_logs = []
        page.on("console", lambda msg: js_logs.append(msg.text))
        
        await page.goto(STATUS_URL)
        await asyncio.sleep(5) # Let JS connect

        # 3. Trigger Wake from UI
        print("[*] Triggering WAKE intent via UI...")
        await page.fill("#text-input", "[ME] Wake up, we have work.")
        await page.press("#text-input", "Enter")

        # 4. Monitor for vLLM Logs in Crosstalk
        print("[*] Monitoring Intercom for Live vLLM Logs (90s window)...")
        start_t = time.time()
        success = False
        vllm_seen = False
        disconnects = 0
        
        while time.time() - start_t < 90:
            current_logs = list(js_logs) # Snapshot
            js_logs.clear() # Clear to prevent re-reading
            
            for log in current_logs:
                if "Disconnected" in log or "failed" in log.lower():
                    disconnects += 1
                if "[vLLM]" in log or "Application startup complete" in log:
                    vllm_seen = True
                    print(f"    [UI LOG] {log}")
                if "Strategic Sovereignty: PRIMARY" in log or "Mind is OPERATIONAL" in log:
                    print(f"    [UI LOG] {log}")
                    if vllm_seen:
                        success = True
                        break
            
            if success:
                break
            await asyncio.sleep(2)
            
        await browser.close()
        
        if disconnects > 2:
            print(f"[!] FAILURE: Flapping detected ({disconnects} disconnects).")
            return False
            
        if not vllm_seen:
            print("[!] FAILURE: Hub survived, but vLLM logs never reached the UI.")
            return False
            
        if not success:
            print("[!] FAILURE: Lab never reached OPERATIONAL state.")
            return False
            
        print(f"[+] WIN {iteration}: Lobby is persistent and vLLM logs are visible.")
        return True

if __name__ == "__main__":
    it = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    passed = asyncio.run(run_single_check(it))
    if not passed:
        sys.exit(1)
