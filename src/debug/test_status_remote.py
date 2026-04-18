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
    key = get_key()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Monitor console for the "NetworkError"
        logs = []
        page.on("console", lambda msg: logs.append(f"[JS] {msg.text}"))
        
        # 1. Navigate to Status page
        print(f"[*] Navigating to {STATUS_URL}")
        await page.goto(STATUS_URL)
        
        # 2. Wait for Vitals to load (Proves pollStatus worked and keys are set)
        print("[*] Waiting for vital sync...")
        await page.wait_for_selector("#vram-status:not(:text('0.0%'))", timeout=15000)
        
        # 3. Trigger 'Quiesce' (Pause)
        print("[*] Triggering QUIESCE via UI...")
        # Handle the confirmation dialog automatically
        page.on("dialog", lambda dialog: dialog.accept())
        
        # Use selector to find the button with 'Pause' text
        pause_btn = page.locator("text=Pause")
        await pause_btn.click()
        
        # 4. Monitor Console for Success/Failure
        print("[*] Monitoring for remote response...")
        found_success = False
        found_error = False
        
        for _ in range(10):
            content = await page.content()
            # Check the virtual console in the UI
            console_text = await page.inner_text("#sys-console")
            
            if "[ATTENDANT]" in console_text:
                print("[+] SUCCESS: Remote control signal acknowledged by Attendant!")
                found_success = True
                break
            
            if "[ERROR] Remote Control failed" in console_text:
                print("[-] FAILURE: Reproduced the Remote Control error.")
                found_error = True
                break
                
            await asyncio.sleep(1)
            
        if not found_success and not found_error:
            print("[-] TIMEOUT: No response from Remote Control action.")
        
        # Dump logs if it failed
        if found_error:
            print("\n--- Forensic UI Logs ---")
            for log in logs[-5:]:
                print(log)

        await browser.close()
        return found_success

if __name__ == "__main__":
    asyncio.run(run_remote_control_simulation())
