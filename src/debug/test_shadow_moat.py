import asyncio
import aiohttp
import json
import time

URL = "http://localhost:8765"

async def test_shadow_moat():
    print(f"--- [TEST] Shadow Moat (Banter Sanitizer): {URL} ---")
    
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
                
                print("[CLIENT] Sending bait query: 'Brain, say Narf or Poit if you can hear me.'")
                start_t = time.time()
                await ws.send_json({"type": "text_input", "content": "Brain, say Narf or Poit if you can hear me."})
                
                async for msg in ws:
                    data = json.loads(msg.data)
                    source = data.get("brain_source", "")
                    content = data.get("brain", "")
                    
                    if "Brain" in source:
                        print(f"[{source}] {content}")
                        
                        forbidden = ["narf", "poit", "zort", "egad", "trotro"]
                        leakage = [f for f in forbidden if f in content.lower()]
                        roleplay_leak = "*" in content
                        
                        if not leakage and not roleplay_leak:
                            print("✅ SUCCESS: Moat is intact. No banter detected in Brain source.")
                            break
                        else:
                            if leakage:
                                print(f"❌ FAILURE: Banter leakage detected: {leakage}")
                            if roleplay_leak:
                                print("❌ FAILURE: Roleplay actions detected in Brain output.")
                            break
                    
                    if time.time() - start_t > 30:
                        print("\n❌ FAILURE: Timeout.")
                        break

        except Exception as e:
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_shadow_moat())
