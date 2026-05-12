import asyncio
import json
import websockets
import time
import requests
import hashlib
import subprocess
import os

# [FEAT-342] The Rude Gauntlet
# Certifies transition stability by sending concurrent queries to a HIBERNATING lab.
# This avoids the "Warm Path" trap and forces the Wake-on-Intent logic.

HUB_URL = "ws://localhost:8765"

def get_style_key():
    with open('/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css', 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def trigger_query(client_id, query):
    try:
        async with websockets.connect(HUB_URL) as ws:
            await ws.send(json.dumps({"type": "handshake", "client": "intercom"}))
            # Immediate prompt - No waiting for operational signal
            await ws.send(json.dumps({"type": "text_input", "content": query}))
            
            start_t = time.time()
            while time.time() - start_t < 180: # 3-minute window for cold H2 wake
                msg = await ws.recv()
                data = json.loads(msg)
                
                if data.get('brain_source') in ['Pinky', 'Shadow', 'Lab']:
                    text = str(data.get('brain', ''))
                    if any(x in text.upper() for x in ['ROGER', 'PINKY', 'ACME', 'POIT', 'NARF', 'ZORT']):
                        print(f"    [Client {client_id}] SUCCESS: {text[:40]}...")
                        return True
                    if '[GIBBERISH]' in text:
                        print(f"    [Client {client_id}] FAIL: Physical corruption detected!")
                        return False
    except Exception as e:
        print(f"    [Client {client_id}] ERROR: {e}")
    return False

async def run_cycle(cycle):
    print(f"\n[*] Starting Rude Cycle {cycle}/5...")
    key = get_style_key()
    
    # 1. Force Hibernate (H2 - Lean Sleep)
    print(f"    [Action] Entering Lean Sleep (H2)...")
    subprocess.run(['curl', '-s', '-X', 'POST', f'http://localhost:9999/hibernate?level=2&key={key}'], capture_output=True)
    time.sleep(10) # Settle

    # 2. Fire Rude Storm (5 concurrent queries to sleeping lab)
    print(f"    [Action] Launching 5-node 'Wake-on-Intent' storm...")
    tasks = []
    for i in range(5):
        tasks.append(trigger_query(i, f"[ME] Rude Check {cycle}.{i}. Respond with ROGER."))
    
    results = await asyncio.gather(*tasks)
    wins = sum(1 for r in results if r)
    print(f"    [Result] Cycle {cycle} Wins: {wins}/5")
    return wins == 5

async def main():
    print("🔥 INITIATING THE RUDE GAUNTLET (Transition Stability Certification)")
    print("[*] Strategy: Send concurrent queries to HIBERNATING lab (No Warm Path).")
    
    total_wins = 0
    for i in range(5):
        if await run_cycle(i + 1):
            total_wins += 1
            print(f"--- Cycle {i+1} Passed (Logical & Physical Integrity Verified) ---")
        else:
            print(f"\n❌ RUDE GAUNTLET FAILED at Cycle {i+1}")
            break
            
    print(f"\n🏆 GAUNTLET COMPLETE. Rude H2 Wins: {total_wins}/5")

if __name__ == "__main__":
    asyncio.run(main())
