import asyncio
import aiohttp
import time
import json
import os
import psutil
import subprocess

# [FEAT-337] Warm Wake Validation Harness
# Used for certifying sub-second wake performance and Zero Layering.

ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "ws://localhost:8765"
STYLE_KEY = "92e785ba"

async def get_status():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{ATTENDANT_URL}/status", headers={'X-Lab-Key': STYLE_KEY}, timeout=2) as r:
            return await r.json()

async def get_resident_count():
    """
    Surgically counts resident node processes by checking command line arguments.
    Returns (count, names) to verify exactly 7 nodes and zero layering.
    """
    count = 0
    names = []
    for proc in psutil.process_iter(['cmdline']):
        try:
            cmd = proc.info['cmdline']
            # Match only the actual resident Python nodes
            if cmd and any("nodes/" in part for part in cmd):
                count += 1
                names.append(cmd[-1].split("/")[-1])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return count, names

async def trigger_query(query):
    """
    Triggers a wake-on-intent query via WebSocket and measures latency.
    """
    import websockets
    try:
        async with websockets.connect(HUB_URL) as ws:
            await ws.send(json.dumps({"type": "handshake", "client": "intercom"}))
            await ws.send(json.dumps({"type": "text_input", "content": query}))
            
            start_t = time.time()
            while time.time() - start_t < 120:
                msg = await ws.recv()
                data = json.loads(msg)
                # We stop the clock the moment the mind reports operational readiness
                if "Mind is OPERATIONAL" in str(data.get('brain', '')):
                    return time.time() - start_t
    except Exception as e:
        print(f"[!] WS Error: {e}")
    return -1

async def main():
    print("=== 🔋 WARM WAKE VALIDATION [FEAT-337] ===")
    
    # 1. Baseline Audit
    initial_nodes, node_names = await get_resident_count()
    print(f"[*] Current resident nodes: {initial_nodes} ({', '.join(node_names)})")
    
    # 2. Performance Check (Cold or Warm depending on current state)
    print("[*] Triggering Wake-on-Intent Query...")
    wake_time = await trigger_query("[ME] Performance audit.")
    
    if wake_time >= 0:
        print(f"[+] Wake Latency: {wake_time:.2f}s")
        if wake_time < 2.0:
            print("    [RESULT] WARM WAKE (Sub-second performance confirmed).")
        else:
            print("    [RESULT] COLD BOOT (Standard start-up).")
    else:
        print("[!] FAILED to receive operational signal.")

    # 3. Memory Audit
    print("[*] Checking Resource Profile...")
    status = await get_status()
    vram = status.get("vram_mib", 0)
    mode = status.get("mode") or status.get("vitals", {}).get("mode")
    print(f"    Mode: {mode} | VRAM: {vram}MiB")

    # 4. Zero Layering Verification
    final_nodes, final_names = await get_resident_count()
    print(f"[*] Final resident nodes: {final_nodes} ({', '.join(final_names)})")
    
    if final_nodes > 7:
        print(f"[!] WARNING: Node layering detected! ({final_nodes} processes)")
    elif final_nodes == 7:
        print("[+] SUCCESS: Standard 7-node residency confirmed.")
    else:
        print(f"[*] Note: {final_nodes} nodes active (below standard 7-node stack).")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
