import asyncio
import websockets
import json
import time

async def test_action_uplink():
    uri = "ws://localhost:8765"
    query = "[ME] Narf! Hey Pinky, let's ask the Brain about Pi."
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Sending Query: {query}")
            await websocket.send(json.dumps({"type": "text_input", "content": query}))
            
            start = time.time()
            found_brain = False
            while time.time() - start < 120: # 2 minute timeout for 4090 cold start
                try:
                    resp = await asyncio.wait_for(websocket.recv(), timeout=5)
                    data = json.loads(resp)
                    text = data.get('brain')
                    source = data.get('brain_source')
                    
                    if text:
                        print(f"[{source}] Response: {text[:100]}...")
                        if "Brain (Result)" in source:
                            found_brain = True
                        
                        if "3.14159" in text:
                            print("✅ SUCCESS: Brain responded with Pi.")
                            return
                except asyncio.TimeoutError:
                    print("... waiting ...")
                    continue
            
            if not found_brain:
                print("❌ FAILURE: Brain never triggered.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_action_uplink())
