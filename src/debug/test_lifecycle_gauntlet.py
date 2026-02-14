import asyncio
import aiohttp
import subprocess
import time
import os
import json

ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "ws://localhost:8765"

async def test_scenario_1_preemption():
    """Scenario 1: Pre-emption (Slow Burn -> Interactive)"""
    print("\n--- Scenario 1: Pre-emption ---")
    async with aiohttp.ClientSession() as session:
        print("[TEST] Hard Resetting...")
        await session.post(f"{ATTENDANT_URL}/hard_reset")
        
        print("[TEST] Starting dummy Slow Burn...")
        subprocess.Popen(["sleep", "3600"], start_new_session=True)
        
        print("[TEST] Triggering Lab Start (Pre-emption)...")
        await session.post(f"{ATTENDANT_URL}/start", json={"engine": "OLLAMA"})
        
        print("[TEST] Awaiting READY signal...")
        async with session.get(f"{ATTENDANT_URL}/status?timeout=60") as resp:
            data = await resp.json()
            if data.get("full_lab_ready"):
                print("[PASS] Lab pre-empted and reached READY.")
            else:
                print(f"[FAIL] Lab failed to reach READY. Status: {data}")

async def test_scenario_3_cold_start():
    """Scenario 3: Cold Start Recovery"""
    print("\n--- Scenario 3: Cold Start Recovery ---")
    async with aiohttp.ClientSession() as session:
        print("[TEST] Hard Resetting...")
        await session.post(f"{ATTENDANT_URL}/hard_reset")
        
        print("[TEST] Triggering Cold Start (vLLM)...")
        await session.post(f"{ATTENDANT_URL}/start", json={"engine": "vLLM", "disable_ear": False})
        
        print("[TEST] Verifying blocking wait for residency...")
        start_t = time.time()
        async with session.get(f"{ATTENDANT_URL}/status?timeout=180") as resp:
            data = await resp.json()
            elapsed = time.time() - start_t
            if data.get("full_lab_ready"):
                print(f"[PASS] Cold start synced in {elapsed:.1f}s.")
            else:
                print(f"[FAIL] Cold start failed. Status: {data}")
            
        print("[TEST] Verifying Pinky Handshake...")
        try:
            import websockets
            async with websockets.connect(HUB_URL) as ws:
                # Welcome message
                welcome = await ws.recv()
                print(f"[DEBUG] Hub Handshake: {welcome[:50]}...")
                
                await ws.send(json.dumps({"type": "chat", "text": "Are you awake Pinky?"}))
                
                # Increased timeout for LLM reasoning + ASR lag
                reply = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(reply)
                if data.get("source") == "PINKY":
                    print(f"[PASS] Pinky responded: {data.get('text')[:50]}...")
                else:
                    print(f"[FAIL] Wrong source: {data.get('source')}")
        except Exception as e:
            print(f"[FAIL] Handshake error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    # We only run Scenario 3 since it covers the most ground
    asyncio.run(test_scenario_3_cold_start())
