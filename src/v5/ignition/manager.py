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

# Add src to path for common and residents imports
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if LAB_DIR not in sys.path:
    sys.path.append(LAB_DIR)

from v5.common.types import LabStatus, IntentEvent
from v5.common.residents import ResidentManager

# [Task 4.4] V5 Ignition: The Larynx-Aware Hardware Manager
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
        self.session_token = uuid.uuid4().hex[:8]
        self.residents = ResidentManager(self.session_token)
        self._vram_lock_fd = None
        self._background_tasks = set()

    def _acquire_vram_lock(self):
        try:
            if self._vram_lock_fd is None:
                self._vram_lock_fd = open(VRAM_LOCK_FILE, 'w')
            fcntl.flock(self._vram_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (IOError, OSError):
            return False

    def _release_vram_lock(self):
        if self._vram_lock_fd is not None:
            try:
                fcntl.flock(self._vram_lock_fd, fcntl.LOCK_UN)
            except Exception: pass

    async def start_lab(self, reason="INTENT"):
        """V5 Ignition Sequence."""
        if self.status.state in ["WAKING", "OPERATIONAL"]:
            return True

        if not self._acquire_vram_lock():
            logging.info("[IGNITION] VRAM Mutex busy. Waiting for next cycle.")
            return False

        self.status.state = "WAKING"
        self.update_status_file()
        logging.info(f"[IGNITION] Starting Lab services for: {reason}")
        
        try:
            # 1. Boot Residents
            await self.residents.boot_all()
            
            # 2. Larynx Probe
            success = await self._verify_vocal_handshake()
            
            if success:
                self.status.state = "OPERATIONAL"
                self.status.engine_up = True
                self.status.vocal = True
                logging.info("[IGNITION] Lab is VOCAL and OPERATIONAL.")
                return True
            else:
                self.status.state = "ERROR"
                return False
        finally:
            self._release_vram_lock()
            self.update_status_file()

    async def _verify_vocal_handshake(self):
        """Probes the node stack for a 'READY' signal."""
        lab_node = self.residents.get_node("lab")
        if lab_node:
            try:
                # [FEAT-295] Larynx Hardening
                await lab_node.call_tool(
                    name="think",
                    arguments={"query": "[ME] [INTERNAL] Larynx Ping", "internal": True}
                )
                return True
            except Exception as e:
                logging.error(f"[IGNITION] Larynx Probe failed: {e}")
        return False

    def update_status_file(self):
        with open(STATUS_JSON, "w") as f:
            json.dump(self.status.to_dict(), f, indent=2)

    async def run_nightly_tasks(self):
        """[Task 2.3] ALARM Resilience: Migration of acme_lab.py induction logic."""
        if not self.status.vocal:
            await self.start_lab(reason="ALARM_NIGHTLY")
        
        logging.info("[ALARM] Starting Nightly Induction...")
        
        # 1. Internal Debate
        try:
            from internal_debate import run_nightly_talk
            await run_nightly_talk(
                self.residents.get_node("archive"),
                self.residents.get_node("pinky"),
                self.residents.get_node("brain")
            )
        except Exception as e:
            logging.error(f"[ALARM] Debate failed: {e}")

    async def continuous_burn_loop(self):
        """[Task 2.4] Quiet Refinement: Performs background gem-refining when idle."""
        logging.info("[IGNITION] Continuous Burn loop active.")
        while True:
            try:
                # 1. Activity & Pressure Gate
                idle_time = time.time() - self.status.timestamp
                is_idle = (idle_time > 3600) # 1h idle
                
                vram_free = 0
                try:
                    res = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"])
                    vram_free = int(res.decode().strip())
                except Exception: pass

                if is_idle and vram_free > 4000: # > 4GB free
                    logging.info("[IGNITION] System Idle. Triggering Quiet Refinement...")
                    if os.path.exists(GEM_REFINER):
                        if not self.status.vocal:
                            await self.start_lab(reason="QUIET_REFINEMENT")
                        
                        proc = await asyncio.create_subprocess_exec(
                            sys.executable, GEM_REFINER,
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                            cwd=os.path.dirname(GEM_REFINER)
                        )
                        stdout, stderr = await proc.communicate()
                        if proc.returncode == 0:
                            logging.info(f"[ALARM] Refinement Success.")
                        else:
                            logging.error(f"[ALARM] Refinement Failed.")
                    
                    await asyncio.sleep(3600) # Only refine once per hour
                
            except Exception as e:
                logging.error(f"Continuous Burn error: {e}")
            await asyncio.sleep(300) # Check every 5m

    async def main_loop(self):
        logging.info("[IGNITION] V5 Ignition Manager Active.")
        asyncio.create_task(self.continuous_burn_loop())
        while True:
            self.update_status_file()
            
            # [Task 2.4] Nightly trigger
            now = time.localtime()
            if now.tm_hour == 2 and self.status.state == "HIBERNATING":
                 asyncio.create_task(self.run_nightly_tasks())

            await asyncio.sleep(30)

if __name__ == "__main__":
    manager = IgnitionManager()
    asyncio.run(manager.main_loop())
