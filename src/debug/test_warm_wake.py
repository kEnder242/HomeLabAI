import asyncio
import aiohttp
import time
import json
import os
import psutil
import subprocess

ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "ws://localhost:8765"
STYLE_KEY = "92e785ba"

async def get_status():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{ATTENDANT_URL}/status?key={STYLE_KEY}") as r:
            return await r.json()

async def get_resident_count():
    count = 0
    for proc in psutil.process_iter(['cmdline']):
        try:
            cmd = proc.info['cmdline']
            if cmd and "nodes/" in " ".join(cmd):
                count += 1
        except:
            continue
    return count

async def trigger_query(query):
    import websockets
    async with websockets.connect(HUB_URL) as ws:
        await ws.send(json.dumps({"type": "handshake", "client": "warm_wake_test"}))
        await ws.send(json.dumps({"type": "text_input", "content": query}))
        
        start_t = time.time()
        while time.time() - start_t < 120:
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"[WS] {data.get('brain_source', 'System')}: {data.get('brain', '')[:50]}...")
            if "Mind is OPERATIONAL" in str(data.get('brain', '')):
                return time.time() - start_t
    return -1

async def main():
    print("=== 🔋 WARM WAKE VALIDATION [FEAT-337] ===")
    
    # 1. Cleanup check
    initial_nodes = await get_resident_count()
    print(f"[*] Initial resident nodes: {initial_nodes}")
    
    # 2. Start Hub if not running
    # (Assuming it will be started by my next tool call or already running)
    
    # 3. First Wake (Cold)
    print("[*] Triggering Cold Wake...")
    cold_time = await trigger_query("[ME] Hello Lab.")
    print(f"[+] Cold Wake Time: {cold_time:.2f}s")
    
    nodes_after_cold = await get_resident_count()
    print(f"[*] Resident nodes after cold wake: {nodes_after_cold}")

    # 4. Hibernate
    print("[*] Triggering Hibernation...")
    async with aiohttp.ClientSession() as session:
        await session.post(f"{ATTENDANT_URL}/hibernate?key={STYLE_KEY}")
    
    # Wait for status change
    for _ in range(30):
        status = await get_status()
        if status.get("vitals", {}).get("mode") == "HIBERNATING":
            print("[+] Lab is HIBERNATING.")
            break
        await asyncio.sleep(2)
    
    nodes_during_sleep = await get_resident_count()
    print(f"[*] Resident nodes during sleep: {nodes_during_sleep}")
    if nodes_during_sleep != nodes_after_cold:
        print("[!] ERROR: Nodes were reaped during hibernation!")
    else:
        print("[+] SUCCESS: Nodes persisted during sleep.")

    # 5. Warm Wake
    print("[*] Triggering Warm Wake...")
    warm_time = await trigger_query("[ME] Are you warm?")
    print(f"[+] Warm Wake Time: {warm_time:.2f}s")
    
    nodes_after_warm = await get_resident_count()
    print(f"[*] Resident nodes after warm wake: {nodes_after_warm}")
    
    if nodes_after_warm > nodes_after_cold:
        print(f"[!] ERROR: Node layering detected! ({nodes_after_warm} > {nodes_after_cold})")
    elif nodes_after_warm == nodes_after_cold:
        print("[+] SUCCESS: Zero layering confirmed.")
    
    if warm_time < cold_time:
        print(f"[+] Performance Gain: {cold_time - warm_time:.2f}s faster.")
    else:
        print("[!] No performance gain observed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
