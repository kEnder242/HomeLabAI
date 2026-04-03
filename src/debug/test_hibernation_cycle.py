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
STYLE_CSS = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/style.css")

def get_style_key():
    import hashlib
    if not os.path.exists(STYLE_CSS):
        return "missing"
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

KEY = get_style_key()
SERVER_LOG = os.path.join(_SRC_DIR, "server.log")

class SiliconAudit:
    """Forensic auditing of ports and processes."""
    @staticmethod
    def check_for_zombies():
        try:
            # [FEAT-256.1] Physical Truth: Check port 8765 instead of process names
            output = subprocess.check_output(["ss", "-tunlp"], text=True)
            return 1 if ":8765" in output else 0
        except Exception: return 0

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

async def cognitive_ping(label="Pre-Sleep"):
    """[FEAT-251.3] Proactive check for 404s, connection errors, and node liveness."""
    print(f"  [PING] Performing {label} Cognitive Check...")
    # Use intercom for Post-Sleep to trigger spark, but TestScript for pre-sleep baseline
    client_id = "intercom" if "Post" in label else "TestScript"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(HUB_URL) as ws:
                await ws.send_str(json.dumps({"type": "handshake", "client": client_id}))
                
                # Consume initial status messages (establishing anchors -> open)
                for _ in range(3):
                    msg = await ws.receive_json(timeout=10)
                    if msg.get("message") == "Lab foyer is open." or msg.get("full_lab_ready"):
                        break
                
                await ws.send_str(json.dumps({"type": "text_input", "content": "[ME] hello?"}))
                
                start_wait = time.time()
                while time.time() - start_wait < 180:
                    try:
                        msg = await ws.receive_json(timeout=10)
                        # DEBUG: Print all received messages
                        print(f"    [DEBUG] Received: {msg.get('type', 'UNKNOWN')} from {msg.get('brain_source', 'None')} (Final: {msg.get('final')})")
                        if "Pinky" in msg.get("brain_source", "") and msg.get("final"):
                            text = msg.get("brain", "").lower()
                            # HARDENED ERROR DETECTION
                            error_keywords = ["error:", "failed", "404", "none", "refused", "offline"]
                            if any(k in text for k in error_keywords):
                                print(f"  ❌ FAILED ({label}): Pinky reported a system error: {text[:100]}")
                                return False
                            
                            print(f"  ✅ Pinky Replied ({label}): {text[:50]}...")
                            return True
                    except asyncio.TimeoutError:
                        continue
                    except TypeError as e:
                        if "WSMsgType.CLOSE" in str(e) or "257" in str(e):
                            print(f"  ❌ FAILED ({label}): WebSocket closed by server.")
                            return False
                        raise
                else:
                    print(f"  ❌ Timeout ({label}): No response from Pinky.")
                    return False
    except Exception as e:
        print(f"  ❌ Connection Failed ({label}): {e}")
        return False

async def test_hibernation_cycle():
    print("--- [TEST] Forensic Hibernation & Cognitive Audit ---")
    audit = SiliconAudit()
    headers = {'X-Lab-Key': KEY, 'Content-Type': 'application/json'}
    
    async with aiohttp.ClientSession() as session:
        print("[STEP 0] Silicon Baseline Check...")
        zombies = audit.check_for_zombies()
        print(f"  ✅ Active Hubs: {zombies}")

        # STEP 1: Ensure READY
        print("[STEP 1] Waiting for Lab READY...")
        initial_vram = 0.0
        for _ in range(45): # 90s
            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                    data = await resp.json()
                    if data.get("full_lab_ready"):
                        vram_str = data.get("vram", "0%").replace("%","")
                        initial_vram = float(vram_str)
                        print(f"  ✅ Lab is READY (Mode: {data.get('mode')}, VRAM: {initial_vram}%)")
                        break
            except Exception: pass
            await asyncio.sleep(2)
        else:
            print("  ❌ Timeout: Lab failed to reach READY.")
            return

        # STEP 1.1: Proactive Check (Abort if broken now)
        if not await cognitive_ping("Pre-Sleep"):
            print("❌ ABORTING: Lab is non-functional before test began.")
            sys.exit(1)

        # STEP 2: Hibernate
        print("[STEP 2] Triggering HIBERNATE...")
        async with session.post(f"{ATTENDANT_URL}/hibernate", headers=headers, json={}) as resp:
            assert resp.status == 200
        await asyncio.sleep(5)
        
        async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
            data = await resp.json()
            if data.get("mode") != "HIBERNATING":
                print(f"  ❌ Failed to enter HIBERNATING mode (Current: {data.get('mode')})")
                sys.exit(1)
            
            hib_vram = float(data.get("vram", "0%").replace("%",""))
            print(f"  ✅ Hibernation verified. VRAM: {initial_vram}% -> {hib_vram}%")
            if initial_vram - hib_vram < 10:
                print(f"  ❌ FAILED: VRAM drop was only {initial_vram - hib_vram:.1f}%. Weights failed to unload.")
                sys.exit(1)

        # STEP 3: Spark
        print("[STEP 3] Sending Handshake Spark...")
        async with aiohttp.ClientSession().ws_connect(HUB_URL) as ws:
            await ws.send_str(json.dumps({"type": "handshake", "client": "TestScript"}))
            msg = await ws.receive_json(timeout=10)
            print(f"  ✅ Spark Ack (Type: {msg.get('type')})")

        # STEP 4: Wait for Restoration
        print("[STEP 4] Waiting for Restoration...")
        start_t = time.time()
        for _ in range(120): # 240s
            async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                data = await resp.json()
                if data.get("full_lab_ready"):
                    restore_vram = float(data.get("vram", "0%").replace("%",""))
                    print(f"  ✅ Lab Restored in {time.time() - start_t:.2f}s (VRAM: {restore_vram}%)")
                    break
            await asyncio.sleep(2)
        else:
            print("  ❌ Restoration timed out.")
            sys.exit(1)

        # STEP 5: Final Cognitive Audit
        if not await cognitive_ping("Post-Sleep"):
            print("❌ FAILED: Lab lost its voice after hibernation cycle.")
            sys.exit(1)

    print("\n--- [RESULT] High-Fidelity Logic is RESONANT ---")

if __name__ == "__main__":
    asyncio.run(test_hibernation_cycle())
