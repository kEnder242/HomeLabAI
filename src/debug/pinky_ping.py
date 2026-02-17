import asyncio
import json
import websockets
import sys

async def ping():
    url = "ws://127.0.0.1:8765"
    print(f"--- 📡 PINKY PING: Connecting to {url} ---")
    try:
        async with websockets.connect(url, open_timeout=5) as ws:
            print("✅ Socket Connected.")
            
            # 1. Send Handshake
            await ws.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            
            # 2. Wait for Status & Cabinet responses
            async with asyncio.timeout(5):
                msg1 = await ws.recv()
                print(f"[RECV 1] {msg1[:100]}...")
                msg2 = await ws.recv()
                print(f"[RECV 2] {msg2[:100]}...")
                
            # 3. Test Query
            print("📤 Sending Vibe Check...")
            await ws.send(json.dumps({"type": "text_input", "content": "Pinky, are you there?"}))
            
            async with asyncio.timeout(10):
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if "brain" in data:
                        print(f"✅ PINKY RESPONDED: {data['brain']}")
                        return True
    except ConnectionRefusedError:
        print("❌ CONNECTION REFUSED: Port 8765 is closed.")
    except asyncio.TimeoutError:
        print("❌ TIMEOUT: Connection established but Pinky is silent.")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    return False

if __name__ == "__main__":
    success = asyncio.run(ping())
    sys.exit(0 if success else 1)
