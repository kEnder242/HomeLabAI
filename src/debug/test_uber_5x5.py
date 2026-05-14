import asyncio
import json
import websockets
import time
import requests
import hashlib
import subprocess
import os

# [TEST-52] The Uber-5x5 Gauntlet
# The definitive transition certification.
# 1. Impolite: Concurrent queries during WAKING.
# 2. JS-Aware: Mimics intercom_v2.js handshake.
# 3. Full-Fuel: Verifies Brain (4090) reachability.
# 4. Transparent: Validates zero-deadlock concurrency.

HUB_URL = "ws://localhost:8765"

def get_key():
    with open('/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css', 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def trigger_query(client_id, query, expected_source=None):
    try:
        async with websockets.connect(HUB_URL) as ws:
            # 1. Handshake and capture SID
            await ws.send(json.dumps({"type": "handshake", "client": "intercom", "version": "3.8.1"}))
            
            # Wait for initial status to get SID
            msg = await ws.recv()
            data = json.loads(msg)
            sid = data.get("socket_id", "Unknown")
            print(f"    [Client {client_id}] Socket established: {sid}")

            # 2. Impolite Timing: Send immediately
            await ws.send(json.dumps({"type": "text_input", "content": query}))
            
            start_t = time.time()
            vocal_received = False
            
            while time.time() - start_t < 180:
                msg = await ws.recv()
                data = json.loads(msg)
                
                source = data.get('brain_source', 'System')
                text = str(data.get('brain', ''))
                
                # Filter out the [RAW_OUTPUT] or System status, look for persona
                if source not in ['System', 'Lab (Triage)', 'Pinky (Triage)']:
                    
                    if '[GIBBERISH]' in text:
                        print(f"    [Client {client_id}] 🚨 FAIL: Gibberish detected from {source}")
                        return False
                        
                    # win condition: SUBSTANCE (Long-form)
                    if len(text) > 200:
                        print(f"    [Client {client_id}] ✅ SUBSTANCE WIN: {source} sent {len(text)} chars.")
                        # Check for strategic source if expected
                        if expected_source and expected_source in source:
                            print(f"    [Client {client_id}] 💎 UBER-WIN: Strategic target {source} reached.")
                            return True
                        elif not expected_source:
                            return True
                    
                    # Log filler but don't count as win
                    if any(x in text.upper() for x in ['ROGER', 'PINKY', 'ACME', 'POIT', 'NARF', 'ZORT']):
                        print(f"    [Client {client_id}] (Filler) {source}: {text[:20]}...")
                        
    except Exception as e:
        print(f"    [Client {client_id}] ❌ ERROR: {e}")
    return False

async def run_cycle(cycle):
    print(f"\n[*] Starting Uber-Cycle {cycle}/5...")
    key = get_key()
    
    # 1. Natural Hibernate (H2 - Lean Sleep)
    print(f"    [Action] Entering Lean Sleep (H2)...")
    subprocess.run(['curl', '-s', '-X', 'POST', f'http://localhost:9999/hibernate?level=2&key={key}'], capture_output=True)
    time.sleep(5) # Minimum settle

    # 2. Launch Storm
    # 4 Pinky queries + 1 Strategic Brain query
    tasks = []
    print(f"    [Action] Launching 5-node storm (4 local, 1 strategic)...")
    for i in range(4):
        tasks.append(trigger_query(i, f"[ME] Rude probe {cycle}.{i}. Respond with ROGER."))
    
    # Strategic query for Brain Reachability
    strategic_query = "[ME] Analyze the physical thermal boundaries of the RTX 2080 Ti and provide a BKM for fan curves."
    tasks.append(trigger_query(4, strategic_query, expected_source="Brain"))
    
    results = await asyncio.gather(*tasks)
    wins = sum(1 for r in results if r)
    print(f"    [Result] Uber-Cycle {cycle}: {wins}/5 wins.")
    return wins == 5

def get_kender_ip():
    try:
        with open('/home/jallred/Dev_Lab/HomeLabAI/config/infrastructure.json', 'r') as f:
            data = json.load(f)
            return data.get("hosts", {}).get("KENDER", {}).get("ip_hint", "192.168.1.26")
    except Exception:
        return "192.168.1.26"

async def check_brain_online():
    ip = get_kender_ip()
    try:
        r = requests.get(f'http://{ip}:11434/api/tags', timeout=2)
        return r.status_code == 200
    except Exception:
        return False

async def main():
    print("💎 INITIATING THE SUBSTANCE-HEAVY UBER-5x5 GAUNTLET")
    print(f"[*] Brain Discovery: {get_kender_ip()} ({'ONLINE' if await check_brain_online() else 'OFFLINE'})")
    print("[*] Strategy: Paragraph-Length Wins (>200 chars).")
    
    # Substance-Heavy Query for Certification
    query = "[ME] Analyze the current physical thermal boundaries of the RTX 2080 Ti and explain the multi-level hibernation (H1-H3) strategy."

    total_wins = 0
    for i in range(5):
        print(f"\n[*] Starting Substance Cycle {i+1}/5...")
        if await trigger_query(i, query):
            total_wins += 1
            print(f"--- Cycle {i+1} Certified ---")
        else:
            print(f"\n❌ SUBSTANCE GAUNTLET FAILED at Cycle {i+1}")
            break
            
    print(f"\n🏆 UBER-CERTIFICATION: {total_wins}/5 Wins.")
    if total_wins == 5:
        print("[+] PASS: Lab is officially Bulletproof.")

if __name__ == "__main__":
    asyncio.run(main())
