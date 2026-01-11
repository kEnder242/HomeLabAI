import asyncio
import websockets
import json
import sys
import time

HOST = "z87-Linux.local"
PORT = 8765
URI = f"ws://{HOST}:{PORT}"

async def test_intercom_protocol():
    print(f"🔌 Connecting to {URI}...")
    try:
        async with websockets.connect(URI) as ws:
            # 1. Handshake
            await ws.send(json.dumps({"type": "handshake", "version": "2.0.0-alpha", "client": "test_suite"}))
            print("✅ Handshake sent.")

            # 2. Consume Hello/Status
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                if data.get("type") == "status" and data.get("state") == "ready":
                    print("✅ Server Ready.")
                    break
            
            # 3. Simulate Text Input (The "Intercom" Feature)
            test_phrase = "Hello from the Intercom Test Suite"
            print(f"📤 Sending Text: '{test_phrase}'")
            await ws.send(json.dumps({
                "type": "text_input", 
                "content": test_phrase,
                "timestamp": time.time()
            }))

            # 4. Verify Response
            # We expect a "brain" response (Pinky replying)
            start = time.time()
            response_received = False
            while time.time() - start < 15.0:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    
                    if "brain" in data:
                        print(f"✅ Received Reply: [{data.get('brain_source')}]: {data['brain']}")
                        response_received = True
                        break
                        
                    if "text" in data:
                        print(f"   (Ignoring STT echo: {data['text']})")
                        
                except asyncio.TimeoutError:
                    break
            
            if response_received:
                print("🏆 Intercom Protocol Test PASSED.")
            else:
                print("❌ Intercom Protocol Test FAILED (No response).")
                sys.exit(1)

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_intercom_protocol())
