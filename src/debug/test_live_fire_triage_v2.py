import asyncio
import websockets
import json
import uuid
import sys

async def test_live_fire():
    uri = "ws://localhost:8765"
    session_id = uuid.uuid4().hex[:4]
    # Unique query to avoid cache confusion
    query = f"[ME] [{session_id}] I don't think you can handle this query: Explain the 18-year shift from fuser-kill to REST-sleep."
    
    print(f"🚀 Initializing Strategic Triage Audit: {session_id}")
    
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "type": "handshake", 
                "version": "3.6.4", 
                "client": f"triage_audit_{session_id}"
            }))
            
            await asyncio.sleep(1)
            await ws.send(json.dumps({"type": "text_input", "content": query}))
            
            found_triage_start = False
            found_triage_success = False
            found_uplink = False
            
            print("📡 Monitoring crosstalk sequence...")
            
            # Use 120s timeout for cold-wake + inference
            start_t = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_t < 120:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)
                    source = data.get("brain_source", "Unknown")
                    text = data.get("brain", "")
                    
                    if text:
                        print(f"  [RECV] {source}: {text[:100]}...")

                    if "Triage starting" in text or "Triage Attempt" in text:
                        print(f"✅ FOUND: Triage Started")
                        found_triage_start = True
                    if "Triage successful" in text or "Triage Result:" in text:
                        print(f"✅ FOUND: Triage Success")
                        found_triage_success = True
                    if "Initiating Deep Thought" in text or "Pinky (Response)" in text:
                        print(f"✅ FOUND: Response Phase")
                        found_uplink = True
                        
                    if found_triage_start and found_triage_success and found_uplink:
                        print("\n🏆 VERDICT: Tier 3 Systematic Baseline PASS.")
                        # Wait a moment for final tokens to arrive
                        await asyncio.sleep(5)
                        return True
                        
                except asyncio.TimeoutError:
                    continue
                    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n❌ FAILED: Did not receive full crosstalk sequence.")
    return False

if __name__ == "__main__":
    if asyncio.run(test_live_fire()):
        sys.exit(0)
    else:
        sys.exit(1)
