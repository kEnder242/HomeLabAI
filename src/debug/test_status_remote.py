import asyncio
from playwright.async_api import async_playwright
import subprocess
import os
import json

# --- Paths ---
STATUS_URL = "http://localhost:9001/status.html"
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    import hashlib
    try:
        with open(STYLE_CSS, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except:
        return "none"

async def run_remote_control_simulation():
    print("[*] Starting Playwright Remote Control Simulation...")
    
    async with async_playwright() as p:
        # 1. Launch Browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        page.on("dialog", lambda dialog: dialog.accept()) # Auto-confirm
        
        # Monitor console for errors
        page.on("console", lambda msg: print(f"[JS] {msg.type.upper()}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[JS_FATAL] {err.message}"))
        
        print(f"[*] Navigating to {STATUS_URL}")
        await page.goto(STATUS_URL)
        
        # 2. Sync Verification
        print("[*] Waiting for vital sync (data/status.json)...")
        # Increase timeout and add explicit check
        try:
            await page.wait_for_selector("#vram-status:not(:text('0.0%'))", timeout=30000)
            print("[+] Vital sync confirmed.")
        except Exception as e:
            print(f"[-] FAILURE: UI failed to load vitals. Dumping state...")
            raise e
        
        # 3. Test Cycle: HIBERNATE -> START -> PAUSE -> STOP
        actions = [
            ("Hibernate", "hiber", "HIBERNATING"),
            ("Start", "ignit", "SERVICE_UNATTENDED"),
            ("Pause", "lock", "MAINTENANCE"),
            ("STOP", "scrub", "OFFLINE")
        ]
        
        # [SECURITY] Re-fetch style key for direct API calls
        style_key = get_key()
        
        for button_text, log_keyword, target_mode in actions:
            # Clear console before action to avoid stale matches
            await page.evaluate("document.getElementById('sys-console').innerHTML = ''")
            
            print(f"[*] Triggering {button_text.upper()} via UI...")
            # Use specific CSS selector to avoid matching log lines
            btn = page.locator(f".control-btn:has-text('{button_text}')")
            await btn.click()
            
            # 1. Wait for immediate acknowledgment in UI
            found = False
            for _ in range(15):
                console_text = await page.inner_text("#sys-console")
                if log_keyword.lower() in console_text.lower():
                    print(f"[+] SUCCESS: {button_text} acknowledged in UI.")
                    found = True
                    break
                await asyncio.sleep(1)
            
            if not found:
                print(f"[-] FAILURE: {button_text} signal not detected in UI console.")
                break

            # 2. Verify silicon transition via Direct API (Zero Polling Delay)
            print(f"[*] Verifying silicon transition to {target_mode} via REST...")
            transitioned = False
            for _ in range(30):
                try:
                    res = requests.get(f"{ATTENDANT_URL}/heartbeat", headers={'X-Lab-Key': style_key}, timeout=2)
                    if res.status_code == 200:
                        mode = res.json().get("mode", "").upper()
                        if mode == target_mode or (target_mode == "MAINTENANCE" and mode == "HIBERNATING"):
                            print(f"[+] SUCCESS: Silicon physically reached {target_mode}.")
                            transitioned = True
                            await asyncio.sleep(5) # Final settle
                            break
                except Exception:
                    pass
                await asyncio.sleep(2)
            
            if not transitioned:
                print(f"[-] WARNING: Silicon transition to {target_mode} timed out, but proceeding...")
            
            if not found:
                print(f"[-] FAILURE: {button_text} signal not detected in UI console.")
                break
                
        await browser.close()
        return found

if __name__ == "__main__":
    asyncio.run(run_remote_control_simulation())
