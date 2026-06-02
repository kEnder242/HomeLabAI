import asyncio
import json
import os
import fcntl
import time
import logging
import websockets
from unittest.mock import AsyncMock, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, format='[TEST] %(message)s')

VRAM_LOCK_FILE = "/tmp/lab_vram.lock"

async def test_v5_mutex_collision():
    """
    [Task 3.1] Scenario A: The Busy Silicon Handshake (VRAM Mutex).
    Verifies that the Foyer enqueues correctly while VRAM is locked by another process.
    """
    print("\n--- [TASK 3.1] VERIFICATION: V5 VRAM MUTEX COLLISION ---")
    
    # 1. Manually acquire the VRAM Mutex (simulating a heavy background task)
    print("[STEP 1] Acquiring physical VRAM lock...")
    lock_fd = open(VRAM_LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("✅ Lock acquired. Silicon is now 'Busy'.")
        
        # 2. Attempt a query via WebSocket to the Foyer
        # (Assuming Foyer is running on :8765)
        uri = "ws://localhost:8765"
        print(f"[STEP 2] Sending query to Foyer at {uri}...")
        
        try:
            async with websockets.connect(uri) as ws:
                # Send text input
                query = "[ME] What is the status of the RAPL-Sim?"
                await ws.send(json.dumps({"type": "text_input", "content": query}))
                
                # 3. Verify Foyer acknowledgment
                print("[STEP 3] Waiting for Foyer acknowledgment...")
                start_time = time.time()
                success = False
                while time.time() - start_time < 10:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2)
                        data = json.loads(msg)
                        if data.get("type") == "crosstalk" and "[FOYER]" in data.get("brain", ""):
                            print(f"✅ Received Foyer Ack: {data.get('brain')}")
                            success = True
                            break
                    except asyncio.TimeoutError:
                        continue
                
                if not success:
                    print("❌ [FAILURE]: Foyer failed to acknowledge the queued request.")
                    return

        except Exception as e:
            print(f"❌ [FAILURE]: Could not connect to Foyer: {e}")
            print("💡 Ensure 'python3 HomeLabAI/src/acme_lab.py' is running in another terminal.")
            return

    finally:
        print("[STEP 4] Releasing VRAM lock.")
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()

    print("\n✅ Task 3.1 Verification: Mutex Collision scenario passed.")

if __name__ == "__main__":
    asyncio.run(test_v5_mutex_collision())
