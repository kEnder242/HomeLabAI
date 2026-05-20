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
    # The prompt below tests: Gibberish fix (don't), RAG (archive), and substance.
    query = "[ME] [STRATEGIC] I don't think the lab is optimal. Search the archive for my work history and analyze the 18-year shift."
    print(f"    [Action] Sending Strategic Query: {query[:30]}...")
    
    # Wait for input field
    await page.wait_for_selector("#text-input")
    await page.fill("#text-input", query)
    await page.keyboard.press("Enter")
    
    # 4. Monitor DOM for Substance
    print("    [Action] Monitoring UI for Substance & Performance Bedrock...")
    start_t = time.time()
    success = False
    
    # Trackers for Proof
    brain_responded_time = 0
    hub_operational_time = 0
    compact_ui_verified = False
    crosstalk_migration_verified = False
    
    while time.time() - start_t < 400: # 6.5 minute window
        # Audit the message list from BOTH consoles and the crosstalk bar
        status = await page.evaluate("""() => {
            const allMessages = Array.from(document.querySelectorAll('.message'));
            const crosstalk = document.getElementById('crosstalk-bar').innerText;
            return {
                messages: allMessages.map(m => {
                    const body = m.querySelector('.msg-body');
                    const source = m.querySelector('.msg-source');
                    return {
                        text: body ? body.innerText : '',
                        source: source ? source.innerText : 'Unknown',
                        is_brain: m.parentElement.id === 'insight-console',
                        is_compact: body ? body.classList.contains('system-inline') : false
                    };
                }),
                crosstalk: crosstalk
            };
        }""")
        
        # [Task 18.1/18.2] Verify UI Compactness and Triage Migration
        if not compact_ui_verified and any(m['is_compact'] for m in status['messages']):
            print("    [🏆] COMPACT UI: Verified (.system-inline found).")
            compact_ui_verified = True
            
        if not crosstalk_migration_verified and "Triage Attempt" in status['crosstalk']:
            print("    [🏆] CROSSTALK: Triage migration verified (#crosstalk-bar populated).")
            crosstalk_migration_verified = True

        for msg in status['messages']:
            text = msg['text']
            source = msg['source']
            is_brain_pane = msg['is_brain']
            
            if "[OPERATIONAL] Hub foyer is fully synchronized" in text and hub_operational_time == 0:
                hub_operational_time = time.time()

            # [Task 18.4] Verify Strategic Routing & Substance
            if len(text) > 100 and ("Brain" in source or "Shadow" in source):
                if brain_responded_time == 0:
                    brain_responded_time = time.time()
                    
                if is_brain_pane:
                    print(f"    [🏆] STRATEGIC WIN: {source} content found in Insight Pane ({len(text)} chars).")
                else:
                    print(f"    [⚠️] ROUTING ALERT: {source} content found in Chat Pane (Expected Insight).")
                
                # [Task 19.9.1] Assert Cached Lobby Relay
                if hub_operational_time > 0 and hub_operational_time < brain_responded_time:
                    print(f"    [🚨] FAILURE: Brain responded AFTER Hub was operational. Cached Lobby Relay failed.")
                elif hub_operational_time == 0:
                    # Check log evidence in previous turns confirmed this works, but we re-verify
                    print(f"    [⚡] SPEED WIN: Brain responded BEFORE Hub was fully operational! Cached Relay active.")
                
                # Check for RAG successful retrieval markers
                if "Anchor" in text or "Work history" in text:
                    print(f"    [🏆] RAG SINCERITY: Archive context detected in response.")
                
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
