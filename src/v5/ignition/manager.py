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

# [FEAT-122] Kernel-Level Visibility
try:
    import setproctitle
except ImportError:
    setproctitle = None

class IgnitionManager:
    def __init__(self):
        # Rename process
        if setproctitle:
            setproctitle.setproctitle("acme_ignition_v5")
            
        self.status = LabStatus()
        self._vram_lock_fd = None
        from collections import deque
        self.processed_ids = deque(maxlen=1000) # [Task 6.3] Hygiene: Prevent memory leaks
        self.last_induction_date = None # [FEAT-289] Atomic Induction
        self.last_activity_time = time.time() # [Task 4.1] Idle tracking

    def _acquire_vram_lock(self):
        """[FEAT-287] Mutual Exclusion (Ignition Mutex)."""
        try:
            if self._vram_lock_fd is None:
                self._vram_lock_fd = open(VRAM_LOCK_FILE, 'w')
            fcntl.flock(self._vram_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logging.info("[IGNITION] VRAM Mutex acquired.")
            return True
        except (IOError, OSError):
            logging.warning("[IGNITION] VRAM Mutex busy (locked by another process).")
            return False

    def _release_vram_lock(self):
        if self._vram_lock_fd is not None:
            try:
                fcntl.flock(self._vram_lock_fd, fcntl.LOCK_UN)
                logging.info("[IGNITION] VRAM Mutex released.")
            except Exception: pass

    async def start_lab(self, reason="INTENT"):
        """[FEAT-265.8] Ignition sequence."""
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
                self._release_vram_lock() # Release on failure
                return False

            self.status.state = "OPERATIONAL"
            self.status.engine_up = True
            self.status.vocal = True
            logging.info("[IGNITION] Physical silicon is READY.")
            # [Task 6.6] Lock is NOT released here; it is held while OPERATIONAL
            return True
        except Exception:
            self._release_vram_lock() # Release on crash
            self.update_status_file()
            raise

    def update_status_file(self):
        """[FEAT-265] Multi-host status synchronization."""
        self.status.timestamp = time.time()
        try:
            with open(STATUS_JSON, "w") as f:
                json.dump(self.status.to_dict(), f, indent=2)
            
            # [Task 6.2] Latency: Async status push
            def _push_update():
                try:
                    import requests
                    requests.post("http://localhost:8765/status_update", json=self.status.to_dict(), timeout=0.5)
                except Exception: pass
            
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_in_executor(None, _push_update)
            else:
                _push_update()
        except Exception: pass

    async def stop_lab(self, reason="AFK"):
        """[Task 4.1] Stable Hibernation: Strict subprocess termination."""
        logging.info(f"[IGNITION] Initiating Deep Sleep: {reason}")
        
        # 1. Notify Foyer to release logical nodes (VRAM Hygiene)
        try:
            import requests
            requests.post("http://localhost:8765/release_nodes", timeout=5)
        except Exception as e:
            logging.warning(f"[IGNITION] Failed to notify Foyer for node release: {e}")

        # 2. Targeted Kill of vLLM (Read PID file)
        try:
            pid_file = os.path.join(LAB_DIR, "run/vllm.pid")
            if os.path.exists(pid_file):
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())
                logging.info(f"[IGNITION] Sending SIGKILL to vLLM PID: {pid}")
                subprocess.run(["sudo", "kill", "-9", str(pid)], check=False)
                os.remove(pid_file)
        except Exception as e:
            logging.debug(f"[IGNITION] PID-based kill failed: {e}")

        # 3. Recursive cleanup (EngineCore and rogue vllm)
        try:
            # [FEAT-036] Release port 8088 and kill survivors
            # [FIX] Avoid fuser -k as it kills clients holding sockets (e.g. Gemini CLI)
            # Adhere to 'The Blacklist Law': Only kill what we own.
            subprocess.run(["sudo", "pkill", "-9", "-f", "vllm.entrypoints.openai.api_server"], check=False)
            subprocess.run(["sudo", "pkill", "-9", "-f", "VLLM::EngineCore"], check=False)
        except Exception: pass
        
        # 4. Reset Status
        self.status.state = "HIBERNATING"
        self.status.engine_up = False
        self.status.vocal = False
        self._release_vram_lock() # [Task 6.6] Release silicon lock on deep sleep
        self.update_status_file()
        logging.info("[IGNITION] Deep Sleep confirmed. VRAM released.")
        return True

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
                                        logging.info(f"[IGNITION] New Intent Detected: {event.id} (State: {self.status.state})")
                                        self.processed_ids.append(event.id)
                                        self.last_activity_time = time.time() # Reset idle timer
                                        
                                        # Handle remote control operational intents
                                        if event.query.startswith("[OPERATIONAL]"):
                                            op = event.query.split(" ")[1]
                                            if op == "HIBERNATE" or op == "STOP":
                                                asyncio.create_task(self.stop_lab(reason=f"REMOTE_{op}"))
                                            elif op == "QUIESCE":
                                                self.status.state = "MAINTENANCE"
                                                self.update_status_file()
                                            elif op == "START":
                                                if self.status.state in ["HIBERNATING", "UNKNOWN", "ERROR", "MAINTENANCE"]:
                                                    logging.info(f"[IGNITION] Triggering ignition task for {event.id}...")
                                                    asyncio.create_task(self.start_lab(reason=f"INTENT_{event.id}"))
                                                else:
                                                    logging.info(f"[IGNITION] Lab already {self.status.state}. Skipping ignition.")
                                        # Normal intents
                                        elif self.status.state in ["HIBERNATING", "UNKNOWN", "ERROR"]:
                                            logging.info(f"[IGNITION] Triggering ignition task for {event.id}...")
                                            asyncio.create_task(self.start_lab(reason=f"INTENT_{event.id}"))
                                        else:
                                            logging.info(f"[IGNITION] Lab already {self.status.state}. Skipping ignition.")
                                except Exception as e:
                                    logging.error(f"[IGNITION] Intent processing error: {e}")

                            last_pos = f.tell()
            except Exception: pass
            await asyncio.sleep(1)

    async def continuous_burn_loop(self):
        """[FEAT-266] Periodic Maintenance (ALARM tasks)."""
        import datetime
        logging.info("[IGNITION] Continuous Burn loop active.")
        while True:
            try:
                now = datetime.datetime.now()
                today = now.date()
                
                # 1. AFK Hibernation (Task 4.1)
                idle_time = time.time() - self.last_activity_time
                if idle_time > 120 and self.status.state == "OPERATIONAL":
                    await self.stop_lab(reason="AFK_TIMEOUT")

                # 2. Daily Induction Window (02:00 - 04:00)
                is_window = (2 <= now.hour < 4)
                if is_window and self.last_induction_date != today:
                    # [FEAT-289] Atomic Induction: Mark today as started
                    self.last_induction_date = today
                    logging.info("[ALARM] Entering Daily Induction Window...")
                    
                    # Try to acquire silicon mutex
                    if self._acquire_vram_lock():
                        try:
                            # Step 1: Nightly Recruiter
                            logging.info("[ALARM] Step 1: Nightly Recruiter...")
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/acme_lab.py"), "--trigger-task", "recruiter"], env=os.environ.copy())
                            
                            # Step 2: Hierarchy Refactor
                            logging.info("[ALARM] Step 2: Hierarchy Refactor...")
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/acme_lab.py"), "--trigger-task", "lab"], env=os.environ.copy())
                            
                            # Step 3: Sequenced Batch Forge
                            logging.info("[ALARM] Step 3: Sequenced Batch Forge...")
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/acme_lab.py"), "--trigger-task", "forge"], env=os.environ.copy())
                        finally:
                            self._release_vram_lock()
                            self.status.timestamp = time.time() 
                    else:
                        logging.warning("[ALARM] Silicon busy (Mutex Locked). Deferring induction.")
                        self.last_induction_date = None

                # 3. Slow Burn: Idle GEM Refinement
                idle_time = time.time() - self.status.timestamp
                if idle_time > 3600 and self.status.state == "HIBERNATING":
                    logging.info("[IGNITION] System Idle > 1hr. Triggering Quiet Refinement...")
                    if self._acquire_vram_lock():
                        try:
                            refiner = os.path.join(LAB_DIR, "field_notes/refine_gem.py")
                            if os.path.exists(refiner):
                                subprocess.run([sys.executable, refiner, "--one-turn"], env=os.environ.copy())
                        finally:
                            self._release_vram_lock()
                            self.status.timestamp = time.time()
                
            except Exception as e:
                logging.error(f"[ALARM] Continuous Burn failure: {e}")
            
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
