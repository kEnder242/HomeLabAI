import asyncio
import websockets
import json

async def test_connection():
    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            # Send handshake
            await websocket.send(json.dumps({"type": "handshake", "version": "2.1.0"}))

            # Wait for response
            response = await websocket.recv()
            print(f"Received: {response}")

            # Send test query
            await websocket.send(json.dumps({"type": "text_input", "content": "ping"}))

            # Receive response
            async for message in websocket:
                data = json.loads(message)
                print(f"Server says: {data}")
                if data.get("brain"):
                    break
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
