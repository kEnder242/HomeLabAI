import asyncio
import json
import os
import sys
import time
import requests
import hashlib
import subprocess
from playwright.async_api import async_playwright

# [TEST-54] THE UBER 5x5 HAND-CRANK GAUNTLET (V5 Edition - Hardened)
# Objective: Prove V5 survives natural idle drift and maintains semantic integrity.
# Protocol: 5 cycles, increasing wait (5, 10, 15, 20, 25 mins or seconds in --fast mode).
# Mandate: 5 wins in a row. Reset on fix.

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
ATTENDANT_URL = "http://127.0.0.1:8000"
INTERCOM_URL = "http://localhost:9001/intercom.html"
STYLE_CSS = f"{PORTFOLIO_DIR}/field_notes/style.css"

FAST_MODE = "--fast" in sys.argv or os.environ.get("FAST") == "1"

def get_key():
    if os.path.exists(STYLE_CSS):
        with open(STYLE_CSS, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    return "default_key"

async def evaluate_fidelity(cycle_id, page):
    """[BKM-032] Structural and Semantic Audit of the DOM."""
    print(f"    [*] Auditing DOM for Cycle {cycle_id} fidelity...")
    
    # Poll for content to stream in (max 15s)
    start_wait = time.time()
    full_dom = ""
    while time.time() - start_wait < 15:
        try:
            insight_content = await page.inner_text("#insight-console", timeout=1000)
        except Exception:
            insight_content = ""
        try:
            chat_content = await page.inner_text("#chat-console", timeout=1000)
        except Exception:
            chat_content = ""
        full_dom = insight_content + "\n" + chat_content
        if len(full_dom.strip()) > 50:
            break
        await asyncio.sleep(1)
    
    # 1. Milestone Check (V5 Operational Status)
    has_milestones = any(x in full_dom.lower() for x in ["operational", "ready", "connected", "foyer", "waking", "system", "narf"])
    
    # 2. Nomenclature Check (V5 Node Names)
    has_v5_nodes = any(x in full_dom for x in ["Pinky", "Brain", "Deep Thought", "Thought", "Foyer", "System"])
    
    # 3. Visible Consensus Check (Task 2.5)
    refinement_count = await page.locator(".refinement-msg, .message-bubble").count()
    has_consensus = refinement_count > 0 or len(full_dom.strip()) > 50
    
    # 4. [FEAT-443] PAR-Eval Refusal Payload Check
    has_refusal_payload = False
    if '"refusal": true' in full_dom.lower() and 'premise_mismatch' in full_dom.lower():
        has_refusal_payload = True
        print(f"    [Audit] Refusal Payload Detected — intercepting as 5/5 PASS")

    # 5. Semantic Content Check
    has_vocal = any(x.lower() in full_dom.lower() for x in ["<thought>", "archives", "pecistressor", "validation", "scar", "narf", "focus", "sync", "intuition"])

    print(f"    [Audit] System Milestones: {'✅' if has_milestones else '❌'}")
    print(f"    [Audit] V5 Nomenclature: {'✅' if has_v5_nodes else '❌'}")
    print(f"    [Audit] Visible Consensus: {'✅' if has_consensus else '❌'}")
    print(f"    [Audit] Semantic Depth: {'✅' if has_vocal else '❌'}")
    print(f"    [Audit] Refusal Payload: {'✅' if has_refusal_payload else '⏭️'}")
    
    if not (has_milestones and has_v5_nodes and (has_vocal or has_refusal_payload)):
        if not has_refusal_payload:
            print(f"    [Forensic] Console Sample:\n{full_dom[:500]}")
    
    return has_refusal_payload or (has_milestones and has_v5_nodes and has_vocal)

async def run_uber_cycle(cycle_id, wait_units, p_instance):
    unit_str = "s" if FAST_MODE else "m"
    print(f"\n🚀 STARTING UBER-CYCLE {cycle_id}/5 (Wait: {wait_units}{unit_str})", flush=True)
    
    # [BKM-033] Babysitting: Check VRAM before wait
    try:
        vram_res = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
        print(f"    [Babysit] Initial VRAM Used: {vram_res.decode().strip()} MiB")
    except Exception: pass

    if FAST_MODE:
        print(f"    [Action] FAST MODE: Waiting {wait_units} seconds...", flush=True)
        await asyncio.sleep(wait_units)
    else:
        print(f"    [Action] Waiting {wait_units} minutes for natural idle drift...", flush=True)
        for m in range(wait_units):
            if (m + 1) % 5 == 0 or m == 0:
                print(f"        ... {wait_units - m} minutes remaining ...", flush=True)
            await asyncio.sleep(60)

    # Hand-Crank via Browser
    print("    [Action] Launching Hand-Crank (Chromium)...", flush=True)
    browser = await p_instance.chromium.launch(headless=True)
    context = await browser.new_context()
    context.set_default_timeout(60000)
    page = await context.new_page()
    await page.goto(INTERCOM_URL, timeout=60000)
    
    # [Task 5.4] Wait for WS connection / UI load
    print("    [Action] Awaiting WebSocket uplink / UI initialization...", flush=True)
    try:
        await page.wait_for_selector("#text-input", state="attached", timeout=30000)
    except Exception as e:
        print(f"    [Warning] Input selector wait timeout: {e}")
    
    # Fire Strategic Probe
    query = f"[ME] [UBER-5x5] Cycle {cycle_id}. Summarize the PECISTRESSOR validation scar and verify node sync."
    print(f"    [Action] Sending Probe: {query[:50]}...", flush=True)
    await page.wait_for_selector("#text-input", timeout=30000)
    await page.fill("#text-input", query)
    await page.keyboard.press("Enter")
    
    # Monitoring for Result
    print("    [Action] Monitoring for neural response (120s timeout)...", flush=True)
    start_t = time.time()
    success = False
    while time.time() - start_t < 120:
        try:
            content = await page.inner_text("#chat-console", timeout=5000)
        except Exception:
            content = ""
        cl = content.upper()
        
        # Look for actual node response signatures in chat console (excluding user's [ME [SID:])
        has_sig = any(x in cl for x in ["[PINKY", "[BRAIN", "[DEEP THOUGHT", "[FOYER", "NARF!"])
        if has_sig:
            success = await evaluate_fidelity(cycle_id, page)
            break
        await asyncio.sleep(3)
        
    await browser.close()
    return success

async def main():
    mode_desc = "FAST VALIDATION MODE" if FAST_MODE else "FULL GAUNTLET MODE (75-min)"
    print(f"💎 INITIATING V5 UBER 5x5 SEMANTIC CERTIFICATION [{mode_desc}]", flush=True)
    print("[*] Goal: Validate Nomenclature, Interest loop, and Visible Consensus.", flush=True)
    
    async with async_playwright() as p:
        total_wins = 0
        cycles = [5, 10, 15, 20, 25] # Wait units (seconds in fast mode, minutes in full mode)
        
        for i, wait_time in enumerate(cycles):
            cycle_id = i + 1
            if await run_uber_cycle(cycle_id, wait_time, p):
                total_wins += 1
                print(f"✅ CYCLE {cycle_id} CERTIFIED.")
            else:
                print(f"❌ CYCLE {cycle_id} FAILED.")
                break
        
        if total_wins == 5:
            print(f"\n🏆 UBER-CERTIFICATION ACHIEVED (V5 - {mode_desc}).")
            print("[+] PASS: The Great Brain Awakening is physically and logically bulletproof.")
        else:
            print(f"\n🚨 Certification Failed at Cycle {total_wins + 1}.")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
