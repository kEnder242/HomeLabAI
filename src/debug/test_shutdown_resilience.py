import asyncio
import json
import websockets
import time
import subprocess
import os
import signal

# Configuration
HUB_URL = "ws://localhost:8765"

async def test_shutdown_resilience():
    """Verifies that the Hub can shut down even if a resident is slow."""
    print("\n--- 🏁 STARTING SHUTDOWN RESILIENCE TEST ---")
    
    # 1. Start a temporary lab server in DEBUG mode
    print("[TEST] Starting background Hub...")
    proc = subprocess.Popen(
        [os.path.expanduser("~/Dev_Lab/HomeLabAI/.venv/bin/python3"), 
         "HomeLabAI/src/acme_lab.py", "--mode", "DEBUG_BRAIN", "--disable-ear"],
        env={**os.environ, "PYTHONPATH": os.path.abspath("HomeLabAI/src")},
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    
    # Wait for ready
    time.sleep(15)
    
    try:
        async with websockets.connect(HUB_URL) as ws:
            print("[TEST] Connected. Triggering shutdown...")
            await ws.send(json.dumps({"type": "text_input", "content": "Please close the lab."}))
            
            start_t = time.time()
            success = False
            while time.time() - start_t < 30:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    print(f"[RECV] {data.get('brain_source')}: {data.get('brain')}")
                    if data.get('brain') and "Closing Lab" in data.get('brain'):
                        success = True
                        break
                except Exception:
                    continue
            
            if success:
                print("[PASS] Shutdown signal received.")
            else:
                print("[FAIL] Shutdown signal NOT received.")
                return False

        # Wait for process to exit
        print("[TEST] Waiting for Hub process to terminate...")
        try:
            proc.wait(timeout=20)
            print("[PASS] Hub process terminated cleanly.")
            return True
        except subprocess.TimeoutExpired:
            print("[FAIL] Hub process HUNG during shutdown.")
            os.kill(proc.pid, signal.SIGKILL)
            return False

    except Exception as e:
        print(f"[ERROR] Test failed with: {e}")
        os.kill(proc.pid, signal.SIGKILL)
        return False

if __name__ == "__main__":
    if asyncio.run(test_shutdown_resilience()):
        print("--- ✅ SHUTDOWN RESILIENCE VERIFIED ---")
        exit(0)
    else:
        print("--- ❌ SHUTDOWN RESILIENCE FAILED ---")
        exit(1)
