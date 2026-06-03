import asyncio
import json
import logging
import os
import time
import fcntl
import psutil
import subprocess
import sys
import uuid
from typing import Dict, Set

# Add src to path for common imports
V5_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.dirname(V5_DIR)
LAB_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from v5.common.types import LabStatus, IntentEvent

# [Task 4.4] V5 Ignition: The physical Hardware Guardian
# Objective: Manage silicon state and certify ALARM tasks.

VRAM_LOCK_FILE = "/tmp/lab_vram.lock"
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")
MAINTENANCE_LOCK = os.path.join(DATA_DIR, "maintenance.lock")
GEM_REFINER = os.path.join(WORKSPACE_DIR, "field_notes/refine_gem.py")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [IGNITION] - %(levelname)s - %(message)s')

class IgnitionManager:
    def __init__(self):
        self.status = LabStatus()
        self._vram_lock_fd = None
        self.processed_ids = set()

    def _acquire_vram_lock(self):
        try:
            if self._vram_lock_fd is None:
                self._vram_lock_fd = open(VRAM_LOCK_FILE, 'w')
            fcntl.flock(self._vram_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logging.info("[IGNITION] VRAM Mutex acquired.")
            return True
        except (IOError, OSError):
            return False

    def _release_vram_lock(self):
        if self._vram_lock_fd is not None:
            try:
                fcntl.flock(self._vram_lock_fd, fcntl.LOCK_UN)
                logging.info("[IGNITION] VRAM Mutex released.")
            except Exception: pass

    async def start_lab(self, reason="INTENT"):
        """V5 Physical Ignition."""
        if self.status.state in ["WAKING", "OPERATIONAL"]:
            return True

        if not self._acquire_vram_lock():
            return False

        self.status.state = "WAKING"
        self.update_status_file()
        logging.info(f"[IGNITION] Waking physical silicon for: {reason}")
        
        try:
            # Physical hardware ignition
            vllm_script = os.path.join(LAB_DIR, "src/start_vllm.sh")
            env = os.environ.copy()
            logging.info(f"[IGNITION] Spawning vLLM engine via {vllm_script}...")
            
            # We run it detached so it survives the manager script block
            subprocess.Popen(["bash", vllm_script], cwd=LAB_DIR, env=env)
            
            # Poll for API readiness
            api_ready = False
            for _ in range(60): # Up to 5 minutes
                try:
                    import urllib.request
                    urllib.request.urlopen("http://localhost:8088/v1/models", timeout=2)
                    api_ready = True
                    break
                except Exception:
                    await asyncio.sleep(5)
            
            if not api_ready:
                logging.error("[IGNITION] vLLM failed to bind port 8088 within 5 minutes.")
                self.status.state = "ERROR"
                return False

            self.status.state = "OPERATIONAL"
            self.status.engine_up = True
            self.status.vocal = True
            logging.info("[IGNITION] Physical silicon is READY.")
            return True
        finally:
            self._release_vram_lock()
            self.update_status_file()

    def update_status_file(self):
        self.status.timestamp = time.time()
        with open(STATUS_JSON, "w") as f:
            json.dump(self.status.to_dict(), f, indent=2)

    async def queue_watcher(self):
        """[Task 4.3] Monitors the foyer queue for new intent."""
        logging.info(f"[IGNITION] Queue watcher started.")
        last_pos = 0
        if os.path.exists(QUEUE_FILE):
            last_pos = os.path.getsize(QUEUE_FILE)

        while True:
            try:
                if os.path.exists(QUEUE_FILE):
                    size = os.path.getsize(QUEUE_FILE)
                    if size > last_pos:
                        with open(QUEUE_FILE, "r") as f:
                            f.seek(last_pos)
                            for line in f:
                                if not line.strip(): continue
                                try:
                                    event = IntentEvent.from_json(line)
                                    if event.status == "PENDING" and event.id not in self.processed_ids:
                                        logging.info(f"[IGNITION] New Intent: {event.id}")
                                        self.processed_ids.add(event.id)
                                        if self.status.state in ["HIBERNATING", "UNKNOWN", "ERROR"]:
                                            asyncio.create_task(self.start_lab(reason=f"INTENT_{event.id}"))
                                except Exception: pass
                            last_pos = f.tell()
            except Exception: pass
            await asyncio.sleep(1)

    async def continuous_burn_loop(self):
        """[Task 2.4] Quiet Refinement."""
        logging.info("[IGNITION] Continuous Burn loop active.")
        while True:
            try:
                idle_time = time.time() - self.status.timestamp
                if idle_time > 3600:
                    logging.info("[IGNITION] System Idle. Triggering Quiet Refinement...")
                    # Future: Logic to run refine_gem.py safely
                    await asyncio.sleep(3600)
            except Exception: pass
            await asyncio.sleep(300)

    async def main_loop(self):
        logging.info("[IGNITION] V5 Ignition Manager Active.")
        asyncio.create_task(self.queue_watcher())
        asyncio.create_task(self.continuous_burn_loop())
        while True:
            self.update_status_file()
            await asyncio.sleep(30)

if __name__ == "__main__":
    manager = IgnitionManager()
    asyncio.run(manager.main_loop())
