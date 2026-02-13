import asyncio
import datetime
import logging
import os
import subprocess
import sys

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
        self.app.router.add_get("/status", self.handle_status)
        self.app.router.add_post("/start", self.handle_start)
        self.app.router.add_post("/stop", self.handle_stop)
        self.app.router.add_post("/cleanup", self.handle_cleanup)
        self.app.router.add_post("/hard_reset", self.handle_hard_reset)
        self.app.router.add_get("/logs", self.handle_logs)

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

    async def cleanup_silicon(self):
        """Sweep all related processes and zero out VRAM."""
        logger.warning("[SWEEP] Purging all Lab-related processes...")
        targets = ["vllm", "ollama", "acme_lab.py", "archive_node.py"]
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                line = " ".join(proc.info['cmdline'] or [])
                if any(t in line for t in targets):
                    logger.info(f"[KILL] Terminating {proc.info['pid']} ({line[:50]})")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        global lab_process, vllm_process
        lab_process = None
        vllm_process = None

        if os.path.exists(ROUND_TABLE_LOCK):
            os.remove(ROUND_TABLE_LOCK)

        await asyncio.sleep(2)

    async def handle_status(self, request):
        lock_active = os.path.exists(ROUND_TABLE_LOCK)
        status = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "vllm_running": False,
            "lab_mode": current_lab_mode,
            "round_table_lock_exists": lock_active,
            "full_lab_ready": False,
            "last_error": None
        }

        # Check vLLM Port
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8088/v1/models", timeout=0.5) as r:
                    if r.status == 200: status["vllm_running"] = True
        except: pass

        global lab_process
        if lab_process and lab_process.poll() is None:
            status["lab_server_running"] = True
            if os.path.exists(SERVER_LOG):
                try:
                    with open(SERVER_LOG, 'r') as f:
                        content = f.read()
                        if "[READY] Lab is Open" in content:
                            status["full_lab_ready"] = True
                        if "[FATAL]" in content:
                            status["last_error"] = content.split("[FATAL]")[-1].strip().split("\n")[0]
                except: pass

        return web.json_response(status)

    async def handle_start(self, request):
        global lab_process, vllm_process, current_lab_mode
        data = await request.json()
        preferred_engine = data.get("engine", "OLLAMA")

        # 1. Kill old Hub
        if lab_process and lab_process.poll() is None:
            lab_process.kill()

        # 2. Handle vLLM specifically
        if preferred_engine == "vLLM":
            logger.info("[VRAM] Ensuring vLLM is active...")
            # We use the shell script but track it
            subprocess.run(["bash", VLLM_START_PATH])
            await asyncio.sleep(10) # Initial weight burst

        # 3. Launch Hub
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
        env["USE_BRAIN_VLLM"] = "1" if preferred_engine == "vLLM" else "0"
        if data.get("disable_ear", True): env["DISABLE_EAR"] = "1"

        with open(SERVER_LOG, 'w') as f: f.write('')

        try:
            lab_process = subprocess.Popen(
                [LAB_VENV_PYTHON, LAB_SERVER_PATH, "--mode", data.get("mode", "SERVICE_UNATTENDED")],
                cwd=LAB_DIR, env=env,
                stderr=open(SERVER_LOG, 'a', buffering=1)
            )
            return web.json_response({"status": "success", "pid": lab_process.pid})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_stop(self, request):
        await self.cleanup_silicon()
        return web.json_response({"status": "success"})

    async def handle_cleanup(self, request):
        """Archives server logs and clears stale locks."""
        if os.path.exists(SERVER_LOG):
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            os.rename(SERVER_LOG, f"{SERVER_LOG}.{ts}")
        if os.path.exists(ROUND_TABLE_LOCK):
            os.remove(ROUND_TABLE_LOCK)
        return web.json_response({"status": "success", "message": "Cleanup complete."})

    async def handle_hard_reset(self, request):
        await self.cleanup_silicon()
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
