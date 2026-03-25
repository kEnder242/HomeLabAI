import asyncio
import json
import aiohttp
import time
import subprocess
import sys
import os

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
HEARTBEAT_URL = "http://localhost:9999/heartbeat"
METRICS_URL = "http://localhost:8088/metrics"

async def get_kv_blocks():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(METRICS_URL, timeout=2) as r:
                if r.status == 200:
                    text = await r.text()
                    for line in text.split('\n'):
                        if "vllm:num_block_free_total" in line:
                            # Example: vllm:num_block_free_total{...} 2432.0
                            return float(line.split()[-1])
    except Exception:
        pass
    return 0

async def characterize_ignition():
    print("--- [AUDIT] Characterizing Ignition & Handshake Curve ---")
    
    # 1. Physical Reset
    print("[STEP 1] Nuclear Purge & Service Start...")
    subprocess.run(["sudo", "systemctl", "stop", "lab-attendant.service"])
    subprocess.run(["sudo", "fuser", "-k", "9999/tcp", "8765/tcp", "8088/tcp", "11434/tcp"], stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "pkill", "-9", "-f", "acme_lab|vllm|ollama|EngineCore"], stderr=subprocess.DEVNULL)
    
    start_t = time.time()
    subprocess.run(["sudo", "systemctl", "start", "lab-attendant.service"])
    
    # 2. Wait for Engine Vitals
    print("[STEP 2] Monitoring Physical Larynx (KV Cache Pinning)...")
    larynx_ready_t = 0
    for i in range(60): # 120s
        blocks = await get_kv_blocks()
        if blocks > 0:
            larynx_ready_t = time.time() - start_t
            print(f"\n✅ Larynx Physically Ready: {larynx_ready_t:.2f}s (KV Blocks: {blocks})")
            break
        print(".", end="", flush=True)
        await asyncio.sleep(2)
    else:
        print("\n❌ FAILED: Larynx never reported KV blocks.")
        return

    # 3. Monitor Node Handshakes
    print("[STEP 3] Monitoring Node Handshake Curve...")
    verified_nodes = {}
    nodes_to_track = ["archive", "brain", "shadow", "pinky", "lab", "thinking", "browser"]
    
    for i in range(60): # 120s
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(HEARTBEAT_URL, timeout=2) as r:
                    if r.status == 200:
                        data = await r.json()
                        node_map = data.get("nodes", {})
                        for name, status in node_map.items():
                            if status == "ONLINE" and name not in verified_nodes:
                                verified_nodes[name] = time.time() - start_t
                                print(f"  ✨ Node Verified: {name.upper():<10} at {verified_nodes[name]:.2f}s")
                        
                        if all(n in verified_nodes for n in ["archive", "brain", "shadow", "pinky"]):
                            print("\n✅ All Core Nodes Verified.")
                            break
        except Exception:
            pass
        await asyncio.sleep(2)

    print("\n--- [RESULTS] Handshake Latency Profile ---")
    base = verified_nodes.get("archive", 0)
    for name in nodes_to_track:
        t = verified_nodes.get(name)
        if t:
            delta = t - base if name != "archive" else 0
            print(f"  {name.upper():<10}: {t:6.2f}s (Delta from 1st: +{delta:.2f}s)")

if __name__ == "__main__":
    asyncio.run(characterize_ignition())
