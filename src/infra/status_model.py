import os
import json
import datetime
import logging
from infra.atomic_io import atomic_write_json

# Paths
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
STATUS_JSON = os.path.join(PORTFOLIO_DIR, "field_notes/data/status.json")

logger = logging.getLogger("status_model")

class StatusModel:
    """
    [FEAT-045] Split Status Model: Physical vs Logical Bifurcation.
    Source of truth for the dashboard.
    """
    def __init__(self):
        self.state = {
            "physical": {
                "status": "OFFLINE",
                "vram_used_mib": 0,
                "vram_total_mib": 11264,
                "engine_active": False,
                "lab_active": False,
                "last_heartbeat": None
            },
            "logical": {
                "persona": "The Shadow",
                "mode": "IDLE",
                "task": "None",
                "readiness": "OFFLINE"
            },
            "timestamp": None
        }
        self.load()

    def load(self):
        if os.path.exists(STATUS_JSON):
            try:
                with open(STATUS_JSON, "r") as f:
                    disk_data = json.load(f)
                    # Support legacy structure mapping if needed
                    if "vitals" in disk_data:
                        self.state["physical"]["lab_active"] = disk_data["vitals"].get("lab_server_running", False)
                        self.state["physical"]["engine_active"] = disk_data["vitals"].get("engine_running", False)
            except Exception: pass

    def update_physical(self, **kwargs):
        self.state["physical"].update(kwargs)
        self.state["physical"]["last_heartbeat"] = datetime.datetime.now().isoformat()
        self.save()

    def update_logical(self, **kwargs):
        self.state["logical"].update(kwargs)
        self.save()

    def save(self):
        self.state["timestamp"] = datetime.datetime.now().isoformat()
        try:
            atomic_write_json(STATUS_JSON, self.state)
        except Exception as e:
            logger.error(f"[STATUS] Failed to save: {e}")

    def get_summary(self):
        return {
            "status": "ONLINE" if self.state["physical"]["lab_active"] else "OFFLINE",
            "message": f"{self.state['logical']['persona']} is {self.state['logical']['mode']}",
            "timestamp": self.state["timestamp"],
            "vitals": self.state["physical"]
        }
