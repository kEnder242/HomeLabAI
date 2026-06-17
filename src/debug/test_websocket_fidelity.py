import asyncio
import websockets
import json
import time
import requests

WS_URL = "ws://localhost:8765"

async def test_streaming_fidelity():
    print("🚀 Initializing Streaming Fidelity Test...")
    
    # Ensure Lab is WAKE
    print("[*] Ensuring Lab is OPERATIONAL...")
    try:
        requests.post("http://localhost:8765/wake", timeout=5)
    except Exception:
        print("  [WARNING] Failed to trigger WAKE signal.")
    
    async with websockets.connect(WS_URL) as ws:
        # Handshake
        await ws.send(json.dumps({"type": "handshake", "version": "3.8.1", "client": "fidelity_test"}))
        
        # Wait for handshake response
        try:
            hs_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            hs = json.loads(hs_raw)
            print(f"  [HANDSHAKE] Server Version: {hs.get('version')}")
        except Exception:
            print("  [WARNING] No handshake response.")

        # Send query
        query_id = "FIDELITY_" + str(int(time.time()))
        print(f"📡 Sending Query: {query_id}")
        await ws.send(json.dumps({
            "type": "text_input",
            "content": "[ME] Hello, what is your current vibe?",
            "request_id": query_id
        }))
        
        token_count = 0
        final_received = False
        start_time = time.time()
        
        while time.time() - start_time < 180:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=20.0)
                data = json.loads(msg)
                
                m_type = data.get("type", "unknown")
                source = data.get("brain_source", data.get("source", "Unknown"))
                content = data.get("brain", data.get("text", ""))
                final = data.get("final", False)
                channel = data.get("channel", "chat")
                
                if m_type == "status":
                    print(f"  [STATUS] {data.get('state')}: {data.get('message')}")
                    continue
                
                print(f"  [{m_type.upper()}] Src: {source:15} | Ch: {channel:8} | Final: {str(final):5} | Content: {content[:40]}...")
                
                if m_type == "chat" and not final and len(content) > 0:
                    token_count += 1
                        
                if final and "Response" in source:
                    final_received = True
                    print(f"✅ Final response received from {source}.")
                    break
            except asyncio.TimeoutError:
                print("⏳ Timeout waiting for message...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                break
        
        if final_received:
            print(f"🏆 FIDELITY TEST PASS. Received {token_count} streaming tokens.")
        else:
            print("❌ FIDELITY TEST FAIL. No final response.")

if __name__ == "__main__":
    asyncio.run(test_streaming_fidelity())
