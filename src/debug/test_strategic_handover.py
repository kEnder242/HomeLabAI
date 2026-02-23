import asyncio
import aiohttp
import json
import time

URL = "http://localhost:8765"

async def test_strategic_handover():
    print(f"--- [TEST] Strategic Handover (MAS): {URL} ---")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect(URL) as ws:
                # Handshake
                await ws.send_json({"type": "handshake", "version": "3.8.1"})
                
                # Consume initial junk
                async for msg in ws:
                    data = json.loads(msg.data)
                    if data.get("message") == "Lab foyer is open.":
                        break
                
                print("[CLIENT] Waiting for priming...")
                await asyncio.sleep(2)
                
                query = "Brain, analyze the bottleneck in our current IPC loop."
                print(f"[CLIENT] Sending Strategic Query: '{query}'")
                start_t = time.time()
                await ws.send_json({"type": "text_input", "content": query})
                
                events = []
                
                async for msg in ws:
                    data = json.loads(msg.data)
                    source = data.get("brain_source", "")
                    content = data.get("brain", "")
                    
                    if source:
                        print(f"[{source}] {content[:100]}...")
                        
                        # Event 1: Pinky Filler (Agentic Reflection)
                        if source == "Pinky":
                            if any(k in content for k in ["Hmm", "Wait", "Poit", "let me"]):
                                if "PINKY_FILLER" not in events:
                                    print(f"✅ EVENT: Pinky Filler detected at {time.time() - start_t:.2f}s")
                                    events.append("PINKY_FILLER")
                        
                        # Event 2: Brain Quip (Handover Signal)
                        if "Brain" in source and len(content.split()) < 20:
                            if "BRAIN_QUIP" not in events:
                                print(f"✅ EVENT: Brain Quip detected at {time.time() - start_t:.2f}s")
                                events.append("BRAIN_QUIP")
                        
                        # Event 3: Brain Deep (The Real Answer)
                        if "Brain" in source and len(content.split()) >= 20:
                            if "BRAIN_DEEP" not in events:
                                print(f"✅ EVENT: Brain Deep detected at {time.time() - start_t:.2f}s")
                                events.append("BRAIN_DEEP")
                                break
                    
                    if time.time() - start_t > 120: # High timeout for deep reasoning
                        print("\n❌ FAILURE: Timeout.")
                        break
                
                print(f"\n[FINAL] Sequence Captured: {events}")
                
                assert "PINKY_FILLER" in events, "Pinky failed to provide organic filler."
                assert "BRAIN_QUIP" in events, "Brain failed to provide perk-up signal."
                assert "BRAIN_DEEP" in events, "Brain failed to deliver analysis."
                print("\n✅ SUCCESS: Agentic Reflection sequence verified.")

        except Exception as e:
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_strategic_handover())
