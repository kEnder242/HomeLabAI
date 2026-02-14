import asyncio
import aiohttp
import time
import sys
import subprocess
import os
import json

ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "ws://localhost:8765"
STABILITY_GOAL = 300 

async def run_soak():
    async with aiohttp.ClientSession() as session:
        while True:
            print("\n--- 🏃 Starting Stability Marathon v2 ---")
            
            print("[MARATHON] Hard-resetting all silicon...")
            await session.post(f"{ATTENDANT_URL}/hard_reset")
            await asyncio.sleep(5)
            
            print("[MARATHON] Launching Lab (Utilization 0.3)...")
            start_payload = {
                "engine": "vLLM", 
                "disable_ear": False,
                "vllm_utilization": 0.3
            }
            await session.post(f"{ATTENDANT_URL}/start", json=start_payload)
            
            print("[MARATHON] Awaiting READY signal...")
            try:
                async with session.get(f"{ATTENDANT_URL}/status?timeout=180") as resp:
                    status = await resp.json()
                    if not status.get("full_lab_ready"):
                        print(f"[MARATHON] Boot failed. Status: {status}")
                        continue
                    print("[MARATHON] Mind is READY.")
            except Exception as e:
                print(f"[MARATHON] Sync error: {e}")
                continue

            print("[MARATHON] Verifying Pinky Gateway...")
            try:
                import websockets
                async with websockets.connect(HUB_URL) as ws:
                    msg = {"type": "chat", "text": "Ping Pinky"}
                    await ws.send(json.dumps(msg))
                    
                    response_received = False
                    start_t = time.time()
                    while time.time() - start_t < 15:
                        reply = await asyncio.wait_for(ws.recv(), timeout=2)
                        data = json.loads(reply)
                        if data.get("source") == "PINKY":
                            txt = data.get('text', '')[:50]
                            print(f"[PASS] Pinky Handshake: {txt}...")
                            response_received = True
                            break
                    
                    if not response_received:
                        print("[FAIL] Pinky failed to respond.")
                        continue
            except Exception as e:
                print(f"[FAIL] Websocket failed: {e}")
                continue

            print(f"[MARATHON] Beginning {STABILITY_GOAL}s stability soak...")
            soak_start = time.time()
            stable = True
            while time.time() - soak_start < STABILITY_GOAL:
                elapsed = int(time.time() - soak_start)
                print(f"\r[SOAK] {elapsed}/{STABILITY_GOAL}s stable...", end="", flush=True)
                
                try:
                    async with session.get(f"{ATTENDANT_URL}/heartbeat") as h_resp:
                        vitals = await h_resp.json()
                        if not vitals.get("lab_server_running") or vitals.get("last_error"):
                            err = vitals.get('last_error', 'Unknown Crash')
                            print(f"\n[FATAL] Mind collapsed! Error: {err}")
                            stable = False
                            break
                except:
                    pass
                
                await asyncio.sleep(10)
            
            if stable:
                print(f"\n[SUCCESS] Lab reached {STABILITY_GOAL}s of continuous stability!")
                break
            else:
                print("[MARATHON] Rinsing and repeating...")

if __name__ == "__main__":
    asyncio.run(run_soak())
