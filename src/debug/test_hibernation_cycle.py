import asyncio
import json
import aiohttp
import sys
import os
import time
import subprocess

# Paths
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_SELF_DIR)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "ws://localhost:8765"
KEY = "c48e0b32"
SERVER_LOG = os.path.join(_SRC_DIR, "server.log")

async def check_for_crashes():
    """[FEAT-251] Forensic check for Hub stack traces."""
    if not os.path.exists(SERVER_LOG):
        return None
    try:
        # Check last 30 lines for common crash indicators
        cmd = ["tail", "-n", "30", SERVER_LOG]
        output = subprocess.check_output(cmd, text=True)
        if "Traceback" in output or "Error:" in output or "Exception:" in output:
            # Narrow down to the actual trace
            lines = output.split('\n')
            for i, line in enumerate(lines):
                if "Traceback" in line:
                    return "\n".join(lines[i:])
    except Exception:
        pass
    return None

async def test_hibernation_cycle():
    print("--- [TEST] VRAM Hibernation & Handshake Spark Cycle ---")
    
    async with aiohttp.ClientSession() as session:
        # STEP 1: Verify READY state
        print("[STEP 1] Waiting for Lab READY (Max 60s)...")
        for i in range(30): # 30 * 2s = 60s
            # Forensic Check
            crash = await check_for_crashes()
            if crash:
                print(f"\n❌ CRASH DETECTED DURING BOOT:\n{crash}")
                return

            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                    data = await resp.json()
                    if data.get("full_lab_ready"):
                        print("  ✅ Lab is READY.")
                        break
            except Exception:
                pass
            await asyncio.sleep(2)
        else:
            print("  ❌ Timeout: Lab failed to reach READY.")
            return

        # STEP 2: Trigger Hibernate
        print("[STEP 2] Triggering HIBERNATE...")
        headers = {'X-Lab-Key': KEY}
        async with session.post(f"{ATTENDANT_URL}/hibernate", headers=headers) as resp:
            assert resp.status == 200
        
        # Wait for status transition (5s total, checking logs)
        for _ in range(5):
            await asyncio.sleep(1)
            crash = await check_for_crashes()
            if crash:
                print(f"\n❌ CRASH DETECTED DURING HIBERNATION:\n{crash}")
                return
        
        async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
            data = await resp.json()
            if data.get("mode") != "HIBERNATING":
                print(f"  ❌ Expected HIBERNATING mode, got: {data.get('mode')}")
                return
            if data.get("intercom") != "ONLINE":
                print("  ❌ HUB DIED during hibernation (Suicide Loop).")
                return
            print("  ✅ Hibernation verified (Hub alive, Engines dead).")

        # STEP 3: Trigger Handshake Spark
        print("[STEP 3] Sending Handshake Spark...")
        try:
            async with aiohttp.ClientSession().ws_connect(HUB_URL) as ws:
                await ws.send_str(json.dumps({"type": "handshake", "client": "TestScript"}))
                
                # We expect a status or crosstalk tic immediately
                msg = await ws.receive_json(timeout=5)
                if msg.get("type") not in ["crosstalk", "status"]:
                    print(f"  ❌ Expected status/crosstalk tic, got: {msg.get('type')}")
                    return
                print(f"  ✅ Spark Acknowledged (Type: {msg.get('type')})")
        except Exception as e:
            print(f"  ❌ Handshake failed: {e}")
            return

        # STEP 4: Verify Restoration
        print("[STEP 4] Waiting for Restoration (Max 60s)...")
        start_t = time.time()
        for _ in range(30):
            crash = await check_for_crashes()
            if crash:
                print(f"\n❌ CRASH DETECTED DURING RESTORATION:\n{crash}")
                return

            async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                data = await resp.json()
                if data.get("mode") in ["VLLM", "OLLAMA"] and data.get("full_lab_ready"):
                    print(f"  ✅ Lab Restored in {time.time() - start_t:.2f}s")
                    break
            await asyncio.sleep(2)
        else:
            print("  ❌ Restoration timed out.")
            return

    print("\n--- [RESULT] Hibernation Logic is RESONANT ---")

if __name__ == "__main__":
    asyncio.run(test_hibernation_cycle())
