import asyncio
import websockets
import json
import time

async def test_hi_persona():
    uri = "ws://localhost:8765"
    query = "[ME] hi Pinky!"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Sending Query: {query}")
            await websocket.send(json.dumps({"type": "text_input", "content": query}))
            
            start = time.time()
            found_persona = False
            while time.time() - start < 30:
                try:
                    resp = await asyncio.wait_for(websocket.recv(), timeout=5)
                    data = json.loads(resp)
                    text = data.get('brain')
                    source = data.get('brain_source')
                    
                    if text:
                        print(f"[{source}] Response: {text[:100]}...")
                        if "Pinky" in source:
                            if "{" not in text: # Success if no JSON leak
                                found_persona = True
                                print("✅ SUCCESS: Pinky delivered natural persona speech.")
                                return
                            else:
                                print("❌ FAILURE: JSON Leak detected in Pinky response.")
                                return
                except asyncio.TimeoutError:
                    continue
            
            if not found_persona:
                print("❌ FAILURE: No persona response received within timeout.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_hi_persona())
