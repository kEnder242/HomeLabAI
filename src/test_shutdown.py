import asyncio
import websockets
import json
import sys

async def test_shutdown():
    uri = "ws://localhost:8765"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected. Sending Handshake...")
            # Handshake (v2.0.0)
            await websocket.send(json.dumps({"type": "handshake", "version": "2.0.0"}))

            print("Waiting for READY status...")

            # Wait for READY status
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=20.0)
                data = json.loads(response)
                print(f"Received status: {data.get('state')}")
                if data.get("type") == "status" and data.get("state") == "ready":
                    break

            # Send Shutdown Command
            print("Sending: 'Goodbye'")
            await websocket.send(json.dumps({"debug_text": "Goodbye"}))

            # Expect response then closure
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    print(f"Received: {data}")

                    if "brain" in data:
                        print(f"✅ Farewell Received: '{data['brain']}' (Source: {data.get('brain_source')})")
                        # The server might close the connection immediately after sending this
                        break

            except websockets.exceptions.ConnectionClosed:
                print("✅ Connection Closed (Server Shut Down).")
                return

    except Exception as e:
        print(f"Test Failed: {repr(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_shutdown())