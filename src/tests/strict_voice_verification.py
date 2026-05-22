import asyncio
import websockets
import json
import time
import sys
import os

async def run_semantic_verification():
    """
    [BKM-029] Strict Verification: Ensures 100% voice restoration and NO reflex spam.
    """
    uri = "ws://localhost:8765"
    print("--- [SPR-29] STRICT VOICE VERIFICATION ---")
    
    SERVER_LOG = "HomeLabAI/server.log"
    
    try:
        async with websockets.connect(uri, open_timeout=60) as ws:
            await ws.send(json.dumps({"type": "handshake", "version": "v3.1.9"}))
            
            # Wait for Foyer sync
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get("type") == "status" and data.get("state") == "operational":
                    break
                print(f"[*] Hub Status: {data.get('state')} - {data.get('message')}")

            # Send Probe
            query = "[ME] Analyze 2023. This is a semantic test."
            print(f"\n--- SENDING PROBE: {query} ---")
            await ws.send(json.dumps({"type": "query", "query": query}))
            
            reflex_detected = False
            semantic_detected = False
            handshake_detected = False
            
            start_time = time.time()
            while time.time() - start_time < 300:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(msg)
                    
                    if data.get("type") in ["crosstalk", "chat", "brain"]:
                        text = data.get("brain", "")
                        source = data.get("brain_source", "Unknown")
                        
                        # 1. Check for Reflex Tics (Narf/Zort/Poit/Egad/Trotro)
                        # Filter out "Pinky (Handshake)" which might use Narf as a persona marker
                        if source == "Pinky" and any(x in text.lower() for x in ["narf!", "zort!", "poit!", "egad!", "trotro!"]):
                            print(f"🚨 [FAILURE]: Reflex detected from {source}: {text}")
                            reflex_detected = True
                        
                        # 2. Check for Vocal Handshake
                        if "Pinky (Handshake)" in source:
                            print(f"✅ [SUCCESS]: Vocal Handshake detected: {text[:50]}...")
                            handshake_detected = True
                            
                        # 3. Check for Semantic Thought (The "2023" probe)
                        if "<thought>" in text and "2023" in text:
                            print(f"✅ [SUCCESS]: Semantic thought detected from {source}!")
                            semantic_detected = True
                            
                        if not reflex_detected:
                             print(f"[{source}]: {text[:100]}...")
                             
                    if data.get("type") == "final":
                        print(f"\n✅ FINAL RESPONSE:\n{data.get('brain')}")
                        break
                        
                except asyncio.TimeoutError:
                    continue

            print("\n--- FINAL VERDICT ---")
            print(f"Reflex Suppression: {'✅ PASS' if not reflex_detected else '❌ FAIL'}")
            print(f"Vocal Handshake: {'✅ PASS' if handshake_detected else '❌ FAIL'}")
            print(f"Semantic Reasoning: {'✅ PASS' if semantic_detected else '❌ FAIL'}")
            
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_semantic_verification())
