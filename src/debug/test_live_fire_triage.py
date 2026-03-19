import asyncio
import websockets
import json
import sys

async def test_live_fire():
    uri = "ws://localhost:8765"
    query = "[ME] Can you analyze the 18-year technical history and explain the evolution of the silicon validation strategy in the Acme Lab?"
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Sending Query: {query}")
            await websocket.send(json.dumps({"type": "text_input", "content": query}))
            
            print("Awaiting responses (Parallel Dispatch)...")
            # Collect first 3 responses to see Triage + Result
            for i in range(3):
                try:
                    resp = await asyncio.wait_for(websocket.recv(), timeout=30)
                    data = json.loads(resp)
                    source = data.get("brain_source", "Unknown")
                    text = data.get("brain", "")
                    print(f"\n--- [RESPONSE {i+1}] Source: {source} ---")
                    print(text[:200] + "...")
                except asyncio.TimeoutError:
                    print(f"\n[TIMEOUT] No response {i+1} within 30s")
                    break
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_live_fire())
