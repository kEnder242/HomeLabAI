import asyncio
import json
import sys

import websockets


async def audit():
    url = "ws://127.0.0.1:8765"
    print("--- 🎭 PERSONA AUDIT ---")
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            await ws.recv()
            await ws.recv()  # Consume init

            # Test 1: Casual Greeting (Should be Pinky only)
            print("📤 Sending: 'hello there'")
            await ws.send(json.dumps({"type": "text_input", "content": "hello there"}))

            async with asyncio.timeout(15):
                msg = await ws.recv()
                data = json.loads(msg)
                source = data.get("brain_source", "Unknown")
                text = data.get("brain", "")
                print(f"   [RECV] Source: {source} | Text: {text[:50]}...")
                if source == "Brain":
                    print("❌ FAIL: Brain woke up for a casual greeting.")
                    return False

            # Test 2: Strategic Query (Should be Brain and Narf-free)
            print("📤 Sending: 'root cause of regression'")
            await ws.send(
                json.dumps(
                    {"type": "text_input", "content": "root cause of regression"}
                )
            )

            async with asyncio.timeout(30):
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    source = data.get("brain_source", "Unknown")
                    text = data.get("brain", "")
                    if source == "Brain":
                        print(f"   [RECV] Source: {source} | Text: {text[:50]}...")
                        if "Narf" in text or "Poit" in text or "Egad" in text:
                            print("❌ FAIL: Brain leaked Pinky's persona!")
                            return False
                        print("✅ PASS: Brain responded professionally.")
                        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
    return False


if __name__ == "__main__":
    if asyncio.run(audit()):
        print("\n✨ PERSONA AUDIT PASSED\n")
        sys.exit(0)
    else:
        print("\n❌ PERSONA AUDIT FAILED\n")
        sys.exit(1)
