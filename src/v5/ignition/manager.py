import asyncio
import json
import logging
import os
import time
import fcntl
import psutil
import subprocess
import sys

# Add src to path for common imports
V5_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.dirname(V5_DIR)
LAB_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from v5.common.types import LabStatus, IntentEvent
from infra.pager_relay import trigger_pager

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
        self.last_induction = None
        self.last_induction_date = None # [FEAT-289] Atomic Induction
        self.last_activity_time = time.time() # [Task 4.1] Idle tracking
        # [FEAT-302] & [FEAT-323] Recovery backoff attributes
        self.recovery_attempts = 0
        self.cooldown_until = 0.0
        self.operational_start_time = 0.0
        self.recovery_in_progress = False
    def record_pager(self, message, severity="INFO", source="LabAttendant"):
        """[Task 9.9] Centralized Pager Logging."""
        trigger_pager(message, severity=severity, source=source)

    async def journal_monitor(self):
        """[Task 9.10] Interleaved System Logs: Bridges journalctl to Pager."""
        logging.info("[IGNITION] Journal monitor started.")
        # Filter for interesting non-lab services
        cmd = ["journalctl", "-f", "-n", "0", "--no-pager"]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode().strip()
                
                # Pattern Matching for "Interleaved" logs
                # Focus on interesting events and errors
                if any(x in text for x in ["Started", "Stopped", "error", "failed", "offline", "online"]):
                    # Ignore internal lab chatter (already logged via record_pager)
                    if not any(x in text for x in ["python3", "acme_foyer", "acme_ignition"]):
                        # Extract source (crude heuristic)
                        try:
                            parts = text.split("z87-Linux ")
                            if len(parts) > 1:
                                content = parts[1]
                                source = content.split("[")[0].split(":")[0].strip()
                                msg = content.split(": ", 1)[1] if ":" in content else content
                                self.record_pager(msg[:200], source=source)
                        except Exception: pass
        except Exception as e:
            logging.error(f"[IGNITION] Journal monitor failed: {e}")

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

        # [FEAT-302] Adaptive Cooldown Tracking
        now = time.time()
        if now < self.cooldown_until:
            remaining = int(self.cooldown_until - now)
            logging.warning(f"[IGNITION] Ignition request rejected. Cooldown active. Try again in {remaining}s.")
            return False

        if not self._acquire_vram_lock():
            return False

        self.recovery_in_progress = True
        self.status.state = "WAKING"
        self.update_status_file()
        logging.info(f"[IGNITION] Waking physical silicon for: {reason}")
        self.record_pager(f"IGNITION_START ({reason})", severity="INFO")
        
        # [Task 12.1] KENDER Parallel Warmup
        async def _bg_prime_kender():
            try:
                import aiohttp
                import json
                kender_ip = "192.168.1.26"
                try:
                    infra_path = os.path.join(LAB_DIR, "config/infrastructure.json")
                    if os.path.exists(infra_path):
                        with open(infra_path, "r") as f:
                            infra = json.load(f)
                            kender_ip = infra.get("hosts", {}).get("KENDER", {}).get("ip_hint", kender_ip)
                except Exception: pass
                
                # Ping with a typical sovereign model to force VRAM load
                payload = {"model": "gemma4:26b", "prompt": "ping", "stream": False, "options": {"num_predict": 1}}
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"http://{kender_ip}:11434/api/generate", json=payload, timeout=30) as r:
                        if r.status == 200:
                            logging.info("[IGNITION] KENDER Parallel Warmup SUCCESS.")
            except Exception as e:
                logging.debug(f"[IGNITION] KENDER Parallel Warmup failed/bypassed: {e}")
        asyncio.create_task(_bg_prime_kender())
        
        try:
            # Physical hardware ignition
            vllm_script = os.path.join(LAB_DIR, "src/start_vllm.sh")
            env = os.environ.copy()
            logging.info(f"[IGNITION] Spawning vLLM engine via {vllm_script}...")
            
            # We run it detached so it survives the manager script block
            subprocess.Popen(["bash", vllm_script], cwd=LAB_DIR, env=env)
            
            # Poll for API readiness and perform cognitive vocality check
            api_ready = False
            for _ in range(60): # Up to 5 minutes
                try:
                    import urllib.request
                    import json
                    # 1. Basic model list check (port binding check)
                    req_models = urllib.request.Request("http://localhost:8088/v1/models")
                    with urllib.request.urlopen(req_models, timeout=2) as resp_models:
                        if resp_models.status != 200:
                            raise Exception(f"Model list returned status {resp_models.status}")
                    
                    # 2. Cognitive probe: Force-check real text generation
                    payload = {
                        "model": "unified-base", 
                        "messages": [{"role": "user", "content": "Respond with the word SUCCESS."}],
                        "max_tokens": 10,
                        "temperature": 0.0
                    }
                    data_bytes = json.dumps(payload).encode('utf-8')
                    req_chat = urllib.request.Request(
                        "http://localhost:8088/v1/chat/completions",
                        data=data_bytes,
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req_chat, timeout=5) as response:
                        if response.status == 200:
                            api_ready = True
                            logging.info("[IGNITION] Cognitive probe SUCCESS. Engine is vocal.")
                            break
                        else:
                            raise Exception(f"Cognitive probe returned status {response.status}")
                except Exception as e:
                    logging.debug(f"[IGNITION] API probe failed (retrying): {e}")
                    await asyncio.sleep(5)
            
            if not api_ready:
                logging.error("[IGNITION] vLLM failed to bind port 8088 within 5 minutes.")
                self.recovery_attempts += 1
                cooldown = 5 + (self.recovery_attempts * 120)
                self.cooldown_until = time.time() + cooldown
                self.status.state = "ERROR"
                self.recovery_in_progress = False
                self._release_vram_lock() # Release on failure
                self.update_status_file()
                return False

            self.status.state = "OPERATIONAL"
            self.status.engine_up = True
            self.status.vocal = True
            self.operational_start_time = time.time()
            self.recovery_in_progress = False
            logging.info("[IGNITION] Physical silicon is READY.")
            # [Task 6.6] Lock is NOT released here; it is held while OPERATIONAL
            self.update_status_file()
            return True
        except Exception:
            self.recovery_attempts += 1
            cooldown = 5 + (self.recovery_attempts * 120)
            self.cooldown_until = time.time() + cooldown
            self.recovery_in_progress = False
            self.status.state = "ERROR"
            self._release_vram_lock() # Release on crash
            self.update_status_file()
            raise

    def update_status_file(self):
        """[FEAT-265] Multi-host status synchronization."""
        self.status.timestamp = time.time()
        
        # [Task 9.7] Live Telemetry Polling
        try:
            self.status.ram_pct = psutil.virtual_memory().percent
            import pynvml
            try:
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                self.status.vram_used = int(info.used // 1024**2)
                self.status.vram_total = int(info.total // 1024**2)
            except Exception: pass
        except Exception: pass

        # [FEAT-323] Expose recovery info to status
        self.status.recovery_level = self.recovery_attempts
        self.status.recovery_in_progress = self.recovery_in_progress

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

    async def stop_lab(self, reason="AFK", target_state="HIBERNATING"):
        """[Task 4.1] Stable Hibernation: Strict subprocess termination."""
        logging.info(f"[IGNITION] Initiating Deep Sleep: {reason}")
        self.record_pager(f"HIBERNATION_START ({reason})", severity="INFO")
        
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
        self.status.state = target_state
        self.status.engine_up = False
        self.status.vocal = False
        self._release_vram_lock() # [Task 6.6] Release silicon lock on deep sleep
        self.update_status_file()
        logging.info("[IGNITION] Deep Sleep confirmed. VRAM released.")
        return True

    async def queue_watcher(self):
        """[Task 4.3] Monitors the foyer queue for new intent."""
        logging.info("[IGNITION] Queue watcher started.")
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
                                            if op == "SLEEP":
                                                asyncio.create_task(self.stop_lab(reason="REMOTE_SLEEP", target_state="HIBERNATING"))
                                            elif op == "SHUTDOWN":
                                                asyncio.create_task(self.stop_lab(reason="REMOTE_SHUTDOWN", target_state="OFFLINE"))
                                            elif op == "LOCK":
                                                # Create maintenance lock file
                                                try: open(MAINTENANCE_LOCK, 'w').close()
                                                except Exception: pass
                                                self.status.state = "MAINTENANCE"
                                                self.update_status_file()
                                            elif op == "WAKE":
                                                self.last_activity_time = time.time() # [Task 15.3] Reset timer for ALL wake attempts
                                                if os.path.exists(MAINTENANCE_LOCK):
                                                    try: os.remove(MAINTENANCE_LOCK)
                                                    except Exception: pass
                                                if self.status.state in ["HIBERNATING", "UNKNOWN", "ERROR", "MAINTENANCE", "OFFLINE"]:
                                                    logging.info(f"[IGNITION] Triggering wake task for {event.id}...")
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

    async def get_foyer_clients(self) -> int:
        """Query Foyer status to get active client count."""
        import urllib.request
        import json
        try:
            url = "http://127.0.0.1:8765/status"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=1.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get("connected_clients", 0)
        except Exception:
            pass
        return 0

    async def is_engine_active(self) -> bool:
        """
        [FEAT-374] Tiered Idle Verification Pattern
        Checks Tier 1 (TCP connections on port 8088) and Tier 2 (vLLM metrics).
        Returns True if active, False if idle.
        """
        if self.operational_start_time > 0:
            uptime = time.time() - self.operational_start_time
            if uptime < 60:  # 60s settle window
                logging.info("[IGNITION] Settle window active. Deferring idle check.")
                return True

        pid_file = os.path.join(LAB_DIR, "run/vllm.pid")
        if not os.path.exists(pid_file):
            return False

        try:
            with open(pid_file, "r") as f:
                vllm_pid = int(f.read().strip())
            
            if not psutil.pid_exists(vllm_pid):
                return False
                
            vllm_proc = psutil.Process(vllm_pid)
            conns = vllm_proc.connections(kind='tcp')
            
            # Look for established connections on local port 8088
            active_conns = [
                c for c in conns 
                if c.status == "ESTABLISHED" and c.laddr.port == 8088
            ]
            
            if not active_conns:
                logging.info("[IGNITION] Tier 1: Zero connections on port 8088. Engine is idle.")
                return False
                
            logging.info(f"[IGNITION] Tier 1: {len(active_conns)} connections detected on port 8088. Escalating to Tier 2...")
            
        except Exception as e:
            logging.warning(f"[IGNITION] Tier 1 check failed: {e}. Escalating to Tier 2.")

        # Tier 2: Check vLLM metrics
        import urllib.request
        try:
            url = "http://localhost:8088/metrics"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as response:
                content = response.read().decode('utf-8')
                
            num_running = 0.0
            num_waiting = 0.0
            
            for line in content.splitlines():
                if line.startswith("vllm:num_requests_running") or line.startswith("vllm_num_requests_running"):
                    parts = line.rsplit(" ", 1)
                    if len(parts) == 2:
                        num_running = float(parts[1])
                elif line.startswith("vllm:num_requests_waiting") or line.startswith("vllm_num_requests_waiting"):
                    parts = line.rsplit(" ", 1)
                    if len(parts) == 2:
                        num_waiting = float(parts[1])
            
            if num_running > 0 or num_waiting > 0:
                logging.info(f"[IGNITION] Tier 2: Active requests detected (running={num_running}, waiting={num_waiting}). Keeping awake.")
                return True
                
            logging.info("[IGNITION] Tier 2: No running or waiting requests in vLLM. Engine is idle.")
            return False
            
        except Exception as e:
            logging.warning(f"[IGNITION] Tier 2 metrics check failed: {e}. Assuming active to be safe.")
            return True

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
                foyer_clients = await self.get_foyer_clients()
                
                # Double standard timeout: 120s -> 240s
                # Extra 5 minutes (300s) if there is an active client connection
                effective_timeout = 240
                if foyer_clients > 0:
                    effective_timeout += 300

                if idle_time > effective_timeout and self.status.state == "OPERATIONAL":
                    if await self.is_engine_active():
                        # Reset idle timer because engine is active
                        self.last_activity_time = time.time()
                        logging.info(f"[IGNITION] Resetting idle timer (foyer_clients={foyer_clients}) due to active engine.")
                    else:
                        logging.info(f"[IGNITION] Idle timeout reached ({idle_time:.1f}s > {effective_timeout}s, foyer_clients={foyer_clients}). Hibernating...")
                        await self.stop_lab(reason="AFK_TIMEOUT")

                # 2. Daily Induction Window (02:00 - 04:00)
                disable_lock_path = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/disable_induction.lock"
                is_window = (2 <= now.hour < 4) and not os.path.exists(disable_lock_path)
                if is_window and self.last_induction_date != today:
                    # [FEAT-289] Atomic Induction: Mark today as started
                    self.last_induction_date = today
                    logging.info("[ALARM] Entering Daily Induction Window...")
                    self.record_pager("Daily Induction Window [OPEN]", source="Induction")
                    
                    # Try to acquire silicon mutex
                    if self._acquire_vram_lock():
                        try:
                            # [Task 1.2] Pre-Forge Dataset Refresh
                            logging.info("[ALARM] Step 0: Pre-Forge Dataset Refresh...")
                            self.record_pager("Step 0: Pre-Forge Dataset Refresh [START]", source="Induction")
                            
                            # Sequential dataset prep runs
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/forge/extract_gemini_prompts.py")], env=os.environ.copy())
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/forge/refine_prompts.py")], env=os.environ.copy())
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/forge/dream_voice.py")], env=os.environ.copy())
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/forge/build_lora_datasets.py")], env=os.environ.copy())
                            
                            # Step 1: Nightly Recruiter
                            logging.info("[ALARM] Step 1: Nightly Recruiter...")
                            self.record_pager("Step 1: Nightly Recruiter [START]", source="Induction")
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/acme_lab.py"), "--trigger-task", "recruiter"], env=os.environ.copy())
                            
                            # Step 2: Hierarchy Refactor
                            logging.info("[ALARM] Step 2: Hierarchy Refactor...")
                            self.record_pager("Step 2: Hierarchy Refactor [START]", source="Induction")
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/acme_lab.py"), "--trigger-task", "lab"], env=os.environ.copy())
                            
                            # Step 3: Sequenced Batch Forge
                            logging.info("[ALARM] Step 3: Sequenced Batch Forge...")
                            self.record_pager("Step 3: Sequenced Batch Forge [START]", source="Induction")
                            subprocess.run([sys.executable, os.path.join(LAB_DIR, "src/acme_lab.py"), "--trigger-task", "forge"], env=os.environ.copy())
                            
                            self.record_pager("Full Induction Cycle [COMPLETE]", source="Induction")
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
                            refiner = GEM_REFINER
                            if os.path.exists(refiner):
                                logging.info(f"[IGNITION] Running {refiner}...")
                                subprocess.run([sys.executable, refiner, "--one-turn"], env=os.environ.copy())
                            else:
                                logging.warning(f"[IGNITION] Refiner script not found at {refiner}")
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
        asyncio.create_task(self.journal_monitor())
        while True:
            # [FEAT-302] Stability Latch: Reset backoff if stable for >5m
            if self.status.state == "OPERATIONAL" and self.operational_start_time > 0:
                stable_dur = time.time() - self.operational_start_time
                if stable_dur > 300 and self.recovery_attempts > 0:
                    logging.info(f"[IGNITION] Silicon Stability Verified ({int(stable_dur)}s). Resetting recovery backoff.")
                    self.recovery_attempts = 0
            self.update_status_file()
            await asyncio.sleep(30)

if __name__ == "__main__":
    manager = IgnitionManager()
    asyncio.run(manager.main_loop())
