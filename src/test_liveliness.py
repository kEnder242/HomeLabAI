import asyncio
import websockets
import json
import sys
import time
import os

LOG_FILE = "/home/jallred/Dev_Lab/HomeLabAI/server.log"

def get_latest_boot_id():
    """Scans for the latest RESTART_MARKER in the logs."""
    if not os.path.exists(LOG_FILE):
        return "No Log"
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            for line in reversed(lines):
                if "[RESTART_MARKER]" in line:
                    return line.strip()
    except: pass
    return "Unknown"

async def liveliness_check():
    uri = "ws://localhost:8765"
    version = "3.4.0"
    
    print(f"--- [LIVELINESS v1.3] Probing {uri} ---")
    current_boot_id = get_latest_boot_id()
    print(f"Initial {current_boot_id}")
    
    start_wait = time.time()
    max_wait = 90
    
    while time.time() - start_wait < max_wait:
        new_boot_id = get_latest_boot_id()
        if new_boot_id != current_boot_id and "Unknown" not in new_boot_id:
            print(f"🚨 DETECTED SERVER RESTART! New {new_boot_id}")
            current_boot_id = new_boot_id

        try:
            async with websockets.connect(uri) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                
                if data.get('type') == 'status' and data.get('state') == 'ready':
                    print(f"✅ Server READY (v{data.get('version')})")
                else:
                    print(f"⌛ Server {data.get('state')}...")
                    await asyncio.sleep(5)
                    continue

                print(f"Tx Handshake (v{version})...")
                await ws.send(json.dumps({"type": "handshake", "version": version}))
                
                msg = await asyncio.wait_for(ws.recv(), timeout=20)
                data = json.loads(msg)
                if data.get('type') == 'cabinet':
                    print(f"✅ Cabinet Sync Success.")
                
                print("Tx Query: 'ping'")
                await ws.send(json.dumps({"type": "text_input", "content": "ping"}))
                
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(msg)
                if data.get('brain'):
                    print(f"✅ Response Rx: [{data.get('brain_source')}]: {data.get('brain')}")
                    print("\n⭐⭐⭐ SYSTEM NOMINAL ⭐⭐⭐")
                    return True
                
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(5)
        except Exception as e:
            print(f"🔍 Probe event: {type(e).__name__}")
            await asyncio.sleep(2)
            
    print("❌ Liveliness check timed out.")
    return False

if __name__ == "__main__":
    success = asyncio.run(liveliness_check())
    sys.exit(0 if success else 1)