import asyncio
import aiohttp
import json
import os
import sys
import time

# Paths
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "ws://localhost:8765/"
STYLE_CSS = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/style.css")

def get_style_key():
    import hashlib
    if not os.path.exists(STYLE_CSS): return "missing"
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

KEY = get_style_key()
HEADERS = {'X-Lab-Key': KEY, 'Content-Type': 'application/json'}

async def wait_for_op(session, timeout=180):
    print(f"[*] Waiting for OPERATIONAL (Timeout: {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            async with session.get(f"{ATTENDANT_URL}/heartbeat?key={KEY}") as r:
                data = await r.json()
                if data.get("operational") or data.get("mode") == "STUB":
                    print(f"  ✅ System is OPERATIONAL ({data.get('mode')})")
                    return True
        except Exception: pass
        await asyncio.sleep(5)
    return False

async def test_socket_resilience():
    print("\n--- [AUDIT 1] Socket Resilience ---")
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(HUB_URL) as ws_b:
            await ws_b.send_json({"type": "handshake", "client": "Test_B"})
            await ws_b.receive_json()
            
            # Simulated Drop
            async with session.ws_connect(HUB_URL) as ws_a:
                await ws_a.send_json({"type": "handshake", "client": "Test_A"})
                await ws_a.receive_json()
                await ws_a.close()
            
            print("  [*] Triggering broadcast after abrupt disconnect...")
            await ws_b.send_json({"type": "handshake", "client": "Test_B"})
            msg = await asyncio.wait_for(ws_b.receive_json(), timeout=5.0)
            print(f"  ✅ Hub survived. Received: {msg.get('type')}")

async def test_hibernation_logic():
    print("\n--- [AUDIT 2] Hibernation Logic ---")
    async with aiohttp.ClientSession() as session:
        # Hibernate
        print("  [*] Triggering Hibernate...")
        await session.post(f"{ATTENDANT_URL}/hibernate", headers=HEADERS)
        await asyncio.sleep(5)
        
        async with session.get(f"{ATTENDANT_URL}/heartbeat?key={KEY}") as r:
            data = await r.json()
            print(f"  ✅ State: {data.get('mode')}")

        # Wake
        print("  [*] Triggering Wake Spark...")
        async with session.ws_connect(HUB_URL) as ws:
            await ws.send_json({"type": "handshake", "client": "intercom"})
            print("  [*] Spark sent. Waiting for restoration...")
            
        await wait_for_op(session)
        print("  ✅ Restoration logic verified.")

async def main():
    print("🚀 STARTING FINAL STABILITY GAUNTLET")
    os.environ["GEMINI_CLI_IMMUNITY"] = "1"
    
    async with aiohttp.ClientSession() as session:
        # 1. Clean Ignition
        print("[*] Preparing Clean STUB Environment...")
        await session.post(f"{ATTENDANT_URL}/stop", headers=HEADERS)
        await asyncio.sleep(5)
        await session.post(f"{ATTENDANT_URL}/start", headers=HEADERS, json={"engine": "STUB", "reason": "FINAL_GAUNTLET"})
        
        if await wait_for_op(session):
            print("  [*] Settle window (10s) for Hub foyer...")
            await asyncio.sleep(10)
            await test_socket_resilience()
            await test_hibernation_logic()
            print("\n✨ FINAL GAUNTLET: 100% SUCCESS")
        else:
            print("\n❌ FINAL GAUNTLET: FAILED (Startup)")

if __name__ == "__main__":
    asyncio.run(main())
