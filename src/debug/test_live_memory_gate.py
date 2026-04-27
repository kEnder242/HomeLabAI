import asyncio
import json
import websockets
import os
import time

async def test_memory_gate():
    uri = "ws://127.0.0.1:8765"
    query = "What did I do with Montana in 2023?"
    
    print(f"[#] Target Query: {query}")
    print(f"[#] Connecting to Hub at {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Handshake
            await websocket.send(json.dumps({
                "type": "handshake",
                "client": "intercom_test",
                "version": "4.5"
            }))
            
            # Wait for status
            resp = await websocket.recv()
            status = json.loads(resp)
            print(f"[+] Connected. Lab State: {status.get('state', 'Unknown')}")
            
            if status.get('state') != 'operational':
                print("[!] WARNING: Lab is not yet OPERATIONAL. Test may fall back to Shadow.")

            # 2. Clear Context (Neuralyzer)
            print("[#] Clearing stale context...")
            await websocket.send(json.dumps({
                "type": "query",
                "content": "Look at the light"
            }))
            # Wait for clear confirmation
            await asyncio.sleep(2)

            # 3. Send History Query
            print(f"[#] Sending target query: {query}")
            await websocket.send(json.dumps({
                "type": "query",
                "content": query
            }))
            
            # 3. Monitor for "Deep Memory Gate" signal in crosstalk
            history_triggered = False
            focal_retrieved = False
            brain_started = False
            
            start_t = time.time()
            while time.time() - start_t < 60: # 60s timeout
                msg = await websocket.recv()
                data = json.loads(msg)
                
                if data.get("type") == "crosstalk":
                    text = data.get("brain", "")
                    print(f"    [CROSSTALK]: {text}")
                    if "[HUB] Triage successful" in text:
                        print("[+] Triage Phase Completed.")
                    if "Initiating Brain (Result)" in text:
                        brain_started = True
                
                if data.get("type") == "chat":
                    # Check for ARCHIVAL tags in the actual output or debug logs
                    content = data.get("content", "")
                    source = data.get("source", "")
                    
                    if "Pinky (Triage)" in source and "[ARCHIVE_HISTORY]" in content:
                        history_triggered = True
                        print("[+] SUCCESS: Multi-Resolution History Triggered.")
                    
                    if "Brain (Result)" in source:
                        print(f"\n[FINAL RESPONSE] ({source}):\n{content[:200]}...")
                        # Evaluation: Looking for technical gems (Kayak, PECI, Montana)
                        if any(k in content.lower() for k in ["peci", "kayak", "mctp"]):
                            print("\n[+] VALIDATION: Response contains specific technical evidence.")
                        break

            if not history_triggered:
                print("\n[!] FAILURE: Proactive Archivist did not trigger.")
            
    except Exception as e:
        print(f"[!] Test Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_memory_gate())
