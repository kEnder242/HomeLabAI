import asyncio
import json
import websockets
import sys

async def audit():
    url = "ws://127.0.0.1:8765"
    print("--- 🛡️ HARDENED GATE AUDIT ---")
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            
            # 1. Drain initial system messages
            print("⏳ Draining startup messages...")
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(msg)
                if data.get('state') == 'ready':
                    print("✅ Lab Ready.")
                    break
            
            # 2. Test Casual Greeting
            print("📤 Sending: 'hi Pinky!'")
            await ws.send(json.dumps({"type": "text_input", "content": "hi Pinky!"}))
            
            # Watch for 10 seconds.
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < 10:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(msg)
                    source = data.get('brain_source', 'Unknown')
                    
                    # IGNORE system messages in the audit
                    if source == "System":
                        continue
                        
                    if source == "Brain":
                        print(f"❌ FAIL: Brain responded! Text: {data.get('brain')}")
                        return False
                    
                    if source == "Pinky":
                        print(f"✅ RECV: Pinky handled it correctly.")
                        return True
                except asyncio.TimeoutError:
                    continue
            
            print("❌ FAIL: No response from Pinky.")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
    return False

if __name__ == "__main__":
    if asyncio.run(audit()):
        print("\n✨ GATE AUDIT PASSED\n")
        sys.exit(0)
    else:
        print("\n❌ GATE AUDIT FAILED\n")
        sys.exit(1)
