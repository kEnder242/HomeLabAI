import asyncio
import json
import websockets
import os
import time
import requests

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
WS_URL = "ws://127.0.0.1:8765"
HB_URL = "http://127.0.0.1:9999/heartbeat"

async def repro_collision():
    print("[#] Starting High-Fidelity Hub Collision Reproduction...")
    
    # 1. Trigger Hibernate to ensure clean start
    style_key = ""
    try:
        import hashlib
        with open("/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css", "rb") as f:
            style_key = hashlib.md5(f.read()).hexdigest()[:8]
        requests.post("http://127.0.0.1:9999/hibernate", headers={"X-Lab-Key": style_key}, json={"reason": "REPRO"})
        print("[+] Lab set to HIBERNATING.")
        await asyncio.sleep(5)
    except: pass

    try:
        async with websockets.connect(WS_URL) as websocket:
            # Handshake
            await websocket.send(json.dumps({"type": "handshake", "client": "intercom", "version": "4.5"}))
            await websocket.recv()
            print("[+] Connected to Lobby.")

            # 2. Trigger RAPID-FIRE Queries
            print("[*] Sending RAPID-FIRE wake queries (Collision simulation)...")
            # First query triggers the ignition
            await websocket.send(json.dumps({"type": "query", "content": "[ME] Wake up query 1"}))
            await asyncio.sleep(0.5)
            # Second query should NOT trigger a second ignition
            await websocket.send(json.dumps({"type": "query", "content": "[ME] Wake up query 2"}))
            
            # 3. Monitor for Disconnect
            print("[*] Monitoring for Hub Murder (60s window)...")
            start_t = time.time()
            while time.time() - start_t < 60:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                    data = json.loads(msg)
                    if data.get("type") == "crosstalk":
                        print(f"    [CROSSTALK]: {data.get('brain')}")
                except asyncio.TimeoutError:
                    print("    [TIMEOUT] Still waiting...")
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"\n[!] REPRODUCED: WebSocket physically closed (Murdered). Code: {e.code}")
                    print("[+] CONCLUSION: Redundant ignition kills the active Hub.")
                    return True
            
            print("\n[-] FAILURE: Hub survived. No collision detected.")
            return False

    except Exception as e:
        print(f"[!] Test Error: {e}")

if __name__ == "__main__":
    asyncio.run(repro_collision())
