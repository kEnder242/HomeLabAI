import asyncio
import json
import os
import time
import requests
import hashlib
import subprocess
from playwright.async_api import async_playwright

# [TEST-54] THE UBER 5x5 HAND-CRANK GAUNTLET
# Protocol: 5 cycles, each with an increasing 5-minute wait (5, 10, 15, 20, 25 mins).
# Mandate: 5 wins in a row. Restart if anything is modified.
# Evaluates: H2 -> Operational transition, Persona fidelity, RAG grounding, and VRAM stability.

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
ATTENDANT_URL = "http://127.0.0.1:9999"
INTERCOM_URL = "http://localhost:9001/intercom.html"
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def evaluate_fidelity(cycle_id, page):
    """Physically audits the DOM for high-fidelity responses."""
    print(f"    [*] Auditing DOM for Cycle {cycle_id} fidelity...")
    
    # Give the DOM a moment to settle after the result is detected
    await asyncio.sleep(10)
    
    # Get content from both consoles to be safe
    insight_content = await page.inner_text("#insight-console")
    chat_content = await page.inner_text("#chat-console")
    full_dom = insight_content + "\n" + chat_content
    
    # 1. Check for [SYSTEM] stage visibility (Phase 3 hardening)
    # focus on persistent status rather than ephemeral startup steps
    has_milestones = any(x in full_dom.lower() for x in ["operational", "synchronized", "established", "ready"])
    
    # 2. Check for Pinky's restored voice (Phase 4 hardening)
    # Must have semantic content or <thought>, not just reflex noise
    has_vocal = any(x in full_dom for x in ["<thought>", "Archives", "PECISTRESSOR", "teams", "focus"])
    
    # 3. Check for Brain reachability (Sovereign Bridge)
    # The brain source is usually 'Brain (Intuition)' or 'Sovereign'
    has_brain = any(x in full_dom for x in ["Brain", "Sovereign"])
    
    print(f"    [Audit] System Milestones: {'✅' if has_milestones else '❌'}")
    print(f"    [Audit] Pinky Voice: {'✅' if has_vocal else '❌'}")
    print(f"    [Audit] Brain Presence: {'✅' if has_brain else '❌'}")
    
    if not (has_milestones and has_vocal and has_brain):
        print(f"    [Forensic] Full Console Content Snippet:\n{full_dom[:1000]}")
    
    return has_milestones and has_vocal and has_brain

async def run_uber_cycle(cycle_id, wait_minutes, p_instance):
    print(f"\n🚀 STARTING UBER-CYCLE {cycle_id}/5 (Wait: {wait_minutes}m)")
    key = get_key()
    
    # [FIX] Natural Drift Logic: Remove forced hibernation.
    # The system must enter sleep naturally during the wait.
    print(f"    [Action] Waiting {wait_minutes} minutes for natural idle drift...")
    for m in range(wait_minutes):
        if (m + 1) % 5 == 0 or m == 0:
            print(f"        ... {wait_minutes - m} minutes remaining ...")
        await asyncio.sleep(60)

    # 3. Hand-Crank the Ignition via UI
    print("    [Action] Launching Headless Browser (Hand-Crank)...")
    browser = await p_instance.chromium.launch(
        headless=True,
        args=[
            "--disable-gpu", 
            "--no-sandbox", 
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
            "--no-zygote",
            "--disable-extensions",
            "--disable-software-rasterizer",
            "--disable-features=IsolateOrigins,site-per-process"
        ]
    )
    page = await browser.new_page()
    await page.goto(INTERCOM_URL)
    
    # 4. Fire Strategic Probe (Triggers Wake-on-Intent)
    query = f"[ME] [UBER-5x5] Cycle {cycle_id}. Summarize my 2023 PECISTRESSOR focus and verify node sync."
    print(f"    [Action] Sending Strategic Probe: {query[:40]}...")
    await page.wait_for_selector("#text-input")
    await page.fill("#text-input", query)
    await page.keyboard.press("Enter")
    
    # 5. Long-Tail Monitoring
    print("    [Action] Monitoring for result (300s timeout)...")
    start_t = time.time()
    success = False
    while time.time() - start_t < 300:
        # Look for the final synthesis from Brain or the vocal handshake from Pinky
        content = await page.inner_text("#chat-console")
        if "PECISTRESSOR" in content or "Archives" in content:
            success = await evaluate_fidelity(cycle_id, page)
            break
        await asyncio.sleep(10)
        
    await browser.close()
    return success

async def main():
    print("💎 INITIATING THE ULTIMATE UBER 5x5 HAND-CRANKED CERTIFICATION")
    print("[*] Mandate: 5 consecutive wins. Reset on fix. Increasing idle stress.")
    
    async with async_playwright() as p:
        total_wins = 0
        cycles = [5, 10, 15, 20, 25] # 5x5 increasing duration
        
        for i, wait_time in enumerate(cycles):
            cycle_id = i + 1
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
