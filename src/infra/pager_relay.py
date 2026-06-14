import os
import json
import time
import sys
import logging

# Setup paths for internal imports
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if LAB_DIR not in sys.path:
    sys.path.append(LAB_DIR)

from infra.atomic_io import atomic_write_json

WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
PAGER_FILE = os.path.join(WORKSPACE_DIR, "field_notes/data/pager_activity.json")

def trigger_pager(message, severity="INFO", source="System"):
    """
    [BKM-014] Neural Pager Bridge.
    Appends events to the interleaved dashboard ledger.
    """
    try:
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "severity": severity.upper(),
            "source": source,
            "message": message
        }
        
        data = []
        if os.path.exists(PAGER_FILE):
            try:
                with open(PAGER_FILE, 'r') as f:
                    data = json.load(f)
            except: 
                # Handle corrupted JSON
                data = []
            
        # De-duplicate: Don't log the exact same message from the same source twice in a row
        if data and data[0].get("message") == message and data[0].get("source") == source:
            return

        data.insert(0, entry)
        # Keep last 100 for the interleaved dashboard
        data = data[:100]
        
        atomic_write_json(PAGER_FILE, data)
        
        # Optional: Trigger external PagerDuty if critical
        if severity.upper() == "CRITICAL":
            try:
                GATEKEEPER = os.path.join(WORKSPACE_DIR, "monitor/notify_gatekeeper.py")
                import subprocess
                subprocess.Popen([sys.executable, GATEKEEPER, message, "--severity", "critical", "--emergency"])
            except: pass
            
    except Exception as e:
        logging.error(f"[PAGER] Relay failed: {e}")

if __name__ == "__main__":
    # CLI mode for testing
    if len(sys.argv) > 1:
        msg = sys.argv[1]
        src = sys.argv[2] if len(sys.argv) > 2 else "Manual"
        sev = sys.argv[3] if len(sys.argv) > 3 else "INFO"
        trigger_pager(msg, severity=sev, source=src)
        print(f"Logged to pager: {msg}")
