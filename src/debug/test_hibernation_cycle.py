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

class SiliconAudit:
    """Forensic auditing of ports and processes."""
    
    @staticmethod
    def get_port_pid(port):
        try:
            output = subprocess.check_output(["sudo", "fuser", f"{port}/tcp"], stderr=subprocess.STDOUT, text=True)
            return int(output.split(":")[-1].strip())
        except Exception:
            return None

    @staticmethod
    def check_for_zombies():
        try:
            output = subprocess.check_output(["ps", "aux"], text=True)
            # Count Hub processes. Filter out the grep itself.
            lines = [l for l in output.split('\n') if "acme_lab" in l and "grep" not in l]
            return len(lines)
        except Exception:
            return 0

async def check_for_crashes():
    """Forensic check for Hub stack traces."""
    if not os.path.exists(SERVER_LOG): return None
    try:
        cmd = ["tail", "-n", "30", SERVER_LOG]
        output = subprocess.check_output(cmd, text=True)
        if "Traceback" in output or "Error:" in output or "Exception:" in output:
            lines = output.split('\n')
            for i, line in enumerate(lines):
                if "Traceback" in line: return "\n".join(lines[i:])
    except Exception: pass
    return None

async def test_hibernation_cycle():
    print("--- [TEST] Autonomous Hibernation & Silicon Audit ---")
    audit = SiliconAudit()
    headers = {'X-Lab-Key': KEY, 'Content-Type': 'application/json'}
    
    async with aiohttp.ClientSession() as session:
        # STEP 0: Pre-Flight Scrub
        print("[STEP 0] Performing Pre-Flight Silicon Scrub...")
        zombies = audit.check_for_zombies()
        if zombies > 1:
            print(f"  ⚠️ WARNING: Detected {zombies} redundant Hub processes. Clearing...")
            subprocess.run(["sudo", "fuser", "-k", "8765/tcp"], check=False)
            await asyncio.sleep(2)
        else:
            print("  ✅ Silicon is clean.")

        # Check if we need to ignite
        async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
            data = await resp.json()
            if data.get("mode") == "OFFLINE":
                print("  🔥 Lab is OFFLINE. Triggering Cold Ignition...")
                await session.post(f"{ATTENDANT_URL}/start", headers=headers, json={})
            else:
                print(f"  ✅ Lab is already {data.get('mode')}.")

        # STEP 1: Wait for READY
        print("[STEP 1] Waiting for Lab READY (Max 90s)...")
        initial_vram = 0
        for i in range(45):
            crash = await check_for_crashes()
            if crash:
                print(f"\n❌ CRASH DETECTED DURING IGNITION:\n{crash}")
                return

            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                    data = await resp.json()
                    if data.get("full_lab_ready"):
                        print(f"  ✅ Lab is READY (VRAM: {data.get('vram')})")
                        initial_vram = float(data.get("vram", "0%").replace("%",""))
                        break
            except Exception: pass
            await asyncio.sleep(2)
        else:
            print("  ❌ Timeout: Lab failed to reach READY.")
            return

        # STEP 2: Trigger Hibernate
        print("[STEP 2] Triggering HIBERNATE...")
        async with session.post(f"{ATTENDANT_URL}/hibernate", headers=headers) as resp:
            assert resp.status == 200
        
        await asyncio.sleep(5) 
        
        async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
            data = await resp.json()
            hib_vram = float(data.get("vram", "0%").replace("%",""))
            
            assert data.get("mode") == "HIBERNATING"
            assert data.get("intercom") == "ONLINE"
            print("  ✅ Hibernation verified (Hub alive, Engines dead).")

            # VRAM Delta check
            print(f"  ✅ VRAM Reclaimed: {initial_vram}% -> {hib_vram}%")
            if initial_vram - hib_vram < 10:
                print("  ⚠️ WARNING: VRAM drop was less than 10%. Check weights status.")

        # STEP 3: Trigger Handshake Spark
        print("[STEP 3] Sending Handshake Spark...")
        try:
            async with aiohttp.ClientSession().ws_connect(HUB_URL) as ws:
                await ws.send_str(json.dumps({"type": "handshake", "client": "TestScript"}))
                msg = await ws.receive_json(timeout=5)
                # Flexible check for response
                assert msg.get("type") in ["crosstalk", "status"]
                print(f"  ✅ Spark Acknowledged (Type: {msg.get('type')})")
        except Exception as e:
            print(f"  ❌ Handshake failed: {e}")
            return

        # STEP 4: Verify Restoration
        print("[STEP 4] Waiting for Restoration...")
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

    print("\n--- [RESULT] High-Fidelity Logic is RESONANT ---")

if __name__ == "__main__":
    asyncio.run(test_hibernation_cycle())
