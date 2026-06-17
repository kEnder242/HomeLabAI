import asyncio
import json
import requests
import time
import hashlib
import subprocess

# [TEST-54] Lobby Robustness Reproduction
# Proves that a Silicon Scythe (H3) kills the Lobby/Foyer and fails to recover it.

ATTENDANT_URL = "http://127.0.0.1:8765"
HUB_URL = "http://localhost:8765"
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

async def reproduce():
    print("🔥 INITIATING LOBBY ROBUSTNESS TEST")
    key = get_key()
    
    # 1. Ensure Hub is UP
    print("[*] Checking Hub status...")
    try:
        r = requests.get(f"{HUB_URL}/heartbeat", timeout=2)
        if r.status_code == 200:
            print("    [+] Hub is ONLINE.")
        else:
            print(f"    [-] Hub returned {r.status_code}. Please start the lab first.")
            return
    except Exception as e:
        print(f"    [-] Hub is OFFLINE: {e}")
        return

    # 2. Trigger Mock Silicon Scythe (H3)
    print("[*] Triggering Mock Silicon Scythe (H3)...")
    try:
        r = requests.post(f"{ATTENDANT_URL}/hibernate?level=3&key={key}&reason=MOCK_SCYTHE", timeout=5)
        print(f"    [+] Attendant response: {r.json()}")
    except Exception as e:
        print(f"    [-] Trigger failed: {e}")
        return

    # 3. Monitor Lobby (Port 8765)
    print("[*] Monitoring Lobby for death...")
    time.sleep(10) # Wait for shutdown to process
    
    dead = False
    try:
        requests.get(f"{HUB_URL}/heartbeat", timeout=2)
    except Exception:
        print("    [!] CONFIRMED: Lobby is DEAD (Port 8765 Refused).")
        dead = True

    if not dead:
        print("    [-] Lobby survived? (Unexpected for H3).")
        return

    # 4. Check for Recovery
    print("[*] Waiting 120s for Autonomous Recovery...")
    start_t = time.time()
    recovered = False
    while time.time() - start_t < 120:
        try:
            r = requests.get(f"{HUB_URL}/heartbeat", timeout=2)
            if r.status_code == 200:
                print(f"    [🏆] RECOVERED: Lobby is back online after {int(time.time() - start_t)}s.")
                recovered = True
                break
        except Exception:
            pass
        time.sleep(10)

    if not recovered:
        print("    [❌] FAILURE: Lobby stayed dead. System is in a 'Zombie State'.")
        # Final physical check
        res = subprocess.run(["sudo", "netstat", "-tulpn"], capture_output=True, text=True)
        if "8765" not in res.stdout:
            print("    [!] Physical Confirmation: Port 8765 is NOT listening.")
        
if __name__ == "__main__":
    asyncio.run(reproduce())
