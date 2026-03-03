import asyncio
import websockets
import json
import time
import requests
import sys
import os
from trace_monitor import TraceMonitor

# Paths
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
ATTENDANT_LOG = os.path.join(LAB_DIR, "attendant.log")

async def test_bounce():
    uri = "ws://localhost:8765"
    attendant_url = "http://localhost:9999/heartbeat"
    
    # [FEAT-151] Initialize Trace Monitor
    monitor = TraceMonitor([SERVER_LOG, ATTENDANT_LOG])
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as ws:
            # 1. Wait for status
            status_raw = await ws.recv()
            status = json.loads(status_raw)
            print(f"[STATUS] State: {status.get('state')} | Boot Hash: {status.get('boot_hash')}")
            
            # Reset monitor marks to just before the trigger
            monitor.refresh_marks()
            
            # 2. Send EXPLICIT tool trigger (Avoid conversational drift)
            payload = {
                "type": "text_input", 
                "content": json.dumps({"tool": "close_lab", "parameters": {}})
            }
            print(f"[TRIGGER] Sending explicit tool call...")
            await ws.send(json.dumps(payload))
            
            # 3. Wait for shutdown broadcast
            try:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                msg = json.loads(msg_raw)
                if msg.get("type") == "shutdown":
                    print("✅ Hub broadcasted shutdown signal.")
            except Exception:
                pass # Connection likely dropped already
            
    except Exception as e:
        print(f"Connection closed: {e}")

    # 4. Monitor Attendant for the "Bounce" (READY -> !READY -> READY)
    print("\n--- MONITORING BOUNCE (Trace Delta Active) ---")
    bounce_detected = False
    start_time = time.time()
    
    for i in range(60):
        # Capture and print any new log lines since the last cycle
        monitor.print_delta()
        
        try:
            r = requests.get(attendant_url, timeout=1).json()
            ready = r.get("full_lab_ready")
            mode = r.get("lab_mode")
            err = r.get("last_error")
            
            if ready == False and not bounce_detected:
                bounce_detected = True
                print(f"⚡ BOUNCE IN PROGRESS: Lab process terminated (T+{int(time.time()-start_time)}s)")
            
            if bounce_detected and ready == True:
                print(f"\n✅ BOUNCE SUCCESSFUL: Lab is back online (T+{int(time.time()-start_time)}s)")
                # Final trace capture
                monitor.print_delta()
                return True
                
            if err and "Process died" in err and not bounce_detected:
                print(f"⚠️  Attendant reports process death: {err}")
                bounce_detected = True

        except Exception as e:
            # Attendant might be briefly unreachable during service restarts
            pass
            
        await asyncio.sleep(2)
            
    print("❌ Hub failed to complete bounce within timeout.")
    monitor.print_delta()
    return False

if __name__ == "__main__":
    if asyncio.run(test_bounce()):
        print("\n[FEAT-149] GOODNIGHT BOUNCE: PASSED")
        sys.exit(0)
    else:
        print("\n[FEAT-149] GOODNIGHT BOUNCE: FAILED")
        sys.exit(1)
