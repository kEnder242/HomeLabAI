#!/usr/bin/env python3
"""
[FEAT-149] Resident Liveness & 30-Minute Attendant Supervisor
[FEAT-537] Internal State-Aware Bytecode & Resilience Engine

Supervisory Engine Roles:
1. State & Lockfile Awareness: Respects status.json ('SLEEP', 'SHUTDOWN', 'MAINTENANCE') and maintenance locks.
2. 30-Minute Cadence: Polling loop to ensure the lab is never offline or hung unexpectedly.
3. 2-Tier Recovery Hierarchy:
   - Resident Node changes -> Soft Reload (POST /reload_residents, <100ms, VRAM preserved)
   - Deep Risk changes / Socket Hung -> Hard Reset (POST /hard_reset / Process resurrection)
"""

import requests
import time
import sys
import hashlib
import os
import json
import subprocess
import argparse
import logging
from typing import Tuple, List

# Configuration & Paths
BASE_DIR = "/home/jallred/Dev_Lab"
PORTFOLIO_DIR = os.path.join(BASE_DIR, "Portfolio_Dev")
LAB_DIR = os.path.join(BASE_DIR, "HomeLabAI")
STATUS_JSON_PATH = os.path.join(PORTFOLIO_DIR, "field_notes/data/status.json")
STYLE_CSS_PATH = os.path.join(PORTFOLIO_DIR, "field_notes/style.css")
MAINTENANCE_LOCK_PATHS = [
    os.path.join(LAB_DIR, "run/maintenance.lock"),
    os.path.join(PORTFOLIO_DIR, "field_notes/data/maintenance.lock")
]

ATTENDANT_URL = 'http://localhost:8765'
STATUS_URL = f'{ATTENDANT_URL}/status?timeout=5'
START_URL = f'{ATTENDANT_URL}/start'
STOP_URL = f'{ATTENDANT_URL}/stop'
RELOAD_URL = f'{ATTENDANT_URL}/reload_residents'
CLEANUP_URL = f'{ATTENDANT_URL}/hard_reset'

TIMEOUT_SEC = 240
POLL_INTERVAL_SEC = 5
DEFAULT_SUPERVISORY_INTERVAL_SEC = 1800 # 30 minutes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ATTENDANT-SUPERVISOR] %(message)s"
)
logger = logging.getLogger("attendant_supervisor")

def get_lab_key() -> str:
    """Calculates dynamic Lab Key from style.css MD5."""
    try:
        if os.path.exists(STYLE_CSS_PATH):
            with open(STYLE_CSS_PATH, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()[:8]
    except Exception as e:
        logger.warning(f"Could not calculate Lab Key at {STYLE_CSS_PATH}: {e}")
    return "ERROR_KEY"

def call_attendant_api(method: str, url: str, json_payload=None, timeout: int = 10) -> dict:
    key = get_lab_key()
    headers = {
        'Content-Type': 'application/json',
        'X-Lab-Key': key
    }
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, timeout=timeout)
        elif method.upper() == 'POST':
            response = requests.post(url, json=json_payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}

def check_lab_state_and_locks() -> Tuple[bool, str]:
    """
    Checks on-disk state.
    Returns (is_active_target, state_description).
    If state is SLEEP, SHUTDOWN, or MAINTENANCE lock exists, returns False.
    """
    for lock_path in MAINTENANCE_LOCK_PATHS:
        if os.path.exists(lock_path):
            return False, f"MAINTENANCE_LOCK ({os.path.basename(lock_path)})"
    
    if os.path.exists(STATUS_JSON_PATH):
        try:
            with open(STATUS_JSON_PATH, "r") as f:
                data = json.load(f)
            state = data.get("state", "UNKNOWN").upper()
            if state in ["SLEEP", "SHUTDOWN", "HIBERNATING", "MAINTENANCE"]:
                return False, f"INTENTIONAL_{state}"
            elif state == "OPERATIONAL":
                return True, "OPERATIONAL"
        except Exception as e:
            logger.warning(f"Error reading {STATUS_JSON_PATH}: {e}")
            
    return True, "DEFAULT_OPERATIONAL"

def check_modified_files(boot_ts: float) -> Tuple[List[str], List[str]]:
    """
    Categorizes files modified in HomeLabAI/src since boot_timestamp.
    Returns (deep_changed_files, resident_changed_files).
    """
    deep_changed = []
    resident_changed = []
    
    src_dir = os.path.join(LAB_DIR, "src")
    if not os.path.exists(src_dir):
        return deep_changed, resident_changed

    deep_prefixes = [
        os.path.join(src_dir, "v5/foyer"),
        os.path.join(src_dir, "lab_attendant.py"),
    ]
    
    resident_prefixes = [
        os.path.join(src_dir, "logic"),
        os.path.join(src_dir, "nodes"),
        os.path.join(src_dir, "data"),
        os.path.join(src_dir, "equipment"),
        os.path.join(src_dir, "curator"),
        os.path.join(src_dir, "compiler"),
    ]

    for root, dirs, files in os.walk(src_dir):
        if "__pycache__" in root or ".git" in root:
            continue
        for file in files:
            if not file.endswith((".py", ".json", ".yaml", ".yml", ".sh")):
                continue
            fpath = os.path.join(root, file)
            try:
                mtime = os.path.getmtime(fpath)
                if mtime > boot_ts:
                    rel_path = os.path.relpath(fpath, LAB_DIR)
                    is_deep = any(fpath.startswith(dp) for dp in deep_prefixes)
                    if is_deep:
                        deep_changed.append(rel_path)
                    else:
                        is_resident = any(fpath.startswith(rp) for rp in resident_prefixes)
                        if is_resident:
                            resident_changed.append(rel_path)
            except OSError:
                continue
                
    return deep_changed, resident_changed

def restart_foyer_process() -> bool:
    """Terminates and restarts the Foyer daemon with new bytecode."""
    logger.info("[SUPERVISOR] Executing clean OS process bounce for Foyer...")
    try:
        subprocess.run(["pkill", "-9", "acme_foyer_v5"], capture_output=True)
        subprocess.run(["pkill", "-9", "acme_ignition_"], capture_output=True)
        time.sleep(2)
        
        py_bin = os.path.join(LAB_DIR, ".venv/bin/python3")
        acme_lab_path = os.path.join(LAB_DIR, "src/acme_lab.py")
        cmd = [py_bin, acme_lab_path, "--mode", "SERVICE_UNATTENDED", "--disable-ear"]
        
        log_out = open(os.path.join(BASE_DIR, "attendant.log"), "a")
        proc = subprocess.Popen(cmd, stdout=log_out, stderr=log_out, start_new_session=True, cwd=LAB_DIR)
        logger.info(f"[SUPERVISOR] Launched Foyer process (PID: {proc.pid})")
        time.sleep(3)
        return True
    except Exception as e:
        logger.error(f"[SUPERVISOR] Failed to restart Foyer process: {e}")
        return False

PENDING_RESET_PATH = os.path.join(PORTFOLIO_DIR, "field_notes/data/pending_reset.json")

def load_pending_reset() -> dict:
    if os.path.exists(PENDING_RESET_PATH):
        try:
            with open(PENDING_RESET_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pending_action": "NONE", "action_level": 0, "timer_expiry_ts": 0}

def clear_pending_reset():
    state_data = {
        "pending_action": "NONE",
        "action_level": 0,
        "timer_expiry_ts": 0,
        "triggered_at_ts": int(time.time()),
        "last_commit": "cleared",
        "reasons": []
    }
    try:
        temp_path = PENDING_RESET_PATH + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(state_data, f, indent=2)
        os.replace(temp_path, PENDING_RESET_PATH)
    except Exception as e:
        logger.warning(f"Failed to clear pending_reset.json: {e}")

def run_supervisory_tick(dry_run: bool = False) -> str:
    """
    Executes a single supervisory check with pending rolling reset support.
    """
    logger.info("=== Starting Supervisory Health & Liveness Tick ===")
    
    # Gate 1: Check on-disk state & maintenance locks
    is_active, state_reason = check_lab_state_and_locks()
    if not is_active:
        logger.info(f"Lab is in intentional dormant state ({state_reason}). Skipping supervisory reloads/resets.")
        return f"SKIP_{state_reason}"

    # Gate 2: Check Git 30-Minute Rolling Reset Queue
    pending = load_pending_reset()
    pending_action = pending.get("pending_action", "NONE")
    expiry_ts = pending.get("timer_expiry_ts", 0)
    now = time.time()

    if pending_action != "NONE" and expiry_ts > 0:
        if now >= expiry_ts:
            logger.info(f"⏱️ 30-Minute quiet window expired for pending action: {pending_action} (Commit: {pending.get('last_commit')})")
            if dry_run:
                logger.info(f"[DRY-RUN] Would execute expired pending action: {pending_action}")
                return f"DRY_RUN_EXPIRED_{pending_action}"
            
            if pending_action == "DEEP_RESET":
                logger.info("Executing queued DEEP_RESET via OS process bounce...")
                restart_foyer_process()
                clear_pending_reset()
                return "EXECUTED_EXPIRED_DEEP_RESET"
            elif pending_action == "SOFT_RELOAD":
                logger.info("Executing queued SOFT_RELOAD via reload_residents...")
                reload_resp = call_attendant_api('POST', RELOAD_URL)
                logger.info(f"Reload response: {reload_resp}")
                clear_pending_reset()
                return "EXECUTED_EXPIRED_SOFT_RELOAD"
        else:
            remaining_sec = int(expiry_ts - now)
            logger.info(f"⏳ Active rolling quiet window: Pending {pending_action} ({remaining_sec}s / {remaining_sec/60:.1f}m remaining). Holding.")
            return f"PENDING_{pending_action}_HOLDING ({remaining_sec}s left)"
        
    # Gate 3: Probe Foyer HTTP Status endpoint
    status_resp = call_attendant_api('GET', STATUS_URL, timeout=8)
    
    if status_resp.get("status") == "error":
        logger.warning(f"First probe failed: {status_resp.get('message')}. Retrying after 3s...")
        time.sleep(3)
        status_resp = call_attendant_api('GET', STATUS_URL, timeout=8)
        
    if status_resp.get("status") == "error":
        logger.critical(f"Foyer port 8765 is UNRESPONSIVE: {status_resp.get('message')}")
        if dry_run:
            logger.info("[DRY-RUN] Would trigger hard_reset for unresponsive Foyer port.")
            return "DRY_RUN_HARD_RESET"
        else:
            logger.info("Executing process resurrection...")
            restart_foyer_process()
            clear_pending_reset()
            return "RECOVERED_PORT_HANG"
            
    # Lab is running & responsive
    foyer_state = status_resp.get("state", "OPERATIONAL")
    boot_ts = status_resp.get("boot_timestamp") or status_resp.get("state_changed_at", 0)
    boot_commit = status_resp.get("boot_commit", "unknown")
    
    logger.info(f"Foyer is {foyer_state} (Boot Commit: {boot_commit}, Boot Timestamp: {boot_ts})")
    
    # Gate 4: Evaluate uncommitted/stale modified files on disk
    if boot_ts > 0:
        deep_files, resident_files = check_modified_files(boot_ts)
        
        if deep_files:
            logger.warning(f"Deep architectural files changed on disk ({len(deep_files)} files): {deep_files[:3]}")
            if dry_run:
                logger.info("[DRY-RUN] Would trigger Hard Reset for deep architectural changes.")
                return "DRY_RUN_DEEP_HARD_RESET"
            else:
                logger.info("Triggering clean OS process restart for deep file changes...")
                restart_foyer_process()
                clear_pending_reset()
                return "EXECUTED_DEEP_HARD_RESET"
                
        elif resident_files:
            logger.info(f"Resident node files changed on disk ({len(resident_files)} files): {resident_files[:3]}")
            if dry_run:
                logger.info("[DRY-RUN] Would trigger Soft Reload (reload_residents).")
                return "DRY_RUN_SOFT_RELOAD"
            else:
                logger.info("Triggering fast soft hot-reload (VRAM preserved)...")
                reload_resp = call_attendant_api('POST', RELOAD_URL)
                logger.info(f"Reload response: {reload_resp}")
                clear_pending_reset()
                return "EXECUTED_SOFT_RELOAD"
                
    logger.info("✅ Systems Nominal. No code changes require reload. Foyer is healthy.")
    return "OK_NOMINAL"

def run_legacy_boot_monitor():
    """Legacy boot monitor loop for manual full restarts."""
    start_time = time.time()
    logger.info("Starting Lab Attendant Boot Monitor (Legacy)")
    print(f"Total timeout: {TIMEOUT_SEC}s")

    current_status = call_attendant_api('GET', STATUS_URL)
    initial_lab_ready = current_status.get('engine_vocal', False) or current_status.get('vocal', False)
    lab_pid = current_status.get('attendant_pid', 'N/A')

    if initial_lab_ready:
        print(f"\n[Monitor] ✅ Lab is already READY (PID: {lab_pid})!")
        sys.exit(0)

    print("\n[Monitor] Performing cleanup and start...")
    call_attendant_api('POST', CLEANUP_URL)
    call_attendant_api('POST', START_URL, json_payload={"mode": "SERVICE_UNATTENDED", "disable_ear": True})

    poll_start_time = time.time()
    while time.time() - start_time < TIMEOUT_SEC:
        current_status = call_attendant_api('GET', STATUS_URL)
        if current_status.get('status') != 'error':
            ready = current_status.get('engine_vocal', False) or current_status.get('vocal', False)
            if ready:
                print('\n[Monitor] ✅ Lab is fully READY!')
                sys.exit(0)
        time.sleep(POLL_INTERVAL_SEC)

    print('\n[Monitor] ❌ Timeout: Lab did not become ready within allocated time.')
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Lab Attendant Liveliness & 30-Minute Supervisory Watchdog")
    parser.add_argument("--supervise", "--daemon", action="store_true", help="Run continuous supervisory loop (default every 30m)")
    parser.add_argument("--interval", type=int, default=DEFAULT_SUPERVISORY_INTERVAL_SEC, help="Supervisory interval in seconds (default: 1800)")
    parser.add_argument("--once", action="store_true", help="Run a single supervisory check and exit")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate health and code changes without sending commands")
    parser.add_argument("--boot-monitor", action="store_true", help="Run legacy boot monitor until lab is ready")

    args = parser.parse_args()

    if args.boot_monitor:
        run_legacy_boot_monitor()
        return

    if args.supervise:
        logger.info(f"Starting continuous supervisor loop (interval: {args.interval}s / {args.interval//60}m)...")
        try:
            while True:
                run_supervisory_tick(dry_run=args.dry_run)
                logger.info(f"Sleeping for {args.interval}s until next supervisory cycle...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Supervisor stopped by user.")
            sys.exit(0)
    else:
        # Default to single tick
        result = run_supervisory_tick(dry_run=args.dry_run)
        print(f"[RESULT] {result}")
        sys.exit(0 if not result.startswith("ERROR") else 1)

if __name__ == "__main__":
    main()
