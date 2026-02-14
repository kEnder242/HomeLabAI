import asyncio
import datetime
import json
import logging
import os
import subprocess
import sys
import time

import aiohttp
import psutil
from aiohttp import web

# --- Configuration ---
LAB_PORT = 8765
ATTENDANT_PORT = 9999
LAB_SERVER_PATH = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/acme_lab.py")
VLLM_START_PATH = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/start_vllm.sh")
LAB_DIR = os.path.dirname(os.path.dirname(LAB_SERVER_PATH))
LAB_VENV_PYTHON = os.path.join(LAB_DIR, ".venv", "bin", "python3")
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
VLLM_LOG = os.path.join(LAB_DIR, "vllm_server.log")
ROUND_TABLE_LOCK = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/round_table.lock"
)

# --- Logger Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ATTENDANT] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# --- Global State ---
lab_process: subprocess.Popen = None
vllm_process: subprocess.Popen = None
current_lab_mode: str = "OFFLINE"


class LabAttendant:
    def __init__(self):
        self.app = web.Application()
        self.app.router.add_get("/status", self.handle_blocking_status)
        self.app.router.add_post("/start", self.handle_start)
        self.app.router.add_post("/stop", self.handle_stop)
        self.app.router.add_post("/cleanup", self.handle_cleanup)
        self.app.router.add_post("/hard_reset", self.handle_hard_reset)
        self.app.router.add_get("/wait_ready", self.handle_wait_ready)
        self.app.router.add_get("/heartbeat", self.handle_heartbeat)
        self.app.router.add_get("/logs", self.handle_logs)
        self.ready_event = asyncio.Event()
        self.monitor_task = None

    async def _get_vram_info(self):
        try:
            cmd = [
                "nvidia-smi", "--query-gpu=memory.used,memory.total",
                "--format=csv,nounits,noheader"
            ]
            output = subprocess.check_output(cmd).decode().strip()
            used, total = map(int, output.split(','))
            return used, total
        except Exception:
            return 0, 0

    async def _get_current_vitals(self):
        """Internal helper to aggregate Lab state."""
        lock_active = os.path.exists(ROUND_TABLE_LOCK)
        vitals = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "vllm_running": False,
            "lab_mode": current_lab_mode,
            "round_table_lock_exists": lock_active,
            "full_lab_ready": self.ready_event.is_set(),
            "last_error": None
        }

        # Check vLLM Port
        try:
            async with aiohttp.ClientSession() as session:
                url = "http://localhost:8088/v1/models"
                async with session.get(url, timeout=0.5) as r:
                    if r.status == 200:
                        vitals["vllm_running"] = True
        except Exception:
            pass

        global lab_process
        if lab_process and lab_process.poll() is None:
            vitals["lab_server_running"] = True
            # Final check for readiness if not already set
            if not vitals["full_lab_ready"]:
                if os.path.exists(SERVER_LOG):
                    with open(SERVER_LOG, 'r') as f:
                        if "[READY] Lab is Open" in f.read():
                            vitals["full_lab_ready"] = True
                            self.ready_event.set()
        elif lab_process and lab_process.poll() is not None:
            vitals["last_error"] = f"Process died: {lab_process.poll()}"

        return vitals

    async def cleanup_silicon(self):
        """Sweep all related processes and zero out VRAM."""
        logger.warning("[SWEEP] Purging all Lab-related processes...")
        if self.monitor_task:
            self.monitor_task.cancel()

        targets = ["vllm", "ollama", "acme_lab.py", "archive_node.py"]
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                line = " ".join(proc.info['cmdline'] or [])
                if any(t in line for t in targets):
                    logger.info(
                        f"[KILL] Terminating {proc.info['pid']} ({line[:50]})"
                    )
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        global lab_process, vllm_process
        lab_process = None
        vllm_process = None

        if os.path.exists(ROUND_TABLE_LOCK):
            os.remove(ROUND_TABLE_LOCK)

        await asyncio.sleep(2)

    async def log_monitor_loop(self):
        """Tails the log and triggers ready_event on [READY]."""
        logger.info("[MONITOR] Starting log monitor...")
        self.ready_event.clear()
        
        while True:
            if os.path.exists(SERVER_LOG):
                try:
                    with open(SERVER_LOG, 'r') as f:
                        f.seek(0, 2)
                        while True:
                            line = f.readline()
                            if not line:
                                await asyncio.sleep(0.5)
                                if not lab_process or lab_process.poll() is not None:
                                    break
                                continue
                            
                            if "[READY] Lab is Open" in line:
                                logger.info("[MONITOR] Signal Detected: READY")
                                self.ready_event.set()
                                # Update public status.json once READY
                                await self.update_status_json()
                                return
                            if "[FATAL]" in line:
                                logger.error("[MONITOR] Signal Detected: FATAL")
                                return
                except Exception as e:
                    logger.error(f"[MONITOR] Error: {e}")
            await asyncio.sleep(1)

    async def update_status_json(self):
        """Updates the shared status.json for the dashboard."""
        vitals = await self._get_current_vitals()
        try:
            v_used, v_total = await self._get_vram_info()
            v_pct = (v_used / v_total * 100) if v_total > 0 else 0
            live_data = {
                "status": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
                "message": "Mind is " + ("READY" if vitals["full_lab_ready"] else "BOOTING"),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "vitals": {
                    "brain": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
                    "intercom": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
                    "vram": f"{v_pct:.1f}%"
                }
            }
            s_json = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/status.json"
            with open(s_json, "w") as f:
                json.dump(live_data, f)
        except Exception:
            pass

    async def handle_blocking_status(self, request):
        """
        Reactive Status: Blocks until timeout OR process death.
        Mandatory: ?timeout=N (seconds)
        """
        timeout_str = request.query.get("timeout")
        if timeout_str is None:
            return web.json_response(
                {"error": "Mandatory 'timeout' parameter missing."},
                status=400
            )

        timeout = int(timeout_str)
        start_t = time.time()

        while time.time() - start_t < timeout:
            vitals = await self._get_current_vitals()

            # --- REACTIVE LOGIC: Return if we have a definitive state ---
            # 1. If DEAD or CRASHED -> Return Fail-Fast
            if not vitals["lab_server_running"] or vitals["last_error"]:
                return web.json_response(vitals)

            # 2. If READY -> Return Success-Fast
            if vitals["full_lab_ready"]:
                return web.json_response(vitals)

            await asyncio.sleep(1)  # Block while BOOTING

        # If we reached here, the mind was healthy for the full duration
        vitals = await self._get_current_vitals()
        return web.json_response(vitals)

    async def handle_start(self, request):
        global lab_process, vllm_process, current_lab_mode
        data = await request.json()
        preferred_engine = data.get("engine", "OLLAMA")

        await self.cleanup_silicon()

        if preferred_engine == "vLLM":
            logger.info("[VRAM] Ensuring vLLM is active...")
            subprocess.run(["bash", VLLM_START_PATH])
            await asyncio.sleep(10)

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
        env["USE_BRAIN_VLLM"] = "1" if preferred_engine == "vLLM" else "0"
        if data.get("disable_ear", True):
            env["DISABLE_EAR"] = "1"

        with open(SERVER_LOG, 'w') as f:
            f.write('')

        try:
            lab_process = subprocess.Popen(
                [
                    LAB_VENV_PYTHON, LAB_SERVER_PATH,
                    "--mode", data.get("mode", "SERVICE_UNATTENDED")
                ],
                cwd=LAB_DIR, env=env,
                stderr=open(SERVER_LOG, 'a', buffering=1)
            )
            current_lab_mode = data.get("mode", "SERVICE_UNATTENDED")
            self.monitor_task = asyncio.create_task(self.log_monitor_loop())
            return web.json_response({"status": "success", "pid": lab_process.pid})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_wait_ready(self, request):
        """Blocks until the Lab is READY. Returns full vitals on success."""
        timeout = int(request.query.get("timeout", 60))
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
            vitals = await self._get_current_vitals()
            return web.json_response({"status": "ready", "vitals": vitals})
        except asyncio.TimeoutError:
            vitals = await self._get_current_vitals()
            return web.json_response({"status": "timeout", "vitals": vitals}, status=408)

    async def handle_heartbeat(self, request):
        """Fast liveliness check for soak phases."""
        vitals = await self._get_current_vitals()
        # Periodically update status.json during soaks
        await self.update_status_json()
        return web.json_response(vitals)

    async def handle_stop(self, request):
        await self.cleanup_silicon()
        await self.update_status_json()
        return web.json_response({"status": "success"})

    async def handle_cleanup(self, request):
        if os.path.exists(SERVER_LOG):
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            os.rename(SERVER_LOG, f"{SERVER_LOG}.{ts}")
        return web.json_response({"status": "success"})

    async def handle_hard_reset(self, request):
        await self.cleanup_silicon()
        await self.update_status_json()
        return web.json_response({"status": "success"})

    async def handle_logs(self, request):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, 'r') as f:
                return web.Response(text=f.read()[-5000:], content_type='text/plain')
        return web.json_response({"status": "not_found"}, status=404)

    async def run(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', ATTENDANT_PORT).start()
        logger.info(f"[BOOT] Attendant online on {ATTENDANT_PORT}")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(LabAttendant().run())
