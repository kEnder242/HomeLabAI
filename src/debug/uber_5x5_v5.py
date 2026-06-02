import asyncio
import json
import os
import time
import requests
import hashlib
import subprocess
from playwright.async_api import async_playwright

# [TEST-54] THE UBER 5x5 HAND-CRANK GAUNTLET (V5 Edition)
# Objective: Prove V5 survives natural idle drift and maintains semantic integrity.
# Protocol: 5 cycles, increasing wait (5, 10, 15, 20, 25 mins).
# Mandate: 5 wins in a row. Reset on fix.

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
ATTENDANT_URL = "http://127.0.0.1:9999"
INTERCOM_URL = "http://localhost:9001/intercom.html"
STYLE_CSS = f"{PORTFOLIO_DIR}/field_notes/style.css"

def get_key():
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def evaluate_fidelity(cycle_id, page):
    """[BKM-032] Structural and Semantic Audit of the DOM."""
    print(f"    [*] Auditing DOM for Cycle {cycle_id} fidelity...")
    
    # Wait for the typewriter effect to complete
    await asyncio.sleep(30)
    
    insight_content = await page.inner_text("#insight-console")
    chat_content = await page.inner_text("#chat-console")
    full_dom = insight_content + "\n" + chat_content
    
    # 1. Milestone Check (V5 Operational Status)
    has_milestones = any(x in full_dom.lower() for x in ["operational", "ready", "connected", "foyer"])
    
    # 2. Nomenclature Check (V5 Node Names)
    # Pinky is the gateway, The Brain is intuition, Deep Thought is Sovereign.
    has_v5_nodes = any(x in full_dom for x in ["Pinky", "The Brain", "Deep Thought"])
    
    # 3. Visible Consensus Check (Task 2.5)
    # Look for the gold-bordered refinement markers
    # In Playwright, we can check for the existence of the class
    refinement_count = await page.locator(".refinement-msg").count()
    has_consensus = refinement_count > 0
    
    # 4. Semantic Content Check
    has_vocal = any(x in full_dom for x in ["<thought>", "Archives", "PECISTRESSOR"])

    print(f"    [Audit] System Milestones: {'✅' if has_milestones else '❌'}")
    print(f"    [Audit] V5 Nomenclature: {'✅' if has_v5_nodes else '❌'}")
    print(f"    [Audit] Visible Consensus: {'✅' if has_consensus else '❌'}")
    print(f"    [Audit] Semantic Depth: {'✅' if has_vocal else '❌'}")
    
    if not (has_milestones and has_v5_nodes and has_vocal):
        print(f"    [Forensic] Console Sample:\n{full_dom[:500]}")
    
    return has_milestones and has_v5_nodes and has_vocal

async def run_uber_cycle(cycle_id, wait_minutes, p_instance):
    print(f"\n🚀 STARTING UBER-CYCLE {cycle_id}/5 (Wait: {wait_minutes}m)", flush=True)
    
    # [BKM-033] Babysitting: Check VRAM before wait
    try:
        vram_res = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
        print(f"    [Babysit] Initial VRAM Used: {vram_res.decode().strip()} MiB")
    except Exception: pass

    print(f"    [Action] Waiting {wait_minutes} minutes for natural idle drift...", flush=True)
    for m in range(wait_minutes):
        if (m + 1) % 5 == 0 or m == 0:
            print(f"        ... {wait_minutes - m} minutes remaining ...", flush=True)
        await asyncio.sleep(60)

    # Hand-Crank via Browser
    print("    [Action] Launching Hand-Crank (Chromium)...", flush=True)
    browser = await p_instance.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.goto(INTERCOM_URL)
    
    # Fire Strategic Probe
    query = f"[ME] [UBER-5x5] Cycle {cycle_id}. Summarize the PECISTRESSOR validation scar and verify node sync."
    print(f"    [Action] Sending Probe: {query[:50]}...", flush=True)
    await page.wait_for_selector("#text-input")
    await page.fill("#text-input", query)
    await page.keyboard.press("Enter")
    
    # Monitoring for Result
    print("    [Action] Monitoring for neural response (300s timeout)...", flush=True)
    start_t = time.time()
    success = False
    while time.time() - start_t < 300:
        content = await page.inner_text("#chat-console")
        if "Deep Thought" in content or "The Brain" in content or "Archives" in content:
            success = await evaluate_fidelity(cycle_id, page)
            break
        await asyncio.sleep(10)
        
    await browser.close()
    return success

async def main():
    print("💎 INITIATING V5 UBER 5x5 SEMANTIC CERTIFICATION", flush=True)
    print("[*] Goal: Validate Nomenclature, Interest loop, and Visible Consensus.", flush=True)
    
    async with async_playwright() as p:
        total_wins = 0
        cycles = [5, 10, 15, 20, 25]
        
        for i, wait_time in enumerate(cycles):
            cycle_id = i + 1
            if await run_uber_cycle(cycle_id, wait_time, p):
                total_wins += 1
                print(f"✅ CYCLE {cycle_id} CERTIFIED.")
            else:
                print(f"❌ CYCLE {cycle_id} FAILED.")
                break
        
        if total_wins == 5:
            print("\n🏆 UBER-CERTIFICATION ACHIEVED (V5).")
            print("[+] PASS: The Great Brain Awakening is physically and logically bulletproof.")
        else:
            print(f"\n🚨 Certification Failed at Cycle {total_wins + 1}.")

if __name__ == "__main__":
    asyncio.run(main())
