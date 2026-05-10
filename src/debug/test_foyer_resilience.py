import asyncio
import json
import websockets
import time
import threading

# [FEAT-339] Foyer Resilience Test (The "Drunken Foyer" Simulator)
# Specifically sends concurrent queries during the ignition/wake-up window.

HUB_URL = "ws://localhost:8765"

async def trigger_query(query, client_id):
    try:
        async with websockets.connect(HUB_URL) as ws:
            # 1. Immediate handshake
            await ws.send(json.dumps({"type": "handshake", "client": f"burst_{client_id}"}))
            # 2. Immediate prompt (sent while Hub is logical but engine is offloaded)
            await ws.send(json.dumps({"type": "text_input", "content": query}))
            
            start_t = time.time()
            seen_ids = set()
            duplicates = 0
            
            while time.time() - start_t < 60:
                msg = await ws.recv()
                data = json.loads(msg)
                
                mid = data.get("msg_id")
                if mid:
                    if mid in seen_ids:
                        duplicates += 1
                    seen_ids.add(mid)
                
                # Check for operational signal
                if "Mind is OPERATIONAL" in str(data.get('brain', '')):
                    print(f"[Client {client_id}] Success. Latency: {time.time() - start_t:.2f}s. Duplicates caught: {duplicates}")
                    return True
    except Exception as e:
        print(f"[Client {client_id}] Connection/Protocol Error: {e}")
    return False

async def main():
    print("🔥 INITIATING FOYER RESILIENCE TEST (5 concurrent queries during wake)...")
    print("[*] Note: This should trigger exactly ONE spark and catch all duplicates.")
    
    # Ensure lab is hibernating first for a true test
    import requests
    try:
        # Get key from style.css
        import hashlib
        with open("/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css", "rb") as f:
            key = hashlib.md5(f.read()).hexdigest()[:8]
        requests.post(f"http://localhost:9999/hibernate?level=1&key={key}")
        print("[*] Triggered H1 Hibernation. Waiting 5s for settle...")
        time.sleep(5)
    except Exception as e:
        print(f"[!] Pre-test hibernation failed: {e}")

    tasks = []
    for i in range(5):
        tasks.append(trigger_query(f"[ME] Resilience check {i}", i))
    
    results = await asyncio.gather(*tasks)
    success_count = sum(1 for r in results if r)
    print(f"\n✅ FOYER RESILIENCE COMPLETE. Success: {success_count}/5")
    if success_count == 5:
        print("[+] PASS: Hub correctly handled the concurrent ignition storm.")
    else:
        print("[!] FAIL: Hub state machine fragmented during burst.")

if __name__ == "__main__":
    asyncio.run(main())
