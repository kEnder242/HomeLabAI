import asyncio
import json
import aiohttp
import os
import time
import sys

# Paths
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
HEARTBEAT_URL = "http://localhost:9999/heartbeat"

async def wait_for_ready(timeout=180):
    """Standalone Forensic Wait: Polls heartbeat and tails log for crashes."""
    print(f"--- [WAIT] Forensic Liveness Audit (Timeout: {timeout}s) ---")
    start_t = time.time()
    
    async with aiohttp.ClientSession() as session:
        while time.time() - start_t < timeout:
            # 1. Check for PHYSICAL READY
            try:
                async with session.get(HEARTBEAT_URL, timeout=2) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get("full_lab_ready"):
                            print(f"\n✅ SUCCESS: Lab reported READY after {int(time.time() - start_t)}s")
                            return True
            except Exception:
                pass

            # 2. Check for FORENSIC CRASH
            if os.path.exists(SERVER_LOG):
                try:
                    with open(SERVER_LOG, "r") as f:
                        lines = f.readlines()[-20:]
                        if any("Traceback" in l or "Error:" in l for l in lines):
                            # Ignore handshake stutters
                            if not any("Larynx is warming" in l for l in lines):
                                print("\n❌ FAILED: Fatal Hub crash detected in logs.")
                                return False
                except Exception:
                    pass

            elapsed = int(time.time() - start_t)
            print(f"  [WAIT] Lab not ready yet... ({elapsed}s)", end="\r")
            await asyncio.sleep(3)
            
    print(f"\n❌ FAILED: Timed out waiting for READY after {timeout}s")
    return False

if __name__ == "__main__":
    success = asyncio.run(wait_for_ready())
    sys.exit(0 if success else 1)
