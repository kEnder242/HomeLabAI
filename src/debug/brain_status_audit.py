import asyncio
import json
import websockets
import sys

async def audit():
    url = "ws://127.0.0.1:8765"
    print("--- 🧠 BRAIN STATUS AUDIT ---")
    try:
        async with websockets.connect(url) as ws:
            # 1. Check Initial Status
            print("⏳ Awaiting initial status handshake...")
            async with asyncio.timeout(10):
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get('brain') and 'Strategic Sovereignty' in data.get('brain'):
                        print(f"   [RECV] {data.get('brain')}")
                        break
            
            # 2. Trigger Engagement Feedback
            print("📤 Sending strategic query to trigger engagement feedback...")
            await ws.send(json.dumps({"type": "text_input", "content": "root cause of regression"}))
            
            async with asyncio.timeout(15):
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get('brain') and 'Engaging' in data.get('brain'):
                        print(f"   [RECV] {data.get('brain')}")
                        print("✅ PASS: Engagement feedback received.")
                        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
    return False

if __name__ == "__main__":
    if asyncio.run(audit()):
        print("\n✨ BRAIN STATUS PASSED\n")
        sys.exit(0)
    else:
        print("\n❌ BRAIN STATUS FAILED\n")
        sys.exit(1)
