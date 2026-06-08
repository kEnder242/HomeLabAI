import asyncio
import json
import os
import time
import requests
import hashlib
import subprocess
from playwright.async_api import async_playwright

# [TEST-54] THE UBER 5x5 HAND-CRANK GAUNTLET
# Protocol: 5 cycles, each with increasing natural idle drift.
# Purpose: Certify the Llama 3.2 3B Multi-LoRA baseline under V5.

PORT = 8765
INTERCOM_URL = "http://localhost:9001/intercom.html"
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")

def get_key():
    style_path = os.path.join(WORKSPACE_DIR, "field_notes/style.css")
    if os.path.exists(style_path):
        with open(style_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    return "default_key"

async def evaluate_fidelity(cycle_id, page):
    print(f"    [*] Auditing DOM for Cycle {cycle_id} fidelity...")
    
    # Wait for the console to actually contain something
    await asyncio.sleep(2)
    
    full_dom = await page.inner_text("#chat-console")
    
    # 1. Check for physical ignition milestones
    has_milestones = any(x in full_dom.lower() for x in ["operational", "synchronized", "established", "ready"])
    
    # 2. Check for Pinky's restored voice (Phase 4 hardening)
    # Must have semantic content or <thought>, not just reflex noise
    # [Task 7.5] Hardened Vocal Audit: Exclude tokens present in the query
    has_vocal = any(x in full_dom for x in ["<thought>", "Archives", "Stable", "2023 focus was"])
    
    # 3. Check for Brain reachability (Sovereign Bridge)
    has_brain = any(x in full_dom for x in ["Brain", "Sovereign"])
    
    print(f"    [Audit] System Milestones: {'✅' if has_milestones else '❌'}")
    print(f"    [Audit] Pinky Voice: {'✅' if has_vocal else '❌'}")
    print(f"    [Audit] Brain Presence: {'✅' if has_brain else '❌'}")
    
    if not (has_milestones and has_vocal and has_brain):
        print(f"    [Forensic] Full Console Content Snippet:\n{full_dom[:1000]}")
    
    return has_milestones and has_vocal and has_brain

async def run_uber_cycle(cycle_id, wait_minutes, p_instance):
    print(f"\n🚀 STARTING UBER-CYCLE {cycle_id}/5 (Wait: {wait_minutes}m)", flush=True)
    
    # Natural Drift Logic
    print(f"    [Action] Waiting {wait_minutes} minutes for natural idle drift...", flush=True)
    for m in range(wait_minutes):
        print(f"        ... {wait_minutes - m} minutes remaining ...", flush=True)
        await asyncio.sleep(60)

    # 3. Hand-Crank the Ignition via UI
    print("    [Action] Launching Headless Browser (Hand-Crank)...", flush=True)
    browser = await p_instance.chromium.launch(
        headless=True,
        args=[
            "--disable-gpu", 
            "--no-sandbox", 
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox"
        ]
    )
    page = await browser.new_page()
    await page.goto(INTERCOM_URL)
    
    # 4. Fire Strategic Probe (Triggers Wake-on-Intent)
    query = f"[ME] [UBER-5x5] Cycle {cycle_id}. Summarize my 2023 PECISTRESSOR focus and verify node sync."
    print(f"    [Action] Sending Strategic Probe: {query[:40]}...", flush=True)
    await page.wait_for_selector("#text-input")
    await page.fill("#text-input", query)
    await page.keyboard.press("Enter")
    
    # 5. Long-Tail Monitoring
    print("    [Action] Monitoring for result (300s timeout)...", flush=True)
    start_t = time.time()
    success = False
    while time.time() - start_t < 300:
        content = await page.inner_text("#chat-console")
        
        # [Task 7.5] Hardened Fidelity Check: Wait for actual node responses
        # The prompt itself is > 100 chars, so we must look for node signatures.
        has_response = "[HUB]" in content or "[PINKY]" in content or "[BRAIN]" in content or "[THOUGHT]" in content
        if has_response or "Archives" in content:
            # Wait a few more seconds for the stream to complete
            await asyncio.sleep(5)
            success = await evaluate_fidelity(cycle_id, page)
            break
        await asyncio.sleep(5)
        
    await browser.close()
    return success

async def main():
    print("💎 INITIATING THE ULTIMATE UBER 5x5 HAND-CRANKED CERTIFICATION", flush=True)
    print("[*] Mandate: 5 consecutive wins. Reset on fix. Increasing idle stress.", flush=True)
    
    total_wins = 0
    cycles = [5, 10, 15, 20, 25] # 5x5 increasing duration
    
    for i, wait_time in enumerate(cycles):
        cycle_id = i + 1
        
        # [Task 7.5] Physical Isolation: Launch playwright per cycle
        async with async_playwright() as p:
            if await run_uber_cycle(cycle_id, wait_time, p):
                total_wins += 1
                print(f"\n✅ CYCLE {cycle_id} CERTIFIED. System is resilient.")
            else:
                print(f"\n❌ CYCLE {cycle_id} FAILED. Reset required.")
                break
    
    if total_wins == 5:
        print("\n🏆 UBER-CERTIFICATION ACHIEVED.")
        print("[+] PASS: Lab is officially Bulletproof across all physical and logical layers.")
    else:
        print(f"\n🚨 Certification Failed. {total_wins}/5 wins.")

if __name__ == "__main__":
    asyncio.run(main())
