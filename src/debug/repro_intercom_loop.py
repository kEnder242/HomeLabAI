import asyncio
from playwright.async_api import async_playwright
import json
import time
import requests

STATUS_URL = "http://localhost:9001/intercom.html"
HB_URL = "http://localhost:9999/heartbeat"

async def repro_loop():
    print("[#] Starting High-Fidelity Intercom Loop Reproduction...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Capture console for forensic evidence
        logs = []
        page.on("console", lambda msg: logs.append(f"[{time.strftime('%H:%M:%S')}] [JS] {msg.text}"))
        
        print(f"[*] Navigating to {STATUS_URL}...")
        await page.goto(STATUS_URL)
        
        # 1. Wait for initial connection
        print("[*] Waiting for WebSocket handshake...")
        await asyncio.sleep(5)
        
        # 2. Trigger Wake
        print("[*] Triggering WAKE query...")
        await page.fill("#text-input", "Wake up, Brain.")
        await page.press("#text-input", "Enter")
        
        # 3. Monitor for 90 seconds
        print("[*] Monitoring for Disconnect Loop (90s window)...")
        start_t = time.time()
        while time.time() - start_t < 90:
            # Check Attendant State
            try:
                hb = requests.get(HB_URL).json()
                print(f"    [SILICON] State: {hb.get('mode')} | Reason: {hb.get('reason')} | Foyer: {hb.get('foyer_up')}")
            except: pass
            
            # Print latest JS logs
            if logs:
                print(logs[-1])
                if "Disconnected" in logs[-1]:
                    print("[!] REPRODUCED: WebSocket disconnected during wake.")
            
            await asyncio.sleep(5)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(repro_loop())
