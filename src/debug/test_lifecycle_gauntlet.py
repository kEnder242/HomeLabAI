import asyncio
import aiohttp
import subprocess
import time
import os
import json
import pytest
import websockets

ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "ws://localhost:8765"

async def pinky_handshake(ws, label="HANDSHAKE"):
    print(f"[TEST] Sending PULSE_CHECK...")
    await ws.send(json.dumps({"type": "handshake"}))
    await asyncio.wait_for(ws.recv(), timeout=15)
    print("[PASS] Pulse confirmed.")

    # THE PRE-FILL POKE
    print(f"[TEST] Sending {label} (Targeted Poke)...")
    # Using a literal command to reduce LLM reasoning 'think time'
    await ws.send(json.dumps({"type": "chat", "text": "Just say 'Poit!', nothing else."}))
    
    start_t = time.time()
    while time.time() - start_t < 120: # 2 Minute Silicon Limit
        try:
            reply = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(reply)
            if data.get("source") == "PINKY":
                print(f"[SUCCESS] Pinky Woke Up: {data.get('text')}")
                return True
        except asyncio.TimeoutError:
            print(f"[{int(time.time() - start_t)}s] still resonates...", end="\r", flush=True)
    return False

@pytest.mark.asyncio
async def test_scenario_3_cold_start():
    print("\n--- 🏁 Scenario 3: Cold Start (The 2-Min Poke) ---")
    async with aiohttp.ClientSession() as session:
        print("[TEST] Silicon Purge...")
        await session.post(f"{ATTENDANT_URL}/hard_reset")
        await asyncio.sleep(5)
        
        print("[TEST] Triggering Start...")
        await session.post(f"{ATTENDANT_URL}/start", json={"engine": "vLLM", "disable_ear": False})
        # Wait for the blocking ready event
        await session.get(f"{ATTENDANT_URL}/status?timeout=180")

        async with websockets.connect(HUB_URL) as ws:
            await ws.recv() # Welcome
            await asyncio.sleep(10) # Settling time
            if await pinky_handshake(ws, "COLD_WAKE"):
                print("[SUCCESS] Cold start win achieved.")
            else:
                pytest.fail("Pinky remained silent after 2 minutes of cold load.")

if __name__ == "__main__":
    asyncio.run(test_scenario_3_cold_start())
