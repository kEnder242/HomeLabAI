import asyncio
import json
import websockets
import time
import requests

# [FEAT-342] The Rude Gauntlet
# Certifies transition stability by sending concurrent queries to a HIBERNATING lab.
# This avoids the "Warm Path" trap and forces the Wake-on-Intent logic.

HUB_URL = "ws://localhost:8765"

# --- [FEAT-342] Browser-status HTTP poller + thermal guardrail (additive) ---

def _read_raw_temp():
    """Read the first readable sysfs thermal sensor, raw millidegrees C."""
    for zone in ("thermal_zone2", "thermal_zone3", "thermal_zone0"):
        path = f"/sys/class/thermal/{zone}/temp"
        try:
            with open(path, "r") as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            continue
    return None

def read_cpu_temp_c():
    """CPU temp in degC (sysfs is millidegrees: 27800 => 27.8 C), or None."""
    raw = _read_raw_temp()
    return raw / 1000.0 if raw is not None else None

async def http_browser_poller(stop_event):
    """Simulate intercom.html browser load: poll GET /status every 1.0s."""
    hits = 0
    failed_once = False
    while not stop_event.is_set():
        try:
            resp = await asyncio.to_thread(requests.get, "http://localhost:8765/status", timeout=5)
            if resp.status_code == 200:
                hits += 1
                try:
                    keys = list(resp.json().keys())
                except Exception:
                    keys = []
                trimmed = [k for k in keys if k in ("session_token", "state", "status")] or keys[:3]
                print(f"[HTTP] poll OK: {resp.status_code} keys={trimmed}")
            elif not failed_once:
                print(f"[HTTP] poll failed: HTTP {resp.status_code}")
                failed_once = True
        except Exception as e:
            if not failed_once:
                print(f"[HTTP] poll failed: {e}")
                failed_once = True
        await asyncio.sleep(1.0)
    return hits

def get_session_token():
    resp = requests.get("http://localhost:8765/status", timeout=5)
    return resp.json().get("session_token", "")

async def trigger_query(client_id, query):
    try:
        token = get_session_token()
        async with websockets.connect(HUB_URL) as ws:
            # Read server pushed init message
            init_msg = await ws.recv()
            
            # Send handshake
            await ws.send(json.dumps({"type": "handshake", "lab_key": token}))
            ack_msg = await ws.recv()
            
            # Immediate prompt via V5 chat payload format
            await ws.send(json.dumps({"type": "chat", "message": query}))
            
            start_t = time.time()
            while time.time() - start_t < 180: # 3-minute window for cold wake
                msg = await ws.recv()
                data = json.loads(msg)
                
                # Check for V5 crosstalk/thought/speech payload or legacy brain field
                speaker = data.get('speaker') or data.get('source') or data.get('brain_source') or ''
                text = str(data.get('content') or data.get('text') or data.get('brain') or '')
                
                if speaker in ['Pinky', 'Brain', 'Shadow', 'Lab', 'Deep Thought'] or data.get('type') in ['crosstalk', 'thought', 'speech', 'chat']:
                    if any(x in text.upper() for x in ['ROGER', 'PINKY', 'ACME', 'POIT', 'NARF', 'ZORT', 'CHECK', 'TEST']):
                        print(f"    [Client {client_id}] SUCCESS ({speaker}): {text[:40]}...")
                        return True
                    if '[GIBBERISH]' in text:
                        print(f"    [Client {client_id}] FAIL: Physical corruption detected!")
                        return False
    except Exception as e:
        print(f"    [Client {client_id}] ERROR: {e}")
    return False

async def run_cycle(cycle):
    print(f"\n[*] Starting Rude Cycle {cycle}/5...")
    
    # 1. Force Hibernate (H2 - Lean Sleep)
    print(f"    [Action] Entering Lean Sleep (H2)...")
    requests.post("http://localhost:8765/status_update", json={"state": "HIBERNATING"}, timeout=5)
    time.sleep(10) # Settle
    
    # 2. Fire Rude Storm (5 concurrent queries to sleeping lab)
    print(f"    [Action] Launching 5-node 'Wake-on-Intent' storm...")
    
    # Thermal baseline (raw millidegrees + degC) right before the storm
    raw_start = _read_raw_temp()
    start_temp = read_cpu_temp_c()
    if start_temp is not None:
        print(f"[Thermal] raw={raw_start} => {start_temp:.1f} C")
    else:
        print("[Thermal] WARN: no readable sysfs temp sensor; guardrail skipped")
    
    # Background HTTP poller (browser-status path) during the storm
    stop_event = asyncio.Event()
    poller_task = asyncio.create_task(http_browser_poller(stop_event))
    
    tasks = []
    for i in range(5):
        tasks.append(trigger_query(i, f"[ME] Rude Check {cycle}.{i}. Respond with ROGER."))
    
    try:
        results = await asyncio.gather(*tasks)
    finally:
        # Clean-cancellation guarantee: stop, cancel, swallow CancelledError
        stop_event.set()
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass
    
    wins = sum(1 for r in results if r)
    print(f"    [Result] Cycle {cycle} Wins: {wins}/5")
    
    # Thermal check after the storm: max of start/end samples, ceiling 78.0 C
    raw_end = _read_raw_temp()
    end_temp = read_cpu_temp_c()
    if end_temp is not None:
        print(f"[Thermal] raw={raw_end} => {end_temp:.1f} C")
    samples = [t for t in (start_temp, end_temp) if t is not None]
    if samples:
        max_temp = max(samples)
        try:
            assert max_temp < 78.0, f"THERMAL THRESHOLD EXCEEDED: {max_temp} degC"
        except AssertionError:
            print(f"[Thermal] GUARDRAIL FAIL: max temp {max_temp:.1f} C >= 78.0 C")
            return False
        print(f"[Thermal] max temp: {max_temp:.1f} C (OK)")
    else:
        print("[Thermal] WARN: no readable sysfs temp sensor; guardrail skipped")
    
    return wins == 5

async def main():
    print("🔥 INITIATING THE RUDE GAUNTLET (Transition Stability Certification)")
    print("[*] Strategy: Send concurrent queries to HIBERNATING lab (No Warm Path).")
    
    total_wins = 0
    for i in range(5):
        if await run_cycle(i + 1):
            total_wins += 1
            print(f"--- Cycle {i+1} Passed (Logical & Physical Integrity Verified) ---")
        else:
            print(f"\n❌ RUDE GAUNTLET FAILED at Cycle {i+1}")
            break
        
    print(f"\n🏆 GAUNTLET COMPLETE. Rude H2 Wins: {total_wins}/5")

if __name__ == "__main__":
    asyncio.run(main())