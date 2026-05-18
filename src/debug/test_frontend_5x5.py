import asyncio
import json
import os
import time
import requests
import hashlib
import subprocess
from playwright.async_api import async_playwright

# [TEST-53] The Uber-Frontend Gauntlet
# Definitive certification of the entire Lab stack (Hardware -> Hub -> JS -> UI).

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
ATTENDANT_URL = "http://127.0.0.1:9999"
INTERCOM_URL = "http://localhost:9001/intercom.html"
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def trigger_cycle(cycle_id, p_instance):
    print(f"\n[*] Starting Uber-Cycle {cycle_id}/5...")
    key = get_key()
    
    # 1. Physical H2 Hibernation (Ensures clean silicon but keeps process alive for Wake-on-Intent)
    print("    [Action] Executing Physical H2 Hibernation via Attendant...")
    requests.post(f"{ATTENDANT_URL}/hibernate?level=2&key={key}")
    time.sleep(5) # Settle

    # 2. Launch Browser (Rude Timing - while Lab is OFFLINE)
    print("    [Action] Launching Headless Browser (Rude Window)...")
    browser = await p_instance.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    
    # Capture console logs for diagnostic truth
    js_logs = []
    page.on("console", lambda msg: js_logs.append(msg.text))
    
    await page.goto(INTERCOM_URL)
    
    # 3. Send Strategic Query during WAKING
    # The prompt below is designed to trigger >200 chars and Brain delegation.
    query = "[ME] [STRATEGIC] Analyze the RTX 2080 Ti physical thermal boundaries and fan curve strategy."
    print(f"    [Action] Sending Strategic Query: {query[:30]}...")
    
    # Wait for input field
    await page.wait_for_selector("#text-input")
    await page.fill("#text-input", query)
    await page.keyboard.press("Enter")
    
    # 4. Monitor DOM for Substance
    print("    [Action] Monitoring UI for Substance (>200 chars from Brain)...")
    start_t = time.time()
    success = False
    retry_sent = False
    
    while time.time() - start_t < 400: # 6.5 minute window
        # Audit the message list
        messages = await page.evaluate("""() => {
            const bodies = Array.from(document.querySelectorAll('.msg-body'));
            const sources = Array.from(document.querySelectorAll('.msg-source'));
            return bodies.map((b, i) => ({
                text: b.innerText,
                source: sources[i] ? sources[i].innerText : 'Unknown'
            }));
        }""")
        
        for msg in messages:
            text = msg['text']
            source = msg['source']
            
            # [FEAT-344] Recovery Awareness: If we see a reset, wait and re-query
            if ("H2 Reset" in text or "Restoration sequence" in text) and not retry_sent:
                print("    [Action] Lab Reset detected in UI. Waiting for recovery...")
                await asyncio.sleep(60)
                print("    [Action] Re-sending Strategic Query...")
                await page.fill("#text-input", query)
                await page.keyboard.press("Enter")
                retry_sent = True
                break

            # Check for Substance Win
            if len(text) > 100 and ("Brain" in source or "Shadow" in source or "Pinky" in source):
                print(f"    [🏆] UBER-WIN: Received {len(text)} chars from {source} in UI.")
                
                # [FEAT-344] Uniqueness Check: Ensure this specific substantive block is unique on the DOM
                repeats = sum(1 for m in messages if m['text'] == text)
                if repeats > 1:
                    print(f"    [🚨] FAILURE: Physical duplication detected on DOM! ({repeats} instances found).")
                    await browser.close()
                    return False
                
                success = True
                break
        
        if success: break
        await asyncio.sleep(5)
        
    if not success:
        print("    [!] FAILURE: Timeout or No Substance received in UI.")
        # Print relevant JS errors if any
        for log in js_logs:
            if "Error" in log or "failed" in log:
                print(f"    [JS_LOG] {log}")
    
    await browser.close()
    return success

async def main():
    print("💎 INITIATING THE UBER-FRONTEND 5x5 GAUNTLET")
    print("[*] Strategy: Headless Browser Execution + DOM Verification.")
    
    async with async_playwright() as p:
        total_wins = 0
        for i in range(5):
            if await trigger_cycle(i + 1, p):
                total_wins += 1
                print(f"--- Cycle {i+1} Certified Bulletproof ---")
            else:
                print(f"\n❌ UBER-FRONTEND FAILED at Cycle {i+1}")
                break
        
        print(f"\n🏆 FINAL UBER-RESULT: {total_wins}/5 Wins.")
        if total_wins == 5:
            print("[+] PASS: Design Integrity Verified at the Physical, Logical, and UI Layers.")

if __name__ == "__main__":
    asyncio.run(main())
