import asyncio
import json
import aiohttp
import time
import subprocess
import sys
import os
import psutil

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
HEARTBEAT_URL = "http://localhost:9999/heartbeat"
METRICS_URL = "http://localhost:8088/metrics"

async def get_vllm_metrics():
    """Extracts KV blocks and throughput from vLLM metrics."""
    metrics = {"blocks": 0, "throughput": 0.0}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(METRICS_URL, timeout=2) as r:
                if r.status == 200:
                    text = await r.text()
                    for line in text.split('\n'):
                        if "vllm:num_block_free_total" in line:
                            metrics["blocks"] = float(line.split()[-1])
                        if "vllm:avg_generation_throughput_tok_s" in line:
                            metrics["throughput"] = float(line.split()[-1])
    except Exception:
        pass
    return metrics

def get_node_pgids(nodes):
    """Maps node names to their Process Group IDs (PGIDs)."""
    pgid_map = {}
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            for node in nodes:
                if node in cmdline and ("python" in cmdline or "node.py" in cmdline):
                    pgid_map[node] = os.getpgid(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pgid_map

async def characterize_ignition():
    print("--- [AUDIT] Characterizing Ignition & Handshake Curve (v2.0) ---")
    
    # 1. Physical Reset
    print("[STEP 1] Nuclear Purge & Service Start...")
    subprocess.run(["sudo", "systemctl", "stop", "lab-attendant.service"])
    subprocess.run(["sudo", "fuser", "-k", "9999/tcp", "8765/tcp", "8088/tcp", "11434/tcp"], stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "pkill", "-9", "-f", "acme_lab|vllm|ollama|EngineCore"], stderr=subprocess.DEVNULL)
    
    start_t = time.time()
    subprocess.run(["sudo", "systemctl", "start", "lab-attendant.service"])
    
    # 2. Wait for Engine Vitals
    print("[STEP 2] Monitoring Physical Larynx (KV Cache & Throughput)...")
    larynx_ready_t = 0
    for i in range(90): # 180s
        metrics = await get_vllm_metrics()
        if metrics["blocks"] > 0:
            larynx_ready_t = time.time() - start_t
            print(f"\n✅ Larynx Physically Ready: {larynx_ready_t:.2f}s (KV Blocks: {metrics['blocks']}, T-Put: {metrics['throughput']:.1f} tok/s)")
            break
        print(".", end="", flush=True)
        await asyncio.sleep(2)
    else:
        # Check if the lab is at least online even if metrics are slow
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:9999/heartbeat", timeout=2) as r:
                    if r.status == 200:
                        print("\n⚠️ WARNING: Lab is ONLINE but KV blocks are not yet reporting in metrics.")
                        larynx_ready_t = time.time() - start_t
                    else:
                        print("\n❌ FAILED: Larynx never reported KV blocks.")
                        return
        except Exception:
            print("\n❌ FAILED: Larynx never reported KV blocks and heartbeat is unreachable.")
            return

    # 3. Monitor Node Handshakes
    print("[STEP 3] Monitoring Node Handshake Curve & PGID Isolation...")
    verified_nodes = {}
    nodes_to_track = ["archive", "brain", "shadow", "pinky", "lab", "thinking", "browser"]
    
    for i in range(90): # 180s total
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(HEARTBEAT_URL, timeout=2) as r:
                    if r.status == 200:
                        data = await r.json()
                        node_map = data.get("vitals", {}).get("nodes", {})
                        for name, status in node_map.items():
                            if status == "ONLINE" and name not in verified_nodes:
                                verified_nodes[name] = time.time() - start_t
                                print(f"  ✨ Node Verified: {name.upper():<10} at {verified_nodes[name]:.2f}s")
                        
                        if all(n in verified_nodes for n in ["archive", "brain", "shadow", "pinky"]):
                            print("\n✅ Core Nodes Verified.")
                            break
        except Exception:
            pass
        await asyncio.sleep(2)

    # 4. Forensic PGID Snapshot
    print("\n[STEP 4] Forensic PGID Audit...")
    pgids = get_node_pgids(nodes_to_track)
    for node, pgid in pgids.items():
        print(f"  {node.upper():<10}: PGID {pgid}")

    print("\n--- [RESULTS] Handshake Latency Profile ---")
    base = verified_nodes.get("archive", 0)
    for name in nodes_to_track:
        t = verified_nodes.get(name)
        if t:
            delta = t - base if name != "archive" else 0
            print(f"  {name.upper():<10}: {t:6.2f}s (Delta from 1st: +{delta:.2f}s)")

if __name__ == "__main__":
    asyncio.run(characterize_ignition())
