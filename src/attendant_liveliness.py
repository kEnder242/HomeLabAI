import requests
import time
import json
import sys
import os

# Configuration
ATTENDANT_URL = 'http://localhost:9999'
STATUS_URL = f'{ATTENDANT_URL}/status'
START_URL = f'{ATTENDANT_URL}/start'
STOP_URL = f'{ATTENDANT_URL}/stop'
CLEANUP_URL = f'{ATTENDANT_URL}/cleanup'

TIMEOUT_SEC = 240 # 4 minutes total timeout for full lifecycle
POLL_INTERVAL_SEC = 5 # Poll every 5 seconds

def call_attendant_api(method, url, json_payload=None):
    try:
        if method == 'GET':
            response = requests.get(url, timeout=10)
        elif method == 'POST':
            response = requests.post(url, json=json_payload, headers={'Content-Type': 'application/json'}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Monitor] ERROR: Attendant API call failed for {url} ({method}): {e}", file=sys.stderr)
        return {"status": "error", "message": str(e)}

def main():
    start_time = time.time()
    print('--- Starting Lab Attendant Liveliness Monitor (v1.0) ---')
    print(f"Total timeout: {TIMEOUT_SEC}s")

    # --- Phase 1: Initial Status Check ---
    print("\n[Monitor] Phase 1: Checking current Lab status...")
    current_status = call_attendant_api('GET', STATUS_URL)
    
    if current_status.get('status') == 'error':
        print(f"[Monitor] FATAL: Could not connect to Lab Attendant. Is the service running? {current_status.get('message')}")
        sys.exit(1)

    initial_lab_running = current_status.get('lab_server_running', False)
    initial_lab_ready = current_status.get('full_lab_ready', False)
    lab_pid = current_status.get('lab_pid', 'N/A')

    if initial_lab_ready:
        print(f"\n[Monitor] ✅ Lab is already READY (PID: {lab_pid})!")
        sys.exit(0)
    elif initial_lab_running:
        print(f"\n[Monitor] Lab is running (PID: {lab_pid}) but not READY. Attempting to stop for a clean restart.")
        stop_response = call_attendant_api('POST', STOP_URL)
        if stop_response.get('status') == 'error':
            print(f"[Monitor] ERROR: Failed to stop Lab server: {stop_response.get('message')}")
            sys.exit(1)
        # Give a moment for process to terminate
        time.sleep(POLL_INTERVAL_SEC)
    else:
        print("\n[Monitor] Lab is not running. Proceeding with cleanup and start.")

    # --- Phase 2: Cleanup and Start Lab Server ---
    print("\n[Monitor] Phase 2: Performing cleanup...")
    cleanup_response = call_attendant_api('POST', CLEANUP_URL)
    if cleanup_response.get('status') == 'error':
        print(f"[Monitor] ERROR: Failed to cleanup Lab resources: {cleanup_response.get('message')}")
        sys.exit(1)
    print("[Monitor] Cleanup complete.")

    print("\n[Monitor] Phase 2: Starting Lab server...")
    start_payload = {"mode": "SERVICE_UNATTENDED", "disable_ear": True}
    start_response = call_attendant_api('POST', START_URL, json_payload=start_payload)
    if start_response.get('status') == 'error':
        print(f"[Monitor] ERROR: Failed to start Lab server: {start_response.get('message')}")
        sys.exit(1)
    print(f"[Monitor] Lab server launched. PID: {start_response.get('pid')}")
    time.sleep(POLL_INTERVAL_SEC) # Give server a moment to boot

    # --- Phase 3: Poll for Readiness ---
    print("\n[Monitor] Phase 3: Polling for Lab readiness...")
    poll_start_time = time.time()
    while time.time() - start_time < TIMEOUT_SEC:
        current_status = call_attendant_api('GET', STATUS_URL)
        if current_status.get('status') == 'error':
            print(f"[Monitor] ERROR: Could not connect to Lab Attendant during polling. {current_status.get('message')}")
            sys.exit(1)

        running = current_status.get('lab_server_running', False)
        ready = current_status.get('full_lab_ready', False)
        mode = current_status.get('lab_mode', 'UNKNOWN')
        lab_pid = current_status.get('lab_pid', 'N/A')
        last_logs = current_status.get('last_log_lines', [])
        
        print(f'\n[Monitor] Lab Status (Mode: {mode}, PID: {lab_pid}) - Running: {running}, Ready: {ready}')
        if last_logs:
            for line in last_logs:
                print(f'\t[LAB LOG] {line}')
        
        if not running and not ready and (time.time() - poll_start_time > 10): # Grace period for boot
            print('[Monitor] FATAL: Lab server died prematurely during polling. Aborting.')
            print('         Check lab_attendant.log or `sudo journalctl -u lab-attendant.service` for details.')
            sys.exit(1)
        
        if ready:
            print('\n[Monitor] ✅ Lab is fully READY!')
            sys.exit(0)
        
        time.sleep(POLL_INTERVAL_SEC)
    
    print('\n[Monitor] ❌ Timeout: Lab did not become ready within allocated time.')
    sys.exit(1)

if __name__ == "__main__":
    main()
