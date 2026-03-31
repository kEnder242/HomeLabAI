import asyncio
import websockets
import json
import time
import aiohttp

async def test_wakeup():
    uri = "ws://localhost:8765"
    print(f"--- [TEST] Triggering Wake-up Handshake ---")
    try:
        async with websockets.connect(uri) as ws:
            # 1. Send Handshake
            payload = {"type": "handshake", "client": "Wakeup-Test"}
            await ws.send(json.dumps(payload))
            print("  ✅ Handshake sent.")
            
            # 2. Wait for status response
            resp = await ws.recv()
            print(f"  ✅ Hub Response: {resp[:100]}...")
            
            # 3. Poll Attendant for mode change
            print("  ⏳ Polling Attendant for Ignition...")
            for i in range(10):
                async with aiohttp.ClientSession() as session:
                    headers = {'X-Lab-Key': 'c48e0b32'}
                    async with session.get("http://localhost:9999/status", headers=headers) as r:
                        if r.status == 404:
                            text = await r.text()
                            print(f"  ❌ 404 ERROR: Attendant returned File Not Found. Trace:\n{text[:200]}")
                            return False
                        
                        data = await r.json()
                        mode = data.get("mode")
                        print(f"    [T+{i*2}s] Mode: {mode}")
                        if mode in ["VLLM", "SERVICE_UNATTENDED", "OLLAMA"]:
                            print("✨ SUCCESS: Snap-to-Life triggered engine ignition!")
                            return True
                await asyncio.sleep(2)
            
            print("❌ FAILURE: Engine failed to ignite.")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_wakeup())
