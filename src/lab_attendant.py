import asyncio
import aiohttp
from aiohttp import web
import json
import logging
import os
import subprocess
import signal
import psutil # For graceful process management
import sys 
import argparse
import datetime

# --- Configuration ---
LAB_PORT = 8765
ATTENDANT_PORT = 9999
LAB_SERVER_PATH = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/acme_lab.py")
LAB_DIR = os.path.dirname(os.path.dirname(LAB_SERVER_PATH))
LAB_VENV_PYTHON = os.path.join(LAB_DIR, ".venv", "bin", "python3")
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
ROUND_TABLE_LOCK = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/round_table.lock")

# --- Logger Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ATTENDANT] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# --- Global State ---
lab_process: subprocess.Popen = None
current_lab_mode: str = "OFFLINE"
last_logged_lab_pid: int = None
last_logged_lab_ready_state: bool = False
last_logged_lab_status_message: str = ""

class LabAttendant:
    def __init__(self):
        self.app = web.Application()
        self.app.router.add_get("/status", self.handle_status)
        self.app.router.add_post("/start", self.handle_start)
        self.app.router.add_post("/stop", self.handle_stop)
        self.app.router.add_post("/cleanup", self.handle_cleanup)
        self.app.router.add_get("/logs", self.handle_logs)

    async def _get_vram_info(self):
        """Queries Prometheus (DCGM) for memory stats with nvidia-smi fallback."""
        try:
            prom_url = "http://localhost:9090/api/v1/query"
            async with aiohttp.ClientSession() as session:
                async with session.get(prom_url, params={"query": "DCGM_FI_DEV_FB_USED"}, timeout=1) as r1:
                    async with session.get(prom_url, params={"query": "DCGM_FI_DEV_FB_FREE"}, timeout=1) as r2:
                        d1 = await r1.json()
                        d2 = await r2.json()
                        used = float(d1['data']['result'][0]['value'][1])
                        free = float(d2['data']['result'][0]['value'][1])
                        return int(used), int(used + free)
        except:
            try:
                cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"]
                output = subprocess.check_output(cmd).decode().strip()
                used, total = map(int, output.split(','))
                return used, total
            except:
                return 0, 0

    async def select_optimal_engine(self, preferred="OLLAMA"):
        """Determines best engine based on VRAM budget."""
        used, total = await self._get_vram_info()
        available = total - used
        VLLM_MIN_HEADROOM = 6000
        OLLAMA_MIN_HEADROOM = 2000
        
        if preferred == "vLLM" and available > VLLM_MIN_HEADROOM:
            return "vLLM", available
        elif available > OLLAMA_MIN_HEADROOM:
            return "OLLAMA", available
        else:
            return "STUB", available

    async def invalidate_resident_models(self):
        """Force-releases VRAM by terminating inference engines."""
        global lab_process
        if lab_process and lab_process.poll() is None:
            pid = lab_process.pid
            logger.warning(f"[RESOURCES] VRAM Pressure. Invalidating PID {pid}...")
            try:
                parent = psutil.Process(pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                _, alive = psutil.wait_procs([parent], timeout=3)
                for p in alive: p.kill()
            except Exception as e:
                logger.error(f"Invalidation failed for {pid}: {e}")
            
            lab_process = None
            return True
        return False

    async def handle_status(self, request):
        status = await self._get_lab_status()
        global last_logged_lab_pid, last_logged_lab_ready_state, last_logged_lab_status_message
        
        if status["lab_pid"] != last_logged_lab_pid:
            last_logged_lab_pid = status["lab_pid"]
        if status["full_lab_ready"] != last_logged_lab_ready_state:
            last_logged_lab_ready_state = status["full_lab_ready"]
        
        return web.json_response(status)

    async def handle_start(self, request):
        global lab_process, current_lab_mode, last_logged_lab_pid, last_logged_lab_ready_state, last_logged_lab_status_message
        
        data = await request.json()
        mode = data.get("mode", "SERVICE_UNATTENDED")
        preferred_engine = data.get("engine", "OLLAMA")

        # 1. Transition Logic: If something is running, we MUST invalidate it to start fresh
        if lab_process and lab_process.poll() is None:
            logger.info(f"[TRANSITION] Invalidation triggered by new start request. Killing PID {lab_process.pid}...")
            await self.invalidate_resident_models()

        # 2. VRAM Guard: Select best engine after invalidation
        engine, avail = await self.select_optimal_engine(preferred_engine)
        logger.info(f"[VRAM GUARD] Available: {avail}MiB | Selected: {engine} (Preferred: {preferred_engine})")

        # 3. Setup Environment
        process_env = os.environ.copy()
        process_env.update(data.get("env", {}))
        process_env["PYTHONPATH"] = f"{process_env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
        process_env["PYTHONUNBUFFERED"] = "1"
        process_env["USE_BRAIN_VLLM"] = "1" if engine == "vLLM" else "0"
        process_env["USE_BRAIN_STUB"] = "1" if engine == "STUB" else "0"

        if data.get("disable_ear", True): process_env["DISABLE_EAR"] = "1"
        else: process_env.pop("DISABLE_EAR", None)
        
        logger.info(f"Starting Lab server: Mode={mode}, Engine={engine}")

        with open(SERVER_LOG, 'w') as f: f.write('')

        try:
            lab_process = subprocess.Popen(
                [LAB_VENV_PYTHON, LAB_SERVER_PATH, "--mode", mode],
                cwd=LAB_DIR, env=process_env,
                stdout=subprocess.DEVNULL,
                stderr=open(SERVER_LOG, 'a', buffering=1)
            )
            current_lab_mode = mode
            last_logged_lab_pid = lab_process.pid
            last_logged_lab_ready_state = False
            last_logged_lab_status_message = ""
            return web.json_response({"status": "success", "message": "Lab server started.", "pid": lab_process.pid})
        except Exception as e:
            logger.error(f"Failed to start Lab server: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_stop(self, request):
        global lab_process, current_lab_mode
        if lab_process and lab_process.poll() is None:
            await self.invalidate_resident_models()
            current_lab_mode = "OFFLINE"
            return web.json_response({"status": "success", "message": "Lab server stopped."})
        return web.json_response({"status": "info", "message": "Lab server not running."})

    async def handle_cleanup(self, request):
        if lab_process and lab_process.poll() is None:
            return web.json_response({"status": "error", "message": "Cannot cleanup while Lab server is running."}, status=400)
        if os.path.exists(SERVER_LOG):
            os.rename(SERVER_LOG, f"{SERVER_LOG}.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if os.path.exists(ROUND_TABLE_LOCK): os.remove(ROUND_TABLE_LOCK)
        return web.json_response({"status": "success", "message": "Cleanup complete."})

    async def handle_logs(self, request):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, 'r') as f: return web.Response(text=f.read(), content_type='text/plain')
        return web.json_response({"status": "info", "message": "server.log not found."}, status=404)

    async def _get_lab_status(self):
        lock_active = os.path.exists(ROUND_TABLE_LOCK)
        status = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "lab_pid": None,
            "lab_mode": current_lab_mode,
            "round_table_lock_exists": lock_active,
            "state_label": "THINKING" if lock_active else "IDLE",
            "last_log_lines": [],
            "vram_usage": "UNKNOWN",
            "full_lab_ready": False 
        }
        if lab_process and lab_process.poll() is None:
            status["lab_server_running"] = True
            status["lab_pid"] = lab_process.pid
            try:
                if os.path.exists(SERVER_LOG):
                    with open(SERVER_LOG, 'r') as f:
                        lines = f.readlines()
                        status["last_log_lines"] = [line.strip() for line in lines[-10:]]
                        if any("[READY] Lab is Open" in line for line in lines):
                            status["full_lab_ready"] = True
            except: pass
            try:
                output = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).decode().strip()
                status["vram_usage"] = f"{output}MiB"
            except: pass
        return status

    async def run(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', ATTENDANT_PORT).start()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(LabAttendant().run())
