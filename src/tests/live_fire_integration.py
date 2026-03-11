import asyncio
import websockets
import json
import sys
import time

async def live_fire_test():
    uri = "ws://localhost:8765"
    print(f"🚀 Initializing Strategic Live Fire: {uri}")
    
    try:
        async with websockets.connect(uri) as ws:
            # 1. Handshake
            await ws.send(json.dumps({"type": "handshake", "version": "3.8.1", "client": "grounded_integrator"}))
            print("📡 Handshake Sent.")
            
            # 2. Wait for Hub Ready
            start_time = time.time()
            query_sent = False
            
            while time.time() - start_time < 180:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    
                    if data.get("type") == "status" and data.get("state") == "ready":
                        if not query_sent:
                            query = "What is the RAPL BKM for thermal profiling?"
                            print(f"🧠 Hub Ready. Sending Strategic Probe: '{query}'")
                            await ws.send(json.dumps({"type": "text_input", "content": query}))
                            query_sent = True
                    
                    if "brain" in data:
                        source = data.get("brain_source", "Unknown")
                        text = data.get("brain", "")
                        print(f"[{source}]: {text}")
                        
                        # [FEAT-172] Hemispheric Interjection Detection
                        if "Interjection" in source:
                            print("✨ SUCCESS: Detected Hemispheric Interjection (Pinky is Thinking Out Loud).")
                        
                        # [FEAT-173] Strategic Pivot Detection
                        if "derivation too thin" in text.lower():
                            print("🔄 SUCCESS: Strategic Pivot Triggered.")
                            
                        if source == "The Brain":
                            print("\n✅ FINAL VERDICT: Strategic Uplink Verified. Federated MoE is LIVE.")
                            return True
                            
                except asyncio.TimeoutError:
                    if query_sent:
                        print("⏳ Awaiting neural activity (Respecting 4090 Priming Latency)...")
                    else:
                        print("⏳ Waiting for Lab Server to report READY...")
                        
    except Exception as e:
        print(f"❌ Integration Error: {e}")
    return False

if __name__ == "__main__":
    success = asyncio.run(live_fire_test())
    if not success:
        sys.exit(1)
