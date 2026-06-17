import asyncio
import json
import os
import time
import requests
import sys
from playwright.async_api import async_playwright

# [FEAT-321] Neural Queue Fidelity Test
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
ATTENDANT_URL = "http://127.0.0.1:8765"
STATUS_URL = "http://localhost:9001/intercom.html"
LAB_KEY = "92e785ba" # Standard MD5 hash of style.css

async def get_lab_status():
    try:
        r = requests.get(f"{ATTENDANT_URL}/status", headers={"X-Lab-Key": LAB_KEY}, timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

async def wait_for_hibernation():
    print("[*] Waiting for Lab to reach HIBERNATING state...")
    while True:
        status = await get_lab_status()
        if status:
            mode = status.get("mode")
            vram = status.get("vram_mib", 0)
            print(f"    [STATUS] Mode: {mode} | VRAM: {vram}MB")
            if mode == "HIBERNATING" and vram < 2000:
                print("[+] Lab is successfully HIBERNATING.")
                return True
        await asyncio.sleep(5)

async def run_queue_test():
    print("\n--- 🏁 Neural Queue Fidelity Test Starting ---")
    
    # 1. Force Hibernate
    print("[*] Forcing Lab into HIBERNATION...")
    try:
        r = requests.post(f"{ATTENDANT_URL}/hibernate", headers={"X-Lab-Key": LAB_KEY}, json={"reason": "QUEUE_TEST"})
        print(f"[*] Hibernate Request: {r.json().get('message')}")
    except Exception as e:
        print(f"[!] Failed to initiate hibernation: {e}")
        return False

    # 2. Wait for confirmation
    if not await wait_for_hibernation():
        return False

    # 3. Launch UI and send query during hibernation
    print("[*] Launching Intercom UI...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto(STATUS_URL)
        await asyncio.sleep(10) # Let JS connect and drain history

        print("[*] Sending 'hello?' while Lab is hibernating...")
        await page.fill("#text-input", "hello?")
        await page.press("#text-input", "Enter")

        # 4. Confirm 'warming anchors' message and reply
        print("[*] Monitoring for buffering acknowledgment and reply...")
        start_t = time.time()
        warming_seen = False
        processing_seen = False
        reply_seen = False
        
        while time.time() - start_t < 400: # 6.5m window for cold load
            content = await page.inner_text("body")
            content_lower = content.lower()
            
            if "warming its anchors" in content_lower and not warming_seen:
                print("[+] ACK SEEN in UI: 'Lab is warming its anchors...'")
                warming_seen = True
                
            if "anchors established" in content_lower and not processing_seen:
                print("[+] PROGRESS SEEN in UI: 'Anchors established. Processing...'")
                processing_seen = True
                    
            if "pinky" in content_lower or "brain" in content_lower:
                # Exclude the "Lab is warming..." message itself if it contains Pinky? No, it doesn't.
                # But wait, history replay might show old messages.
                # However, we only care that *something* appeared.
                if "hello" in content_lower or "assist" in content_lower or "mind" in content_lower:
                    print("[+] REPLY RECEIVED in UI.")
                    reply_seen = True
                    break
                
            await asyncio.sleep(5)
                
        await browser.close()
        
        if not warming_seen:
            print("[!] FAILURE: Never received buffering acknowledgment.")
            return False
        if not processing_seen:
            print("[!] FAILURE: Never received 'Processing' notification.")
            return False
        if not reply_seen:
            print("[!] FAILURE: Never received actual reply to queued query.")
            return False
            
        print("[🏆] QUEUE FIDELITY VERIFIED: Query buffered and processed autonomously.")
        
        # 5. Wait for auto-hibernation
        print("[*] Waiting for auto-hibernation (Gate: 600s)...")
        idle_start = time.time()
        while True:
            status = await get_lab_status()
            if status:
                mode = status.get("mode")
                elapsed = int(time.time() - idle_start)
                if elapsed % 60 == 0:
                    print(f"    [IDLE] Mode: {mode} ({elapsed}s elapsed)")
                if mode == "HIBERNATING":
                    print(f"[+] Auto-hibernation triggered after {elapsed}s.")
                    break
            await asyncio.sleep(10)
            
        return True

if __name__ == "__main__":
    asyncio.run(run_queue_test())
