import asyncio
import json
import logging
import os
import time
import fcntl
import psutil
from common.types import LabStatus, IntentEvent

# [Task 4.4] V5 Ignition: The Larynx-Aware Hardware Manager (Refined)
# Objective: Manage silicon state and verify readiness via Vocal Handshake.

VRAM_LOCK_FILE = "/tmp/lab_vram.lock"
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [IGNITION] - %(levelname)s - %(message)s')

class IgnitionManager:
    def __init__(self):
        self.status = LabStatus()
        self._vram_lock_fd = None
        self.active_tasks = set()

    def _acquire_vram_lock(self):
        """[Task 1.4] Physical VRAM Mutex."""
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

    async def start_lab(self):
        """[FEAT-265.8] Ignition sequence."""
        if not self._acquire_vram_lock():
            logging.info("[IGNITION] Silicon busy. Aborting start.")
            return False

        self.status.state = "WAKING"
        self.update_status_file()
        logging.info("[IGNITION] Starting Lab services...")
        
        try:
            # 1. Start vLLM / Nodes
            logging.info("[IGNITION] Spawning Node stack...")
            # Future: Actual subprocess spawning
            await asyncio.sleep(2.0)
            
            # 2. Wait for Vocal Handshake
            # [Task 4.4] Larynx-Aware check
            success = await self._verify_vocal_handshake()
            
            if success:
                self.status.state = "OPERATIONAL"
                self.status.engine_up = True
                self.status.vocal = True
                logging.info("[IGNITION] Lab is VOCAL and OPERATIONAL.")
                return True
            else:
                self.status.state = "ERROR"
                logging.warning("[IGNITION] Vocal handshake failed.")
                return False
        finally:
            self._release_vram_lock()
            self.update_status_file()

    async def _verify_vocal_handshake(self):
        """Probes the node stack for a 'READY' signal."""
        logging.info("[IGNITION] Probing Larynx...")
        # Future: Real WebSocket probe to Brain
        await asyncio.sleep(1.0)
        return True

    def update_status_file(self):
        self.status.timestamp = time.time()
        with open(STATUS_JSON, "w") as f:
            json.dump(self.status.to_dict(), f, indent=2)

    async def queue_watcher(self):
        """[Task 4.3] Monitors the foyer queue for new intent."""
        last_pos = 0
        while True:
            try:
                if os.path.exists(QUEUE_FILE):
                    size = os.path.getsize(QUEUE_FILE)
                    if size > last_pos:
                        with open(QUEUE_FILE, "r") as f:
                            f.seek(last_pos)
                            for line in f:
                                event = IntentEvent.from_json(line)
                                if event.status == "PENDING":
                                    logging.info(f"[IGNITION] Detected pending intent: {event.id}")
                                    if self.status.state == "HIBERNATING":
                                        asyncio.create_task(self.start_lab())
                            last_pos = f.tell()
            except Exception as e:
                logging.error(f"Queue watcher error: {e}")
            await asyncio.sleep(1)

    async def main_loop(self):
        logging.info("[IGNITION] Main loop started.")
        asyncio.create_task(self.queue_watcher())
        while True:
            self.update_status_file()
            # [Task 2.4] Continuous Burn: Future refinement tasks
            await asyncio.sleep(5.0)

if __name__ == "__main__":
    manager = IgnitionManager()
    asyncio.run(manager.main_loop())
