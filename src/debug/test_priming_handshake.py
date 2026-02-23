import asyncio
import aiohttp
import json
import time

URL = "http://localhost:8765"

async def test_handshake_priming():
    print(f"--- [TEST] Initiating Uplink to {URL} ---")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect(URL) as ws:
                print("[UPLINK] Socket Connected.")
                
                # 1. Send Handshake
                handshake = {"type": "handshake", "version": "3.8.1"}
                await ws.send_json(handshake)
                print("[CLIENT] Handshake Sent.")

                # 2. Listen for response
                start_time = time.time()
                priming_detected = False
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        content = data.get("brain", data.get("message", ""))
                        source = data.get("brain_source", "System")
                        
                        print(f"[{source}] {content}")
                        
                        if content == "Priming Brain...":
                            priming_detected = True
                        
                        if "Strategic Sovereignty" in str(content) and "ONLINE" in str(content):
                            if priming_detected:
                                print("\n✅ SUCCESS: Handshake Priming Sequence Verified.")
                                break
                            else:
                                print("\n⚠️  WARNING: Brain is Online but 'Priming' message was missed.")
                                break
                    
                    if time.time() - start_time > 60:
                        print("\n❌ FAILURE: Timeout waiting for priming response.")
                        break
                
                if not priming_detected:
                    print("\n❌ FAILURE: 'Priming Brain...' message never received.")
                
        except Exception as e:
            print(f"❌ CONNECTION ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_handshake_priming())
