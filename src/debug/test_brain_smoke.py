import asyncio
import json
import aiohttp
import sys
import os
import time

# Paths
HUB_URL = "ws://localhost:8765"

async def test_brain_smoke():
    """[FEAT-251.4] Simple smoke test to verify Brain/Shadow response via Hub."""
    print("--- [TEST] Brain Cognitive Smoke Test ---")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(HUB_URL) as ws:
                print("[STEP 1] Performing Handshake...")
                await ws.send_str(json.dumps({"type": "handshake", "client": "SmokeTest"}))
                handshake_resp = await ws.receive_json(timeout=5)
                print(f"  ✅ Hub Status: {handshake_resp.get('status')}")

                print("\n[STEP 2] Sending Technical Query to Brain...")
                # Using [ME] prefix and addressing BRAIN to trigger deep reasoning/failover
                query = "[ME] Brain, provide a one-sentence summary of your current technical capability."
                await ws.send_str(json.dumps({"type": "text_input", "content": query}))
                
                print("  [WAIT] Awaiting technical synthesis...")
                
                start_wait = time.time()
                received_response = False
                while time.time() - start_wait < 120: # 120s timeout for engine response
                    try:
                        msg = await ws.receive_json(timeout=1)
                        
                        # Handle the 'Warming' crosstalk
                        if msg.get("type") == "crosstalk" and "warming" in msg.get("brain", "").lower():
                            print("  [WAIT] Larynx is warming... Narf!")
                            continue

                        # We are looking for the final result from either Brain or Shadow (Failover)
                        source = msg.get("brain_source", "")
                        if source in ["Brain (Result)", "Shadow (Failover)", "Shadow (Intuition)"]:
                            text = msg.get("brain", "")
                            if text:
                                # ERROR DETECTION
                                error_keywords = ["error:", "failed", "404", "none", "refused", "offline", "traceback"]
                                if any(k in text.lower() for k in error_keywords):
                                    print(f"  ❌ FAILED: Received error response from {source}:")
                                    print(f"     \"{text[:200]}\"")
                                    return
                                
                                print(f"  ✅ SUCCESS: Received response from {source}:")
                                print(f"     \"{text}\"")
                                received_response = True
                                break
                    except asyncio.TimeoutError:
                        continue
                
                if not received_response:
                    print("  ❌ FAILED: Timed out waiting for Brain/Shadow response.")
                else:
                    print("\n--- [RESULT] Brain is COGNITIVELY ACTIVE ---")

    except Exception as e:
        print(f"  ❌ Connection Failed: {e}")
        print("     Ensure the Lab Hub is running on port 8765.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Allow passing a custom query for manual testing
        custom_query = sys.argv[1]
        asyncio.run(test_brain_smoke())
    else:
        asyncio.run(test_brain_smoke())
