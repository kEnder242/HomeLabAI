import asyncio
import json
import requests
import time
import hashlib
import subprocess

ATTENDANT_URL = "http://127.0.0.1:9999"
HUB_URL = "http://localhost:8765"
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def test_persistence():
    print("💎 INITIATING LOBBY PERSISTENCE CERTIFICATION")
    key = get_key()
    
    # 1. Trigger H2 Recovery Scythe (The New Fix)
    print("[*] Triggering H2 Silicon Scythe with RECOVER=TRUE...")
    try:
        url = f"{ATTENDANT_URL}/hibernate?level=2&recover=true&key={key}&reason=TEST_CERT"
        r = requests.post(url, timeout=10)
        print(f"    [+] Attendant accepted: {r.json()}")
    except Exception as e:
        print(f"    [-] Trigger failed: {e}")
        return

    # 2. Immediate Physical Port Audit
    print("[*] Performing Physical Port Audit (Goal: 100% Uptime)...")
    try:
        r = requests.get(f"{HUB_URL}/heartbeat", timeout=2)
        if r.status_code == 200:
            print("    [🏆] SUCCESS: Lobby (8765) stayed UP during scythe.")
        else:
            print(f"    [❌] FAILURE: Lobby returned {r.status_code}.")
            return
    except Exception as e:
        print(f"    [❌] FAILURE: Lobby DISCONNECTED: {e}")
        return

    # 3. Monitor for Ignition Recovery
    print("[*] Monitoring for Autonomous Re-ignition...")
    start_t = time.time()
    while time.time() - start_t < 120:
        try:
            r = requests.get(f"{HUB_URL}/heartbeat", timeout=2)
            data = r.json()
            if data.get('state') == 'operational' or data.get('operational'):
                print(f"    [🏆] CERTIFIED: Lab re-ignited in {int(time.time() - start_t)}s.")
                return True
            print(f"    ... State: {data.get('state')} (Waiting)")
        except Exception:
            pass
        time.sleep(10)
    
    print("    [!] TIMEOUT: Hub stayed in lobby mode.")
    return False

if __name__ == '__main__':
    asyncio.run(test_persistence())
