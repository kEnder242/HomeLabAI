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
        res = subprocess.check_output(
            ["nvidia-smi", "--query-compute-apps=used_memory", "--format=csv,noheader"],
            text=True
        )
        return sum(int(x.replace("MiB", "").strip()) for x in res.strip().split("\n") if x.strip())
    except:
        return 0

async def run_cycle(iteration):
    key = get_key()
    headers = {"X-Lab-Key": key, "Content-Type": "application/json"}
    
    print(f"\n" + "="*50)
    print(f"--- ITERATION {iteration}/3 ---")
    
    # [FEAT-265.28] Physical Settle: Wait for VOCAL baseline before starting cycle
    print("[*] STEP 0: Verifying Vocal Baseline...")
    for _ in range(24): # 120s max
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ATTENDANT_URL}/status", headers=headers, timeout=1.0) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get("engine_up") and data.get("foyer_up"):
                            print("[+] Lab is ACTIVE and ready for transition.")
                            break
        except Exception:
            pass
        print("  [*] Waiting for active baseline...")
        await asyncio.sleep(5)

    # 1. Force Premature Hibernation
    print("[*] STEP 1: Forcing Premature Hibernation...")
    async with aiohttp.ClientSession() as session:
        for _ in range(12): # 60s max retry
            async with session.post(f"{ATTENDANT_URL}/hibernate", headers=headers, json={"reason": "WAKE_TEST"}) as r:
                res = await r.json()
                if res.get("status") == "deferred":
                    print(f"  [!] Hibernation deferred: {res.get('message')}. Retrying in 5s...")
                    await asyncio.sleep(5)
                    continue
                print(f"[+] Hibernation signal accepted: {res.get('message')}")
                break
        else:
            print("[-] FAILURE: Hibernation remained deferred for 60s.")
            return False

    print("[*] STEP 2: Waiting for VRAM decay (< 1500MB)...")
    decayed = False
    for i in range(24): # 120s max
        vram = await get_vram()
        print(f"  [*] Current VRAM: {vram}MB")
        if vram < 1500:
            print("[+] Silicon cleared. Lab is in Deep Sleep.")
            decayed = True
            break
        await asyncio.sleep(5)
    
    if not decayed:
        print("[-] FAILURE: VRAM failed to decay.")
        return False

    print("[*] STEP 3: Triggering Sovereign Wake via Intent...")
    # [FEAT-265.20] Boot Patience: Wait for Hub Foyer to open
    foyer_up = False
    for _ in range(12): # 60s max wait for foyer
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8765/heartbeat", timeout=1.0) as r:
                    if r.status == 200:
                        print("[+] Hub Foyer is OPEN and listening.")
                        foyer_up = True
                        break
        except Exception:
            pass
        print("  [*] Waiting for Hub foyer to initialize...")
        await asyncio.sleep(5)
    
    if not foyer_up:
        print("[-] FAILURE: Hub foyer failed to open.")
        return False

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(HUB_URL) as ws:
            payload = {"type": "text_input", "content": "[ME] Stress test: Wake up!"}
            await ws.send_json(payload)
            print("[*] Query sent. Monitoring for 'Warming' crosstalk...")
            
            start_t = time.time()
            vocal_received = False
            while time.time() - start_t < 180: # 180s for vLLM restore
                try:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=10)
                    if msg.get("type") == "crosstalk" and "warming" in msg.get("brain", "").lower():
                        print("[+] Hub acknowledged intent and sparked Attendant.")
                    if msg.get("type") == "chat" and ("SUCCESS" in str(msg.get("content", "")).upper() or "OPERATIONAL" in str(msg.get("content", "")).upper()):
                        vram_now = await get_vram()
                        if vram_now > 5000:
                            print(f"[+] SUCCESS: Engine is vocal and VRAM is resident ({vram_now}MB).")
                            vocal_received = True
                            break
                        else:
                            print(f"  [*] Vocal detected, but weights still loading ({vram_now}MB)...")
                except asyncio.TimeoutError:
                    vram = await get_vram()
                    print(f"  [*] Waiting... Current VRAM: {vram}MB")
                    if vram > 5000:
                        print("[+] VRAM returned to active levels.")
                except Exception as e:
                    print(f"[!] Socket Error: {e}")
                    break
            
            if not vocal_received:
                print("[-] FAILURE: No vocal response received.")
                return False

    vram_final = await get_vram()
    print(f"[*] Final VRAM State: {vram_final}MB")
    if vram_final > 5000:
        print("[+] FULL PASS: Lifecycle transition verified.")
        return True
    else:
        print("[-] FAILURE: VRAM did not return to active baseline.")
        return False

async def main():
    print("[*] Starting Hibernation Iterative Hardening...")
    passes = 0
    for i in range(1, 4): # Run 3 cycles
        if await run_cycle(i):
            passes += 1
        else:
            print(f"[!] Iteration {i} failed. Breaking for analysis.")
            break
    
    print(f"\n[*] Hardening Complete: {passes}/3 passes.")

if __name__ == "__main__":
    asyncio.run(main())
