import requests
import time
import sys

FOYER_URL = "http://localhost:8765"

def wait_for_state(target_state, timeout=120):
    print(f"[*] Waiting for Lab state to become: {target_state} (Timeout: {timeout}s)...")
    start_t = time.time()
    while time.time() - start_t < timeout:
        try:
            res = requests.get(f"{FOYER_URL}/status", timeout=2)
            if res.status_code == 200:
                state = res.json().get("state")
                if state == target_state:
                    print(f"  ✅ SUCCESS: Lab reached {target_state} state.")
                    return True
        except Exception:
            pass
        time.sleep(2)
        print(".", end="", flush=True)
    
    print(f"\n  ❌ FAILED: Timed out waiting for {target_state}")
    return False

def trigger_action(action):
    print(f"\n[➡] Triggering Action: /{action.upper()}")
    try:
        res = requests.post(f"{FOYER_URL}/{action}", timeout=5)
        if res.status_code == 200:
            print(f"  ✅ Action enqueued: {res.json().get('message')}")
            return True
        else:
            print(f"  ❌ Action rejected: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return False

def run_taxonomy_test():
    print("=== 🧪 REMOTE CONTROL TAXONOMY TEST ===")
    
    # 1. Test WAKE
    if not trigger_action("wake"): sys.exit(1)
    if not wait_for_state("OPERATIONAL"): sys.exit(1)
    
    # Wait for things to settle so we don't trip over fast state transitions
    time.sleep(5)
    
    # 2. Test SLEEP
    if not trigger_action("sleep"): sys.exit(1)
    if not wait_for_state("HIBERNATING", timeout=60): sys.exit(1)
    
    time.sleep(5)
    
    # 3. Test LOCK
    if not trigger_action("lock"): sys.exit(1)
    if not wait_for_state("MAINTENANCE", timeout=30): sys.exit(1)
    
    time.sleep(5)
    
    # 4. Test WAKE from LOCK
    print("\n[➡] Testing WAKE from MAINTENANCE lock...")
    if not trigger_action("wake"): sys.exit(1)
    if not wait_for_state("OPERATIONAL"): sys.exit(1)
    
    time.sleep(5)
    
    # 5. Test SHUTDOWN
    if not trigger_action("shutdown"): sys.exit(1)
    if not wait_for_state("OFFLINE", timeout=60): sys.exit(1)
    
    print("\n🏆 ALL TAXONOMY ENDPOINTS VERIFIED.")

if __name__ == "__main__":
    run_taxonomy_test()
