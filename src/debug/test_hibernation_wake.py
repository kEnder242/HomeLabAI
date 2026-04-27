import asyncio
import json
import requests
import websockets
import os
import time

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
ATTENDANT_URL = "http://127.0.0.1:9999"
WS_URL = "ws://127.0.0.1:8765"

def get_style_key():
    import hashlib
    style_path = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"
    with open(style_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def test_hibernation_wake():
    style_key = get_style_key()
    headers = {"X-Lab-Key": style_key}
    
    print("[#] Initiating Hibernation Wake Test...")
    
    # 1. Trigger Hibernate
    print("[#] Triggering manual hibernation...")
    res = requests.post(f"{ATTENDANT_URL}/hibernate", headers=headers, json={"reason": "TEST_COLD_WAKE"})
    print(f"[+] Attendant Response: {res.json()}")
    
    # 2. Wait for HIBERNATING state and VRAM drop
    print("[#] Waiting for hibernation stability (Max 60s)...")
    hibernated = False
    for _ in range(30):
        hb = requests.get(f"{ATTENDANT_URL}/heartbeat").json()
        vram = hb.get("vram_mib", 0)
        mode = hb.get("mode", "Unknown")
        print(f"    [VITALS] State: {mode} | VRAM: {vram}MB")
        
        if mode == "HIBERNATING" or vram < 2000:
            print("[+] SUCCESS: Silicon is cold.")
            hibernated = True
            break
        await asyncio.sleep(2)
        
    if not hibernated:
        print("[!] FAILURE: Lab failed to hibernate in time.")
        return

    # 3. Connect and Wake
    print("[#] Simulating external connection to wake the mind...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            # Send Handshake
            await websocket.send(json.dumps({"type": "handshake", "client": "wake_test", "version": "4.5"}))
            
            # Send Wake Query
            print("[#] Sending wake query: 'Hello Brain, wake up!'")
            await websocket.send(json.dumps({"type": "query", "content": "Hello Brain, wake up!"}))
            
            # 4. Monitor for WAKING -> OPERATIONAL
            start_t = time.time()
            vocal_received = False
            while time.time() - start_t < 180: # 3 min timeout for vLLM reload
                msg = await websocket.recv()
                data = json.loads(msg)
                
                if data.get("type") == "crosstalk":
                    text = data.get("brain", "")
                    print(f"    [CROSSTALK]: {text}")
                    if "[WAKE]" in text or "Mind is OPERATIONAL" in text:
                        print("[+] SUCCESS: Mind is vocal!")
                        vocal_received = True
                        break
                
                if data.get("type") == "chat":
                    print(f"\n[RESPONSE]: {data.get('content')}")
                    vocal_received = True
                    break

            if not vocal_received:
                print("[!] FAILURE: Lab failed to reach operational state.")

    except Exception as e:
        print(f"[!] Test Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_hibernation_wake())
