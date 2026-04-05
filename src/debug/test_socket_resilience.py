import asyncio
import aiohttp
import json
import os
import sys

# Ensure we are in the right directory
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
HUB_URL = "ws://localhost:8765/"

async def test_socket_resilience():
    print("[*] Starting Socket Resilience Audit...")
    
    async with aiohttp.ClientSession() as session:
        # 1. Connect Client A
        print("  [+] Connecting Client A...")
        ws_a = await session.ws_connect(HUB_URL)
        await ws_a.send_json({"type": "handshake", "client": "Test_A"})
        resp_a = await ws_a.receive_json()
        print(f"    [A] Handshake: {resp_a.get('state')}")

        # 2. Connect Client B
        print("  [+] Connecting Client B...")
        ws_b = await session.ws_connect(HUB_URL)
        await ws_b.send_json({"type": "handshake", "client": "Test_B"})
        resp_b = await ws_b.receive_json()
        print(f"    [B] Handshake: {resp_b.get('state')}")

        # 3. Abruptly Close A (Simulate F5/Disconnect)
        print("  [!] Abruptly closing Client A transport...")
        await ws_a.close()
        # We don't close the session yet to simulate a raw socket drop
        
        # 4. Trigger Broadcast (Handshake from B)
        print("  [*] Triggering broadcast from B. Hub must not crash.")
        await ws_b.send_json({"type": "handshake", "client": "Test_B"})
        
        try:
            # Wait for B to receive its status update
            msg = await asyncio.wait_for(ws_b.receive_json(), timeout=5.0)
            print(f"  ✅ SUCCESS: Hub is stable. Received type: {msg.get('type')}")
        except asyncio.TimeoutError:
            print("  ❌ FAILED: Hub timed out. Possible crash or deadlock.")
            return False
        except Exception as e:
            print(f"  ❌ FAILED: Encoutered error: {e}")
            return False

        await ws_b.close()
    
    print("[*] Audit Complete.")
    return True

if __name__ == "__main__":
    os.environ["GEMINI_CLI_IMMUNITY"] = "1"
    asyncio.run(test_socket_resilience())
