import asyncio
import websockets
import json
import sys

PORT = 8765
# Use localhost since we'll run this on the server itself via SSH
URI = f"ws://localhost:{PORT}"

async def run_test(query):
    print(f"Connecting to {URI}...")
    try:
        async with websockets.connect(URI) as websocket:
            print(f"sending debug text: '{query}'")
            # The host supports injecting text for debugging
            await websocket.send(json.dumps({"debug_text": query}))
            
            # Listen for responses
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    data = json.loads(msg)
                    if "brain" in data:
                        print(f"\nResponse from {data.get('brain_source', 'Unknown')}:")
                        print(f"{data['brain']}")
                        # If we get a final response (not just the handoff msg), break
                        if "Handoff" not in data.get("brain_source", ""):
                            break
                    elif "text" in data:
                        print(f"STT: {data['text']}")
                except asyncio.TimeoutError:
                    print("Timeout waiting for response.")
                    break
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    q = "Write a python script to calculate fibonacci numbers."
    if len(sys.argv) > 1:
        q = sys.argv[1]
    asyncio.run(run_test(q))
