import asyncio
import json
import logging
import time
import websockets
import sys
import os
import uuid

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

class ProbeV2:
    """[TOOL-015] Probe v2.0: Bundle-Aware Bicameral Auditor."""
    def __init__(self, uri="ws://localhost:8765"):
        self.uri = uri
        self.active_bundles = {} # turn_id -> list of packets

    async def run_audit(self):
        print(f"[PROBE v2.0] Connecting to {self.uri}...")
        try:
            async with websockets.connect(self.uri) as ws:
                # 1. Handshake
                await ws.send(json.dumps({"type": "handshake"}))
                print("[BOOT] Handshake sent.")

                # 2. Test Scenarios
                queries = [
                    "What is the current VRAM status? Use your hardware perspective.",
                    "Are you pondering what I'm pondering?",
                    "Bye"
                ]

                for q in queries:
                    print(f"\n[USER] -> {q}")
                    await ws.send(json.dumps({"type": "text_input", "content": q}))
                    
                    # Collector Loop for this specific turn
                    start_t = time.time()
                    responses_received = []
                    
                    while time.time() - start_t < 15.0: # 15s timeout for deep thinking
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            data = json.loads(msg)
                            
                            source = data.get("brain_source") or data.get("source") or "System"
                            text = data.get("brain") or data.get("text") or data.get("reply_to_user")
                            
                            if text:
                                # Clean up formatting if it's a dict
                                if isinstance(text, dict):
                                    text = json.dumps(text)
                                print(f"  [{source}] {text}")
                                if source in ["Pinky", "Brain", "The Brain"]:
                                    responses_received.append(source)
                            
                            # If we have both Pinky and Brain, the bundle is likely complete
                            if "Pinky" in responses_received and "Brain" in responses_received:
                                print("  [BUNDLE] Complete.")
                                break
                                
                            # Status packets as heartbeat
                            if data.get("type") == "status":
                                density = data.get("vitals", {}).get("turn_density", "N/A")
                                # print(f"  [STATUS] Density: {density}")
                                
                        except asyncio.TimeoutError:
                            continue
                    
                    await asyncio.sleep(2) # User thinking delay

        except Exception as e:
            print(f"[PROBE] Audit Error: {e}")

if __name__ == "__main__":
    audit = ProbeV2()
    asyncio.run(audit.run_audit())
