import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8765"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            # 1. Handshake
            await ws.send(json.dumps({"type": "handshake", "version": "3.4.0", "client": "test_agent"}))
            await asyncio.sleep(2)

            # 2. Send query
            query = "Pinky, are you there? Can you ask The Brain if the integration test passed?"
            print(f"Sending: {query}")
            await ws.send(json.dumps({"type": "text_input", "content": query}))

            # 3. Wait for responses
            print("Waiting for responses...")
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(msg)

                    if "brain" in data:
                        source = data.get("brain_source", "Unknown")
                        print(f"\n[{source}]: {data['brain']}")
                        if source == "The Brain":
                            print("\n✅ Full Flow Verified (Pinky -> Brain).")
                            break
                    elif data.get("type") == "debug":
                        print(f"DEBUG: {data.get('event')} - {data.get('data')}")
                    elif data.get("type") == "status":
                        print(f"STATUS: {data.get('state')} - {data.get('message', '')}")

                except asyncio.TimeoutError:
                    print("\n❌ Timeout waiting for Brain response.")
                    break
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
