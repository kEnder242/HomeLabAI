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

async def run_cycle():
    key = get_key()
    headers = {"X-Lab-Key": key, "Content-Type": "application/json"}
    
    print("\n" + "="*50)
    print("[*] STEP 1: Forcing Premature Hibernation...")
    async with aiohttp.ClientSession() as session:
        # We use a custom reason 'WAKE_TEST' which is NOT 'IDLE_TIMEOUT' 
        # so the Attendant allows it even during the boot grace period.
        async with session.post(f"{ATTENDANT_URL}/hibernate", headers=headers, json={"reason": "WAKE_TEST"}) as r:
            res = await r.json()
            if res.get("status") == "deferred":
                print(f"[!] Hibernation deferred: {res.get('message')}. Waiting 30s...")
                await asyncio.sleep(30)
                return False
            print(f"[+] Hibernation signal accepted: {res.get('message')}")

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
                    if msg.get("type") == "chat" and "SUCCESS" in str(msg.get("content", "")).upper():
                        print("[+] SUCCESS: Engine is vocal.")
                        vocal_received = True
                        break
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
        print(f"\n--- ITERATION {i}/3 ---")
        if await run_cycle():
            passes += 1
        else:
            print(f"[!] Iteration {i} failed. Breaking for analysis.")
            break
    
    print(f"\n[*] Hardening Complete: {passes}/3 passes.")

if __name__ == "__main__":
    asyncio.run(main())
