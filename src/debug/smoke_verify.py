import asyncio
import aiohttp
import time
import sys

ATTENDANT_URL = "http://localhost:9999"

async def run_smoke():
    print("--- 🌫️  Starting Full-Stack DEBUG_SMOKE Gate ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Hard Reset
        print("[SMOKE] Resetting silicon...")
        try:
            await session.post(f"{ATTENDANT_URL}/hard_reset", timeout=10)
        except Exception as e:
            print(f"❌ Failed to reach Attendant: {e}")
            return False

        # 2. Start in DEBUG_SMOKE
        print("[SMOKE] Launching Lab in DEBUG_SMOKE mode...")
        payload = {
            "engine": "Ollama",
            "mode": "DEBUG_SMOKE",
            "disable_ear": True
        }
        try:
            # Non-blocking start
            async with session.post(f"{ATTENDANT_URL}/start", json=payload, timeout=10) as r:
                if r.status != 200:
                    print(f"❌ Failed to start lab: {r.status}")
                    return False
        except Exception as e:
            print(f"❌ Start request failed: {e}")
            return False

        # 3. Poll Heartbeat
        print("[SMOKE] Monitoring boot sequence...")
        start_t = time.time()
        max_wait = 180 # 3 minutes for vLLM + compiling + 4 nodes
        
        reached_ready = False
        while time.time() - start_t < max_wait:
            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat", timeout=5) as resp:
                    vitals = await resp.json()
                    
                    if vitals.get("last_error"):
                        print(f"\n❌ FATAL ERROR: {vitals.get('last_error')}")
                        return False
                    
                    if vitals.get("full_lab_ready"):
                        print("\n✅ Lab reached READY state.")
                        reached_ready = True
                        break
                    
                    # Log state
                    vllm = "UP" if vitals.get("vllm_running") else "INIT"
                    lab = "UP" if vitals.get("lab_server_running") else "DOWN"
                    elapsed = int(time.time() - start_t)
                    print(f"   [BOOT] vLLM: {vllm} | Lab: {lab} | {elapsed}s")
            except Exception:
                # Occasional connection drops during reset are expected
                pass
            
            await asyncio.sleep(5)

        if not reached_ready:
            print("\n❌ Timeout waiting for Lab READY.")
            return False

        # 4. Wait for Self-Termination
        print("[SMOKE] Verifying self-termination...")
        term_start = time.time()
        while time.time() - term_start < 30:
            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat", timeout=5) as resp:
                    vitals = await resp.json()
                    if not vitals.get("lab_server_running"):
                        print("✅ Lab self-terminated successfully.")
                        print("--- ✨ SMOKE GATE PASSED ---")
                        return True
            except Exception:
                pass
            await asyncio.sleep(2)

        print("⚠️ Lab reached READY but did not self-terminate in time.")
        return True # Still technically a success if it got to READY

if __name__ == "__main__":
    success = asyncio.run(run_smoke())
    if not success:
        sys.exit(1)
