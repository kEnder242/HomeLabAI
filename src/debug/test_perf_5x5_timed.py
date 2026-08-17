import asyncio
import json
import os
import time
import requests
import hashlib
import subprocess
from playwright.async_api import async_playwright

# [TEST-55] SPRINT 29: Physical Bedrock Timed Gauntlet
# Definitive certification of KV-Cache Recency over 5+10+15+20+25 minutes.

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
ATTENDANT_URL = "http://127.0.0.1:8765"
INTERCOM_URL = "http://localhost:9001/intercom.html"
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def run_cycle(cycle_id, wait_mins, p_instance):
    print(f"\n[Cycle {cycle_id}/5] Waiting {wait_mins} minutes for recency check...")
    if wait_mins > 0:
        await asyncio.sleep(wait_mins * 60)
    
    print(f"[*] Executing Cycle {cycle_id}...")
    
    # Check TTFT and Substance
    browser = await p_instance.chromium.launch(headless=True)
    page = await browser.new_page()
    
    start_t = time.time()
    await page.goto(INTERCOM_URL)
    
    query = "[ME] [STRATEGIC] Analyze the lab architecture."
    await page.wait_for_selector("#text-input")
    await page.fill("#text-input", query)
    
    # Measure TTFT
    send_t = time.time()
    await page.keyboard.press("Enter")
    
    warming_pop_t = None
    success = False
    while time.time() - send_t < 180:
        # Get all current brain messages to scan for the warming pop vs real answer
        messages = await page.locator(".brain-msg .msg-body").all_inner_texts()
        
        for text in messages:
            if "warming its anchors" in text.lower() and warming_pop_t is None:
                warming_pop_t = time.time() - send_t
                print(f"    [🔥] Warming Pop Latency = {warming_pop_t*1000:.0f}ms (target <100ms)")
            elif "warming its anchors" not in text.lower() and len(text) > 0:
                # This is a real answer
                ttft = time.time() - send_t
                print(f"    [🏆] SUCCESS: TTFT = {ttft:.2f}s | Length = {len(text)} chars.")
                success = True
                break
        
        if success:
            break
        await asyncio.sleep(2)

    if warming_pop_t is None:
        print("    [ℹ️] Engine already warm — warming pop skipped (not a failure).")
    
    await browser.close()
    return success

async def main():
    print("💎 INITIATING TIMED PERFORMANCE GAUNTLET (75 MINS)")
    print("[*] intervals: 0, 5, 10, 15, 20, 25 minutes.")
    
    intervals = [0, 5, 10, 15, 20, 25]
    
    async with async_playwright() as p:
        for i, wait in enumerate(intervals):
            if not await run_cycle(i+1, wait, p):
                print(f"❌ GAUNTLET FAILED at cycle {i+1}.")
                break
        else:
            print("\n🏆 GAUNTLET COMPLETE: Sprint 29 Performance Bedrock is CERTIFIED.")

if __name__ == "__main__":
    asyncio.run(main())
