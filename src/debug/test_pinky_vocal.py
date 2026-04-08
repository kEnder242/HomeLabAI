import asyncio
import aiohttp
import json
import time

ATTENDANT_URL = "http://127.0.0.1:9999"
HUB_URL = "http://127.0.0.1:8765"
LAB_KEY = "92e785ba"

async def test_pinky_vocal():
    print("--- [TEST] Focused Pinky Vocal Verification ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Start Lab in PINKY_MODE_VOCAL
        print("[STEP 1] Starting Lab in PINKY_MODE_VOCAL...")
        start_payload = {
            "engine": "VLLM",
            "model": "MEDIUM",
            "op_mode": "PINKY_MODE_VOCAL",
            "reason": "VOCAL_TEST"
        }
        async with session.post(f"{ATTENDANT_URL}/start", json=start_payload, headers={"X-Lab-Key": LAB_KEY}) as r:
            if r.status != 200:
                print(f"  ❌ FAILED: Start rejected ({r.status})")
                return
        
        # 2. Wait for OPERATIONAL
        print("[STEP 2] Waiting for OPERATIONAL (Max 180s)...")
        for i in range(36):
            async with session.get(f"{ATTENDANT_URL}/status", headers={"X-Lab-Key": LAB_KEY}) as r:
                data = await r.json()
                if data.get("operational"):
                    print(f"  ✅ Lab is OPERATIONAL (VRAM: {data.get('vram')})")
                    break
                else:
                    v_reason = data.get("engine_vocal")
                    print(f"  [*] Waiting... (VRAM: {data.get('vram')}, Vocal:{v_reason})")
            await asyncio.sleep(5)
        else:
            print("  ❌ TIMEOUT: Lab never reached OPERATIONAL.")
            return

        # 3. Hub-Level Cognitive Check
        print("[STEP 3] Performing Hub-Level Cognitive Check...")
        async with session.ws_connect(HUB_URL) as ws:
            await ws.send_str(json.dumps({"type": "handshake", "client": "prober"}))
            # Drain initial noise
            print("    [*] Draining foyer noise...")
            for _ in range(10):
                try:
                    await ws.receive_json(timeout=0.5)
                except Exception:
                    break

            print("    [*] Dispatching query: hello?")
            await ws.send_str(json.dumps({"type": "text_input", "content": "[ME] hello?"}))
            
            try:
                # Wait for response
                while True:
                    msg = await ws.receive_json(timeout=30)
                    m_type = msg.get('type')
                    m_src = msg.get('brain_source', 'None')
                    m_text = msg.get('brain', '')
                    
                    if m_type in ["chat", "crosstalk"] and "Pinky" in m_src:
                        print(f"  ✅ Pinky Replied: {m_text[:50]}...")
                        break
            except Exception as e:
                print(f"  ❌ FAILED: Pinky is silent ({e})")
                return

    print("--- SUCCESS: Pinky is VOCAL through the Hub foyer. ---")

if __name__ == "__main__":
    asyncio.run(test_pinky_vocal())
