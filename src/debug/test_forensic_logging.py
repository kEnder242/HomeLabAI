import asyncio
import json
import os
import time

import websockets

SERVER_LOG = "HomeLabAI/server.log"


async def test_forensics():
    print("--- 🔍 Testing Forensic Logging & 'Bye' Feature ---")

    url = "ws://127.0.0.1:8765"
    try:
        async with websockets.connect(url) as ws:
            # 1. Send Unique Test String
            test_id = f"TEST_QUERY_{int(time.time())}"
            print(f"📤 Sending unique query: {test_id}")
            await ws.send(json.dumps({"type": "text_input", "content": test_id}))

            # Wait for processing
            await asyncio.sleep(5)

            # 2. Verify string exists in log (append check)
            if os.path.exists(SERVER_LOG):
                with open(SERVER_LOG, "r") as f:
                    content = f.read()
                    if test_id in content:
                        print("✅ Forensic Log: Unique query captured.")
                    else:
                        print("❌ Forensic Log: Unique query MISSING.")
                        return False
            else:
                print("❌ ERROR: server.log not found.")
                return False

            # 3. Test 'Bye' Feature (Shutdown)
            print("📤 Sending 'bye' to trigger feature reboot...")
            await ws.send(json.dumps({"type": "text_input", "content": "bye"}))

            # Wait for shutdown signal
            try:
                async with asyncio.timeout(10):
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if data.get("type") == "shutdown":
                            print("✅ 'Bye' Feature: Shutdown signal received.")
                            break
            except asyncio.TimeoutError:
                print("❌ 'Bye' Feature: Timeout waiting for shutdown signal.")
                return False

            # 4. Final Append Check: Did the log survive the reboot request?
            if os.path.exists(SERVER_LOG):
                with open(SERVER_LOG, "r") as f:
                    content = f.read()
                    if test_id in content:
                        print(
                            "✅ Forensic Stability: Log persisted through shutdown trigger."
                        )
                    else:
                        print("❌ Forensic Stability: Log WIPED during shutdown.")
                        return False

            return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    if asyncio.run(test_forensics()):
        print("\n✨ FORENSIC TEST PASSED\n")
    else:
        print("\n❌ FORENSIC TEST FAILED\n")
