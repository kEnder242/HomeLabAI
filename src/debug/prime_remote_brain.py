#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sovereign Prime & Probe (B+A)
[FEAT-212] Direct REST Priming + Hub WebSocket Probing.

This script proves model residency on the 4090 and audits the Hub's triage turns.
"""

import asyncio
import json
import time
import requests
import websockets

# --- Configuration ---
SOVEREIGN_IP = "192.168.1.26"
OLLAMA_PORT = 11434
HUB_URI = "ws://localhost:8765"
MODEL = "llama3.1:8b" # Target Sovereign model

async def prime_4090():
    print(f"--- [PHASE 1] Priming Sovereign (Direct REST) ---")
    url = f"http://{SOVEREIGN_IP}:{OLLAMA_PORT}/api/generate"
    payload = {
        "model": MODEL,
        "prompt": "Respond with 'Sovereign Online'.",
        "stream": False
    }
    
    start = time.time()
    try:
        response = requests.post(url, json=payload, timeout=120)
        duration = time.time() - start
        if response.status_code == 200:
            print(f"✅ Prime Successful in {duration:.2f}s: {response.json().get('response', '').strip()}")
            return True
        else:
            print(f"❌ Prime Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Prime Error: {e}")
    return False

async def probe_hub():
    print(f"\n--- [PHASE 2] Probing Hub (WebSocket Trace) ---")
    query = "[ARCHIVE_EXTRACT]: Find the specific paragraphs in the raw file (notes_2024_PIAV.txt) that correspond to this summary: 'Strategic Sovereignty'. Output ONLY the raw paragraphs."
    
    async with websockets.connect(HUB_URI) as ws:
        # Wait for greeting
        greeting = await ws.recv()
        print(f"  [Handshake] {greeting}")
        
        print(f"  [Query] Sending extraction prompt...")
        await ws.send(json.dumps({"type": "text_input", "content": query}))
        
        start = time.time()
        while True:
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=120)
                data = json.loads(resp)
                source = data.get("brain_source", "Unknown")
                content = data.get("brain", "")
                
                elapsed = time.time() - start
                print(f"  [{elapsed:6.2f}s] {source:15}: {content[:100]}...")
                
                if "Result" in source or "Failover" in source:
                    print(f"\n✅ Probe Complete. Final Turn received from {source}.")
                    break
            except asyncio.TimeoutError:
                print(f"❌ Probe Timeout after 120s.")
                break

if __name__ == "__main__":
    import sys
    skip_prime = "--no-prime" in sys.argv
    
    should_probe = False
    if skip_prime:
        print("--- Skipping Prime Phase ---")
        should_probe = True
    else:
        if asyncio.run(prime_4090()):
            should_probe = True
        else:
            print("Aborting Probe due to Prime failure.")
            
    if should_probe:
        asyncio.run(probe_hub())
