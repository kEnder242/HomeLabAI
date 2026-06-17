import asyncio
import json
import websockets
import time
import requests
import hashlib

# [TEST-48] Screaming Lab Replicator
# Forcefully induces physical VRAM corruption by triggering the Double Ignition race.

HUB_URL = "ws://localhost:8765"

def get_key():
    with open("/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css", "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def stress_ignition(client_id, delay):
    await asyncio.sleep(delay)
    try:
        async with websockets.connect(HUB_URL) as ws:
            # 1. Immediate handshake
            await ws.send(json.dumps({"type": "handshake", "client": "intercom"})) # Use 'intercom' to bypass gate
            # 2. Immediate prompt to trigger 'WAKE_INTENT' ignition
            await ws.send(json.dumps({"type": "text_input", "content": f"[ME] Chaos probe {client_id}"}))
            
            # Wait for response
            msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
            print(f"[Client {client_id}] Initial: {msg[:100]}")
            
    except Exception as e:
        print(f"[Client {client_id}] Connection error: {e}")

async def main():
    print("☣️  INITIATING CHAOS STORM: Inducing 'Screaming Lab'...")
    key = get_key()
    
    # 1. Force Hibernation (Ensure weights are offloaded)
    print("[*] Leveling silicon to H1...")
    requests.post(f"http://localhost:8765/hibernate?level=1&key={key}")
    time.sleep(10)
    
    # 2. Fire Burst
    print("[*] Launching 2-node ignition storm...")
    tasks = []
    # Two nodes with 0.2s gap to hit the await window
    tasks.append(stress_ignition(0, 0.0))
    tasks.append(stress_ignition(1, 0.2))
    
    await asyncio.gather(*tasks)
    print("\n[*] Storm complete. Auditing silicon...")
    
    # 3. Audit
    time.sleep(5)
    try:
        res = requests.post("http://localhost:8088/v1/chat/completions", json={
            "model": "unified-base",
            "messages": [{"role": "user", "content": "Respond with ROGER."}],
            "max_tokens": 10,
            "temperature": 0.0
        }, timeout=10)
        output = res.json()['choices'][0]['message']['content']
        print(f"\n[PHYSICAL AUDIT] Result: {output}")
        
        if "!!!!" in output:
            print("🚨 SUCCESS: 'Screaming Lab' reproduced. Silicon is corrupted.")
        else:
            print("⚠️ FAILURE: Silicon remains vocal. Adjust timing and retry.")
    except Exception as e:
        print(f"[!] Audit failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
