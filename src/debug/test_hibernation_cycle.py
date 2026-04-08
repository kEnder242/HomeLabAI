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

ATTENDANT_URL = "http://127.0.0.1:9999"
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
        except Exception:
            return 0

async def check_for_crashes():
    """Forensic check for Hub stack traces."""
    if not os.path.exists(SERVER_LOG):
        return None
    try:
        cmd = ["tail", "-n", "30", SERVER_LOG]
        output = subprocess.check_output(cmd, text=True)
        if "Traceback" in output:
            lines = output.split('\n')
            for i, line in enumerate(lines):
                if "Traceback" in line:
                    return "\n".join(lines[i:])
    except Exception:
        pass
    return None

async def cognitive_ping(label="Pre-Sleep"):
    """[FEAT-251.3] Proactive check for 404s, connection errors, and node liveness."""
    print(f"  [PING] Performing {label} Cognitive Check...")
    # Always use intercom to ensure wake-up if baseline starts while hibernating
    client_id = "intercom"
    try:
        async with aiohttp.ClientSession() as session:
            # [FEAT-259.7] Handshake Persistence: Retry connection until foyer is ready
            ws = None
            print("    [*] Attempting handshake with foyer (8765)...")
            for i in range(90): # 180s total for sequential boot
                try:
                    ws = await session.ws_connect(HUB_URL, timeout=2.0)
                    break
                except Exception:
                    await asyncio.sleep(2)
            
            if not ws:
                print(f"  ❌ FAILED ({label}): Could not connect to Hub foyer.")
                return False

            async with ws:
                await ws.send_str(json.dumps({"type": "handshake", "client": client_id}))
                
                # Consume initial status messages until OPERATIONAL
                print("    [*] Handshake sent. Waiting for foyer to reach OPERATIONAL...")
                is_foyer_ready = False
                for _ in range(60): # Increase to 120s for sequential boot
                    try:
                        msg = await ws.receive_json(timeout=10)
                        m_state = msg.get("state")
                        m_full = msg.get("operational") or msg.get("full_lab_ready")
                        if m_state == "operational" or m_full:
                            print("    [+] Foyer confirmed OPERATIONAL.")
                            is_foyer_ready = True
                            break
                    except Exception:
                        break

                
                if not is_foyer_ready:
                    print(f"  ❌ FAILED ({label}): Foyer never reached OPERATIONAL state.")
                    return False

                # [FINAL_FIX] Drain foyer noise completely before querying
                print("    [*] Draining foyer noise...")
                for _ in range(20):
                    try:
                        await ws.receive_json(timeout=0.5)
                    except Exception:
                        break

                # [FEAT-259.6] Settle window for reasoning nodes (Physical Silicon)
                print("    [*] Settle window (60s) for physical silicon and adapters...")
                await asyncio.sleep(60)

                # [FEAT-259.8] Query Persistence
                for attempt in range(3):
                    print(f"    [*] Dispatching query (Attempt {attempt+1}): hello?")
                    await ws.send_str(json.dumps({"type": "text_input", "content": "[ME] hello?"}))
                    
                    start_wait = time.time()
                    while time.time() - start_wait < 60: # 60s per attempt
                        try:
                            msg = await ws.receive_json(timeout=10)
                            m_type = msg.get('type', 'UNKNOWN')
                            m_src = str(msg.get('brain_source') or msg.get('source', 'None'))
                            m_text = str(msg.get('brain') or msg.get('message', ''))
                            
                            if m_type in ["chat", "crosstalk"] and "Pinky" in m_src:
                                print(f"  ✅ Pinky Replied ({label}): {m_text[:50]}...")
                                return True
                        except Exception:
                            continue
                    print(f"    [!] Attempt {attempt+1} timed out.")
                
                print(f"  ❌ FAILED ({label}): No response from Pinky after 3 attempts.")
                return False
    except Exception as e:
        print(f"  ❌ Connection Failed ({label}): {e}")
        return False

async def test_hibernation_cycle():
    print("--- [TEST] Forensic Hibernation & Cognitive Audit ---")
    audit = SiliconAudit()
    headers = {'X-Lab-Key': KEY, 'Content-Type': 'application/json'}
    
    async with aiohttp.ClientSession() as session:
        # [STEP 0] Silicon Baseline Check
        print("[STEP 0] Silicon Baseline Check...")
        zombies = audit.check_for_zombies()
        print(f"  ✅ Active Hubs: {zombies}")

        # STEP 1: Ensure OPERATIONAL
        print("[STEP 1] Waiting for Lab OPERATIONAL...")
        initial_vram = 0.0
        sparked = False
        start_wait = time.time()
        while time.time() - start_wait < 300:
            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat?key={KEY}") as resp:
                    data = await resp.json()
                    mode = data.get("mode")
                    is_op = data.get("operational")
                    
                    if mode == "HIBERNATING" and not sparked:
                        print("  [*] Lab is hibernating. Sparking wake-up...")
                        async with aiohttp.ClientSession() as spark_session:
                            async with spark_session.ws_connect(HUB_URL) as ws:
                                await ws.send_str(json.dumps({"type": "handshake", "client": "intercom"}))
                        sparked = True

                    vram_str = data.get("vram", "0%").replace("%","")
                    vram = float(vram_str)
                    if is_op or mode == "STUB":
                        initial_vram = vram
                        print(f"  ✅ Lab is OPERATIONAL (Mode: {mode}, VRAM: {initial_vram}%)")
                        break
            except Exception:
                pass
            await asyncio.sleep(5)
        else:
            print("  ❌ Timeout: Lab failed to reach OPERATIONAL.")
            sys.exit(1)

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
            
            is_stub = data.get("mode") == "STUB"
            if not is_stub and initial_vram - hib_vram < 10:
                print(f"  ❌ FAILED: VRAM drop was only {initial_vram - hib_vram:.1f}%. Weights failed to unload.")
                sys.exit(1)
            elif is_stub:
                print("  [*] STUB Mode: Skipping physical VRAM check.")

        # STEP 3: Spark
        print("[STEP 3] Sending Handshake Spark...")
        spark_success = False
        for i in range(5): # 5 attempts
            try:
                async with aiohttp.ClientSession().ws_connect(HUB_URL) as ws:
                    await ws.send_str(json.dumps({"type": "handshake", "client": "intercom"})) # Use 'intercom' to trigger spark
                    
                    print(f"  [*] Handshake sent (Attempt {i+1}). Awaiting state transitions...")
                    for _ in range(60): # 120s patience
                        try:
                            msg_raw = await ws.receive()
                            if msg_raw.type == aiohttp.WSMsgType.CLOSE:
                                print("    [!] WebSocket closed by server during restoration.")
                                break
                            if msg_raw.type != aiohttp.WSMsgType.TEXT:
                                continue
                                
                            msg = msg_raw.json()
                            m_type = msg.get("type")
                            m_state = msg.get("state")
                            m_msg = msg.get("message")
                            if m_type == "status":
                                print(f"    [WS] State: {m_state} | {m_msg}")
                                if m_state == "ready" or m_state == "init": # Support both
                                    print(f"  ✅ Spark Successful. System reported {m_state.upper()}.")
                                    spark_success = True
                                    break
                        except Exception as e:
                            print(f"    [!] WebSocket Error: {e}")
                            break
                    if spark_success:
                        break
            except Exception as e:
                print(f"  [!] Spark Connection failed: {e}. Retrying in 5s...")
                await asyncio.sleep(5)
        
        if not spark_success:
            print("  ❌ Failed to spark restoration after 5 attempts.")
            sys.exit(1)

        # STEP 4: Wait for Restoration
        print("[STEP 4] Waiting for Restoration...")
        start_t = time.time()
        for _ in range(180): # 900s patience
            async with session.get(f"{ATTENDANT_URL}/status", headers={"X-Lab-Key": KEY}) as resp:
                data = await resp.json()
                vram_str = data.get("vram", "0%").replace("%","")
                vram = float(vram_str)
                # [FIX] Match new vocabulary
                is_op = data.get("operational") or data.get("full_lab_ready")
                print(f"    [RESTORE_DEBUG] Operational: {is_op} | VRAM: {vram}% | Mode: {data.get('mode')}")
                if is_op and vram > 50:
                    print(f"  ✅ Lab Restored in {time.time() - start_t:.2f}s (VRAM: {vram}%)")
                    break
            await asyncio.sleep(5)
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
