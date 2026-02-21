import asyncio
import json
import websockets
import time
import aiohttp
import subprocess
import os
import signal

# Configuration
HUB_URL = "ws://localhost:8765"
ATTENDANT_URL = "http://localhost:9999"

async def test_shutdown_resilience():
    """Verifies that the Hub can shut down via native tool flow."""
    print("\n--- 🏁 STARTING SHUTDOWN RESILIENCE TEST [v2.0] ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Start Lab via Attendant
        print("[TEST] Launching Lab via Attendant...")
        await session.post(f"{ATTENDANT_URL}/start", json={"mode": "DEBUG_BRAIN", "disable_ear": True})
        
        # 2. Wait for READY state
        print("[TEST] Waiting for READY state (up to 120s)...")
        ready = False
        start_ready_t = time.time()
        while time.time() - start_ready_t < 120:
            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                    data = await resp.json()
                    if data.get("full_lab_ready"):
                        ready = True
                        break
            except: pass
            await asyncio.sleep(2)
            
        if not ready:
            print("[FAIL] Lab failed to reach READY state.")
            return False

        # 3. Connect and Shutdown
        try:
            async with websockets.connect(HUB_URL) as ws:
                print("[TEST] Connected. Draining buffer...")
                # Drain handshake/status
                try:
                    await asyncio.wait_for(ws.recv(), timeout=5)
                    await asyncio.wait_for(ws.recv(), timeout=5)
                except: pass

                print("[TEST] Triggering shutdown command...")
                await ws.send(json.dumps({"type": "text_input", "content": "Please close the lab."}))
                
                start_t = time.time()
                success = False
                while time.time() - start_t < 60:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=10)
                        data = json.loads(msg)
                        print(f"[RECV] {data.get('brain_source') or data.get('type')}: {data.get('brain')}")
                        if data.get('type') == 'shutdown' or (data.get('brain') and "Closing Lab" in data.get('brain')):
                            success = True
                            break
                    except: continue
                
                if not success:
                    print("[FAIL] Shutdown signal NOT received.")
                    return False

            # 4. Final verification of process termination
            print("[TEST] Verifying Hub termination...")
            await asyncio.sleep(5)
            async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                vitals = await resp.json()
                if not vitals.get("lab_server_running"):
                    print("[PASS] Hub process terminated cleanly.")
                    return True
                else:
                    print("[FAIL] Hub process is STILL RUNNING.")
                    return False

        except Exception as e:
            print(f"[ERROR] Test failed with: {e}")
            return False

if __name__ == "__main__":
    if asyncio.run(test_shutdown_resilience()):
        print("--- ✅ SHUTDOWN RESILIENCE VERIFIED ---")
        exit(0)
    else:
        print("--- ❌ SHUTDOWN RESILIENCE FAILED ---")
        exit(1)
