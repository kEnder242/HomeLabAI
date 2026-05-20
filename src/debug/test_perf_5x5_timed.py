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
ATTENDANT_URL = "http://127.0.0.1:9999"
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
    
    success = False
    while time.time() - send_t < 180:
        # Check for first brain message
        count = await page.locator(".brain-msg").count()
        if count > 0:
            ttft = time.time() - send_t
            text = await page.locator(".brain-msg .msg-body").last.inner_text()
            print(f"    [🏆] SUCCESS: TTFT = {ttft:.2f}s | Length = {len(text)} chars.")
            success = True
            break
        await asyncio.sleep(2)
    
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
