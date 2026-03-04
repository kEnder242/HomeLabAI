import asyncio
import json
import websockets
import sys

async def ping_hub():
    url = "ws://127.0.0.1:8765/"
    print(f"--- 📡 HUB PING: Connecting to {url} ---")
    try:
        async with websockets.connect(url, open_timeout=5) as ws:
            print("✅ Socket Connected.")
            
            print("📤 Sending Query...")
            await ws.send(json.dumps({"type": "text_input", "content": "Pinky, are you there? Identify yourself!"}))
            
            async with asyncio.timeout(30):
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    print(f"[RECV] {data}")
                    if data.get('brain_source') == 'Pinky':
                        print(f"✅ Success! Pinky responded from vLLM: {data.get('brain')}")
                        return True
    except asyncio.TimeoutError:
        print("❌ ERROR: Timeout! Did not receive Pinky's response in 30 seconds.")
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__} - {e}")
    return False

if __name__ == "__main__":
    success = asyncio.run(ping_hub())
    sys.exit(0 if success else 1)
