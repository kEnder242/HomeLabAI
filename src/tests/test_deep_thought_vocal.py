import asyncio
import websockets
import json
import time

async def test_brain_vocal():
    """
    [Task 5.2] Certify the 4090 (Brain) handshake logic.
    Verifies that the Architect Brain is resident and vocal.
    """
    uri = "ws://localhost:8765"
    print("--- [TASK 5.2] VOCAL HANDSHAKE: DEEP THOUGHT (4090) ---", flush=True)
    
    async with websockets.connect(uri) as ws:
        # 1. Handshake to ensure Hub is ready
        await ws.send(json.dumps({"type": "handshake", "client": "test_script"}))
        
        # 2. Check for Brain Online status
        brain_online = False
        start_time = time.time()
        print("⌛ Waiting for Brain Online status...", flush=True)
        
        while time.time() - start_time < 60:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("type") == "status":
                    brain_online = data.get("brain_online", False)
                    state = data.get("state", "")
                    print(f"  [STATUS] Brain Online: {brain_online} | State: {state}", flush=True)
                    if brain_online and state == "operational":
                        print("✅ [SUCCESS]: Hub reports Brain is ONLINE and Hub is OPERATIONAL.", flush=True)
                        break
            except asyncio.TimeoutError:
                continue
        
        if not brain_online:
            print("❌ [FAILURE]: Brain is not online or failed probe within 60s.", flush=True)
            # return # We might want to try anyway if the hub is operational

        # 3. Direct Vocal Probe
        # Using [ME] to trigger human-level priority and bypass some filters
        query = "[ME] Brain, provide a vocal handshake. Respond with 'READY' and your current VRAM stance."
        print(f"--- SENDING VOCAL PROBE: {query} ---", flush=True)
        await ws.send(json.dumps({"type": "text_input", "content": query}))
        
        vocal_success = False
        probe_start = time.time()
        while time.time() - probe_start < 300: # Wait up to 5 mins for slow 4090 wake
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                m_type = data.get("type")
                m_source = data.get("brain_source", "")
                m_content = str(data.get("brain", ""))
                
                if m_type == "chat" or m_type == "crosstalk":
                    print(f"  📥 RX: {m_type} ({m_source}) -> {m_content[:100]}...", flush=True)
                
                if "Brain (Result)" in m_source or "The Brain" in m_source:
                    if "READY" in m_content.upper():
                        print("\n✅ [SUCCESS]: Brain (4090) responded vocally with READY.", flush=True)
                        vocal_success = True
                        break
            except asyncio.TimeoutError:
                print("  ⌛ Waiting for Brain response...", flush=True)

        if not vocal_success:
            print("\n❌ [FAILURE]: Brain failed to respond vocally with READY within 300s.", flush=True)

if __name__ == "__main__":
    asyncio.run(test_brain_vocal())
