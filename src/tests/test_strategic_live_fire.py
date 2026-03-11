import asyncio
import json
import websockets
import sys
import os

async def live_fire_test():
    uri = "ws://localhost:8765"
    query = "What is the RAPL BKM for thermal profiling?"
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Initial Handshake
            await websocket.send(json.dumps({"type": "handshake"}))
            
            # 2. Send Strategic Query
            print(f"Sending Query: {query}")
            await websocket.send(json.dumps({
                "type": "text_input",
                "content": query
            }))
            
            # 3. Monitor responses for 60 seconds
            print("Monitoring lifecycle...")
            found_brain = False
            found_pinky = False
            found_telemetry = False
            
            try:
                async with asyncio.timeout(60):
                    while True:
                        resp = await websocket.recv()
                        data = json.loads(resp)
                        source = data.get("brain_source", "")
                        text = str(data.get("brain", ""))
                        
                        if source:
                            print(f"[{source}] {text[:100]}...")
                        
                        if "Brain" in source: found_brain = True
                        if "Pinky" in source: found_pinky = True
                        if "RAPL" in text or "thermal" in text: found_telemetry = True
                        
                        # Stop if we got a dense response from Brain
                        if found_brain and len(text) > 100:
                            print("\nSUCCESS: Dense Brain response received.")
                            break
            except asyncio.TimeoutError:
                print("\nTIMEOUT: Did not receive full response in time.")
            
            print("\nVerification Checklist:")
            print(f"- Brain Responded: {found_brain}")
            print(f"- Pinky Responded: {found_pinky}")
            print(f"- Technical context present: {found_telemetry}")
            
            if found_brain and found_pinky:
                print("\nPASSED: Strategic Live Fire Successful.")
                return True
            else:
                print("\nFAILED: Missing components in response.")
                return False
                
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(live_fire_test())
    sys.exit(0 if success else 1)
