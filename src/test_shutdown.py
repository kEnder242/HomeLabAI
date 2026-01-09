import asyncio
import websockets
import json
import logging

async def test_shutdown():
    uri = "ws://localhost:8765"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected.")
            
            # Wait for handshake
            status = await websocket.recv()
            print(f"Status: {status}")
            
            # Send Shutdown Command
            print("Sending: 'Goodbye'")
            # Note: We send as 'debug_text' to bypass STT for the test
            await websocket.send(json.dumps({"debug_text": "Goodbye"}))
            
            # Expect response then closure
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    print(f"Received: {data}")
                    
                    if "brain" in data and "Closing Lab" in data["brain"]:
                        print("✅ Shutdown Message Received.")
                        return

            except websockets.exceptions.ConnectionClosed:
                print("✅ Connection Closed (Server Shut Down).")
                return
                
    except Exception as e:
        print(f"Test Failed: {repr(e)}")

if __name__ == "__main__":
    asyncio.run(test_shutdown())
