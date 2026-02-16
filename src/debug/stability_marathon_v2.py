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
        print("\n--- 🏃 Starting Optimized Stability Marathon v2 ---")
        
        print("[MARATHON] Hard-resetting all silicon...")
        await session.post(f"{ATTENDANT_URL}/hard_reset")
        await asyncio.sleep(5)
        
        print("[MARATHON] Launching Lab (Llama-3.2-3B Tuning)...")
        # Ensure we target Llama specifically
        start_payload = {
            "engine": "vLLM", 
            "model": "llama-3.2-3b-awq",
            "mode": "SERVICE_UNATTENDED",
            "disable_ear": True
        }
        await session.post(f"{ATTENDANT_URL}/start", json=start_payload)
        
        print("[MARATHON] Awaiting READY signal...")
        try:
            boot_start = time.time()
            booted = False
            while time.time() - boot_start < 180: # Increased timeout just in case
                async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                    status = await resp.json()
                    
                    # EARLY EXIT: Failure check
                    if status.get("last_error"):
                        print(f"\n[FATAL] Boot failed! Error: {status.get('last_error')}")
                        return False
                    
                    # EARLY EXIT: Success check
                    if status.get("full_lab_ready"):
                        booted = True
                        break
                    
                    # Progress reporting
                    vllm_state = "RUNNING" if status.get("vllm_running") else "INIT"
                    lab_state = "UP" if status.get("lab_server_running") else "DOWN"
                    print(f"   [WAIT] vLLM: {vllm_state} | Lab: {lab_state} (Elapsed: {int(time.time()-boot_start)}s)")
                
                await asyncio.sleep(5)
            
            if not booted:
                print("\n[MARATHON] Boot failed or timed out.")
                return False
            print("\n[MARATHON] Mind is READY.")
        except Exception as e:
            print(f"\n[MARATHON] Sync error: {e}")
            return False

        print("[MARATHON] Verifying Pinky Gateway...")
        try:
            import websockets
            async with websockets.connect(HUB_URL) as ws:
                await ws.send(json.dumps({"type": "handshake", "version": "3.5.0"}))
                await ws.send(json.dumps({"type": "text_input", "content": "Narf! Vibe check!"}))
                
                response_received = False
                start_t = time.time()
                while time.time() - start_t < 30:
                    reply = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(reply)
                    if "brain" in data:
                        txt = data.get('brain', '')[:50]
                        print(f"[PASS] Pinky Response: {txt}...")
                        response_received = True
                        break
                
                if not response_received:
                    print("[FAIL] Pinky failed to respond.")
                    return False
        except Exception as e:
            print(f"[FAIL] Websocket failed: {e}")
            return False

        print(f"[MARATHON] Beginning {STABILITY_GOAL}s stability soak...")
        soak_start = time.time()
        stable = True
        while time.time() - soak_start < STABILITY_GOAL:
            elapsed = int(time.time() - soak_start)
            print(f"[SOAK] {elapsed}/{STABILITY_GOAL}s stable...")
            
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
            return True
        else:
            return False

if __name__ == "__main__":
    success = asyncio.run(run_soak())
    if not success:
        sys.exit(1)
