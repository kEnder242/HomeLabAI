import asyncio
import websockets
import json
import sys
import time
import os
import subprocess

def get_pid():
    """Returns the PID of the active acme_lab.py process."""
    try:
        return subprocess.check_output(["pgrep", "-f", "acme_lab.py"]).decode().strip()
    except: return None

async def liveliness_check():
    uri = "ws://localhost:8765"
    version = "3.4.0"
    
    print(f"--- [LIVELINESS v1.5] STARTING VERIFICATION ---")
    
    # 1. IMMEDIATE PID CHECK
    pid = get_pid()
    if not pid:
        print("❌ FATAL: No acme_lab.py process found. Aborting.")
        return False
    print(f"✅ Process found (PID: {pid}).")

    start_time = time.time()
    retry_count = 0
    
    while time.time() - start_time < 90:
        retry_count += 1
        print(f"Attempt {retry_count}: Probing {uri}...")
        
        try:
            async with websockets.connect(uri) as ws:
                print("  🤝 Socket Connected. Waiting for Status...")
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                print(f"  📥 RX: {data}")
                
                if data.get('type') == 'status':
                    state = data.get('state', 'unknown').upper()
                    print(f"  ✅ Server is in {state} mode.")
                    
                    if state == 'READY':
                        print("\n⭐⭐⭐ SYSTEM NOMINAL ⭐⭐⭐")
                        return True
                    else:
                        print("  ⌛ Waiting for READY signal...")
                        while True:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            if data.get('state') == 'ready':
                                print("\n⭐⭐⭐ SYSTEM NOMINAL ⭐⭐⭐")
                                return True
                
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {e}")
            # Fast-fail if process disappeared mid-test
            if not get_pid():
                print("  🛑 Server process died during probe.")
                return False
            await asyncio.sleep(5)
            
    print("\n❌ Liveliness check timed out.")
    return False

if __name__ == "__main__":
    success = asyncio.run(liveliness_check())
    sys.exit(0 if success else 1)