import asyncio
import websockets
import json
import sys
import time
import subprocess

def get_pid():
    """Returns the PID of the active acme_lab process, handling renamed titles."""
    try:
        # Search for 'acme_lab' substring in the full command line
        return subprocess.check_output(["pgrep", "-f", "acme_lab"]).decode().strip().split('\n')[0]
    except: return None

async def liveliness_check():
    uri = "ws://localhost:8765"
    version = "3.4.0"

    print("--- [LIVELINESS v1.5] STARTING VERIFICATION ---")

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
                print("  🤝 Socket Connected. Sending Handshake...")
                await ws.send(json.dumps({"type": "handshake", "version": version}))
                
                # Wait for Status Response
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(msg)
                    print(f"  📥 RX: {data.get('type')} from {data.get('brain_source')}")

                    if data.get('type') == 'status':
                        state = str(data.get('state', 'unknown')).upper()
                        print(f"  ✅ Server state: {state}")
                        if state in ['READY', 'OPERATIONAL']:
                            print("\n⭐⭐⭐ SYSTEM NOMINAL ⭐⭐⭐")
                            return True
                    
                    # If we get a chat message from System, it's also a sign of life
                    if data.get('type') == 'chat' and data.get('brain_source') == 'System':
                         print("  ✅ System is talking. Assuming operational.")
                         return True
                         
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {e}")
            await asyncio.sleep(2) # Prevent tight loop

    print("\n❌ Liveliness check timed out.")
    return False

if __name__ == "__main__":
    success = asyncio.run(liveliness_check())
    sys.exit(0 if success else 1)
