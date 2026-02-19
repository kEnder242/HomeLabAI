import asyncio
import json
import websockets
import sys

async def audit():
    url = "ws://127.0.0.1:8765"
    print("--- 🧠 STRATEGIC AUDIT ---")
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            
            # 1. Trigger Strategic Query
            print("📤 Sending: 'What is the root cause of the regression?'")
            await ws.send(json.dumps({"type": "text_input", "content": "What is the root cause of the regression?"}))
            
            # Watch for Brain response
            async with asyncio.timeout(45):
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    source = data.get('brain_source', 'Unknown')
                    text = data.get('brain', '')
                    if source == "Brain":
                        print(f"✅ RECV from Brain: {text[:100]}...")
                        if text and text != "...":
                            return True
                        else:
                            print("❌ FAIL: Brain still silent or producing ellipsis.")
                            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
    return False

if __name__ == "__main__":
    if asyncio.run(audit()):
        print("\n✨ STRATEGIC AUDIT PASSED\n")
        sys.exit(0)
    else:
        print("\n❌ STRATEGIC AUDIT FAILED\n")
        sys.exit(1)
