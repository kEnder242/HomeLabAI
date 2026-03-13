import os
import json
import datetime
import logging
from infra.atomic_io import atomic_write_json
from debug.trace_monitor import TraceMonitor

# Paths
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
PAGER_ACTIVITY_FILE = os.path.join(PORTFOLIO_DIR, "field_notes/data/pager_activity.json")
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
ATTENDANT_LOG = os.path.join(LAB_DIR, "attendant.log")

logger = logging.getLogger("forensic_ledger")

class ForensicLedger:
    """
    [FEAT-151] Forensic Ledger: Structured Silicon Logging.
    Captures state transitions and physical trace evidence during autonomous transitions.
    """
    def __init__(self):
        self.monitor = TraceMonitor([SERVER_LOG, ATTENDANT_LOG])
        self.ensure_ledger_exists()

    def ensure_ledger_exists(self):
        if not os.path.exists(PAGER_ACTIVITY_FILE):
            atomic_write_json(PAGER_ACTIVITY_FILE, [])

    def record_event(self, severity: str, message: str, metadata: dict = None):
        """
        Records a structured event with physical trace evidence.
        """
        timestamp = datetime.datetime.now().isoformat()
        
        # Capture trace delta
        trace = self.monitor.capture_delta()
        
        event = {
            "timestamp": timestamp,
            "severity": severity,
            "message": message,
            "metadata": metadata or {},
            "trace": trace
        }

        try:
            with open(PAGER_ACTIVITY_FILE, "r") as f:
                ledger = json.load(f)
            
            # Keep only last 100 events to prevent blow-out
            ledger.append(event)
            ledger = ledger[-100:]
            
            atomic_write_json(PAGER_ACTIVITY_FILE, ledger)
            logger.info(f"[FORENSIC] Event recorded: {message}")
        except Exception as e:
            logger.error(f"[FORENSIC] Failed to record event: {e}")

    def refresh_marks(self):
        """Resets the trace markers to the current EOF."""
        self.monitor.refresh_marks()
