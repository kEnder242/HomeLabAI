import asyncio
import aiohttp
import subprocess
import time
import json
import os
import hashlib

# --- Config ---
HUB_URL = "http://localhost:8765/hub"
ATTENDANT_URL = "http://localhost:9999"
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    try:
        with open(STYLE_CSS, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except:
        return "none"

async def get_vram():
    try:
        # Get total used VRAM on device 0
        res = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,nounits,noheader"],
            text=True
        )
        return int(res.strip())
    except:
        return 0

async def run_audit_cycle(iteration):
    key = get_key()
    headers = {"X-Lab-Key": key, "Content-Type": "application/json"}
    
    print(f"\n--- CYCLE {iteration} ---")
    
    # 1. Capture Active Baseline
    active_vram = await get_vram()
    print(f"[*] Active VRAM: {active_vram}MB")

    # 2. Hibernate
    print("[*] Transitioning to Sleep...")
    async with aiohttp.ClientSession() as session:
        await session.post(f"{ATTENDANT_URL}/hibernate", headers=headers, json={"reason": "LEAK_AUDIT"})
    
    # Wait for decay
    decayed_vram = 0
    for _ in range(12):
        await asyncio.sleep(5)
        decayed_vram = await get_vram()
        if decayed_vram < 1500:
            break
    print(f"[*] Passive VRAM: {decayed_vram}MB")

    # 3. Wake
    print("[*] Triggering Sovereign Wake...")
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(HUB_URL) as ws:
            await ws.send_json({"type": "text_input", "content": "[ME] Audit ping."})
            # Wait for response
            start_t = time.time()
            while time.time() - start_t < 120:
                msg = await ws.receive_json()
                if msg.get("type") == "chat" and "DIRECT_RESPONSE" in str(msg.get("content", "")):
                    break
    
    # 4. Capture Final Active
    final_active = await get_vram()
    print(f"[*] Post-Wake Active VRAM: {final_active}MB")
    
    return active_vram, decayed_vram, final_active

async def main():
    print("[*] Starting 5-Cycle VRAM Leak Investigation...")
    results = []
    for i in range(1, 6):
        res = await run_audit_cycle(i)
        results.append(res)
        await asyncio.sleep(5) # Settle window

    print("\n" + "="*50)
    print("VRAM LEAK REPORT")
    print("Iteration | Active (MB) | Passive (MB) | Delta (MB)")
    print("-" * 50)
    
    first_passive = results[0][1]
    for i, (act, pas, post) in enumerate(results):
        delta = pas - first_passive
        print(f"  {i+1}       | {act:10} | {pas:11} | {delta:+9}")
    
    total_leak = results[-1][1] - first_passive
    print("-" * 50)
    print(f"Total Drift over 5 cycles: {total_leak} MB")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
