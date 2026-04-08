import asyncio
import aiohttp
import json
import time
import subprocess

ATTENDANT_URL = "http://127.0.0.1:9999"
HUB_URL = "http://127.0.0.1:8765"
LAB_KEY = "92e785ba"

async def test_focused_hibernate():
    print("--- [TEST] Focused Pinky Hibernation Cycle ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Start Lab in PINKY_MODE_HIBERNATE
        print("[STEP 1] Starting Lab in PINKY_MODE_HIBERNATE...")
        start_payload = {
            "engine": "VLLM",
            "model": "MEDIUM",
            "op_mode": "PINKY_MODE_HIBERNATE",
            "reason": "FOCUS_TEST"
        }
        async with session.post(f"{ATTENDANT_URL}/start", json=start_payload, headers={"X-Lab-Key": LAB_KEY}) as r:
            if r.status != 200:
                print(f"  ❌ FAILED: Start rejected ({r.status})")
                return
        
        # 2. Wait for OPERATIONAL
        print("[STEP 2] Waiting for OPERATIONAL...")
        for _ in range(60):
            async with session.get(f"{ATTENDANT_URL}/status", headers={"X-Lab-Key": LAB_KEY}) as r:
                data = await r.json()
                if data.get("operational"):
                    print(f"  ✅ Lab is OPERATIONAL (VRAM: {data.get('vram')})")
                    break
            await asyncio.sleep(5)
        else:
            print("  ❌ TIMEOUT: Lab never reached OPERATIONAL.")
            return

        # 3. Cognitive Check (Vocal)
        print("[STEP 3] Performing Cognitive Check...")
        async with session.ws_connect(HUB_URL) as ws:
            await ws.send_str(json.dumps({"type": "handshake", "client": "prober"}))
            await ws.send_str(json.dumps({"type": "text_input", "content": "[ME] hello?"}))
            
            try:
                msg = await ws.receive_json(timeout=30)
                print(f"  ✅ Pinky Replied: {msg.get('brain', '')[:50]}...")
            except Exception as e:
                print(f"  ❌ FAILED: Pinky is silent ({e})")
                return

        # 4. Trigger Hibernate
        print("[STEP 4] Triggering HIBERNATE...")
        async with session.post(f"{ATTENDANT_URL}/hibernate", headers={"X-Lab-Key": LAB_KEY}) as r:
            if r.status == 200:
                print("  ✅ Hibernate Signal Sent.")
            else:
                print(f"  ❌ FAILED: Hibernate rejected ({r.status})")
                return

        # 5. Verify VRAM drop
        print("[STEP 5] Verifying VRAM drop...")
        for _ in range(15):
            async with session.get(f"{ATTENDANT_URL}/status", headers={"X-Lab-Key": LAB_KEY}) as r:
                data = await r.json()
                vram_str = data.get("vram", "100%")
                vram_val = float(vram_str.strip('%'))
                if vram_val < 10.0:
                    print(f"  ✅ SUCCESS! VRAM reclaimed: {vram_str}")
                    return True
                print(f"  [*] Current VRAM: {vram_str}")
            await asyncio.sleep(5)
        
        print("  ❌ FAILED: VRAM did not drop below 10%.")
        return False

if __name__ == "__main__":
    asyncio.run(test_focused_hibernate())
