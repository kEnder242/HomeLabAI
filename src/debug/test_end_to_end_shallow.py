import asyncio
import aiohttp
import json
import time

URL = "http://localhost:8765"

async def test_e2e_shallow():
    print(f"--- [TEST] End-to-End Shallow Think: {URL} ---")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect(URL) as ws:
                print("[UPLINK] Socket Connected.")
                
                # Handshake
                await ws.send_json({"type": "handshake", "version": "3.8.1"})
                
                # Wait for foyer
                async for msg in ws:
                    data = json.loads(msg.data)
                    if data.get("message") == "Lab foyer is open.":
                        break
                
                print("[CLIENT] Waiting for priming to settle...")
                await asyncio.sleep(2)
                
                print("[CLIENT] Sending Casual Query: 'hi brain'")
                start_t = time.time()
                await ws.send_json({"type": "text_input", "content": "hi brain"})
                
                brain_replied = False
                
                async for msg in ws:
                    data = json.loads(msg.data)
                    source = data.get("brain_source", "")
                    content = data.get("brain", "")
                    
                    if source:
                        print(f"[{source}] {content}")
                    
                    if "Brain" in source:
                        end_t = time.time()
                        print(f"\n[METRIC] Brain Response Latency: {end_t - start_t:.2f}s")
                        print(f"[METRIC] Content Length: {len(content.split())} words")
                        
                        if end_t - start_t < 3.0: # 2s target + network/dispatch overhead
                            print("✅ SUCCESS: Fast response detected.")
                        else:
                            print("❌ FAILURE: Latency too high.")
                            
                        if len(content.split()) < 25:
                            print("✅ SUCCESS: Short response detected.")
                        else:
                            print("❌ FAILURE: Response too verbose.")
                            
                        brain_replied = True
                        break
                    
                    if time.time() - start_t > 20:
                        print("\n❌ FAILURE: Timeout.")
                        break
                
                if not brain_replied:
                    print("\n❌ FAILURE: Brain never replied.")

        except Exception as e:
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_e2e_shallow())
