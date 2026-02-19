import asyncio
import json
import websockets
import sys

async def audit():
    url = "ws://127.0.0.1:8765"
    print("--- 🎤 MIC TOGGLE AUDIT ---")
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            await ws.recv(); await ws.recv() # Consume init
            
            # Test 1: Enable Mic
            print("📤 Sending: mic_state active=True")
            await ws.send(json.dumps({"type": "mic_state", "active": True}))
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get('type') == 'status' and 'Mic' in data.get('message', ''):
                    print(f"   [RECV] {data.get('message')}")
                    if data.get('mic_active') == True:
                        print("✅ PASS: Mic state enabled.")
                        break
                
            # Test 2: Disable Mic
            print("📤 Sending: mic_state active=False")
            await ws.send(json.dumps({"type": "mic_state", "active": False}))
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get('type') == 'status' and 'Mic' in data.get('message', ''):
                    print(f"   [RECV] {data.get('message')}")
                    if data.get('mic_active') == False:
                        print("✅ PASS: Mic state disabled.")
                        break
                
            return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
    return False

if __name__ == "__main__":
    if asyncio.run(audit()):
        print("\n✨ MIC AUDIT PASSED\n")
        sys.exit(0)
    else:
        print("\n❌ MIC AUDIT FAILED\n")
        sys.exit(1)
