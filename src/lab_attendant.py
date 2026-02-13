import argparse
import asyncio
import datetime
import json
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
LAB_DIR = os.path.dirname(os.path.dirname(LAB_SERVER_PATH))
LAB_VENV_PYTHON = os.path.join(LAB_DIR, ".venv", "bin", "python3")
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
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
        """Queries nvidia-smi for current VRAM usage."""
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
        """Sweep all related processes and zero out VRAM as much as possible."""
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
        
        if os.path.exists(ROUND_TABLE_LOCK):
            os.remove(ROUND_TABLE_LOCK)
        
        await asyncio.sleep(2) # Let VRAM settle

    async def select_optimal_engine(self, preferred="OLLAMA"):
        """Determines best engine based on VRAM budget."""
        used, total = await self._get_vram_info()
        available = total - used
        # We need ~1.5GB for EarNode + Overheads
        VLLM_MIN_HEADROOM = 7000 
        OLLAMA_MIN_HEADROOM = 3000

        if preferred == "vLLM" and available > VLLM_MIN_HEADROOM:
            return "vLLM", available
        elif available > OLLAMA_MIN_HEADROOM:
            return "OLLAMA", available
        else:
            return "STUB", available

    async def handle_status(self, request):
        lock_active = os.path.exists(ROUND_TABLE_LOCK)
        status = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "lab_pid": None,
            "lab_mode": current_lab_mode,
            "round_table_lock_exists": lock_active,
            "full_lab_ready": False,
            "last_error": None
        }

        global lab_process
        if lab_process:
            poll = lab_process.poll()
            if poll is None:
                status["lab_server_running"] = True
                status["lab_pid"] = lab_process.pid
                # Check log for READY or FATAL
                if os.path.exists(SERVER_LOG):
                    try:
                        with open(SERVER_LOG, 'r') as f:
                            content = f.read()
                            if "[READY] Lab is Open" in content:
                                status["full_lab_ready"] = True
                            if "[FATAL]" in content:
                                # Extract fatal error
                                lines = content.split("\n")
                                for line in reversed(lines):
                                    if "[FATAL]" in line:
                                        status["last_error"] = line
                                        break
                    except Exception: pass
            else:
                status["last_error"] = f"Process terminated with exit code {poll}"
                lab_process = None

        return web.json_response(status)

    async def handle_start(self, request):
        global lab_process, current_lab_mode
        data = await request.json()
        mode = data.get("mode", "SERVICE_UNATTENDED")
        preferred_engine = data.get("engine", "OLLAMA")

        # 1. Automatic Cleanup if already running
        if lab_process and lab_process.poll() is None:
            await self.cleanup_silicon()

        # 2. VRAM Check
        engine, avail = await self.select_optimal_engine(preferred_engine)
        logger.info(f"[VRAM] Available: {avail}MiB | Selected: {engine}")

        # 3. Launch
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
        env["USE_BRAIN_VLLM"] = "1" if engine == "vLLM" else "0"
        env["USE_BRAIN_STUB"] = "1" if engine == "STUB" else "0"
        if data.get("disable_ear", True): env["DISABLE_EAR"] = "1"

        with open(SERVER_LOG, 'w') as f: f.write('')

        try:
            lab_process = subprocess.Popen(
                [LAB_VENV_PYTHON, LAB_SERVER_PATH, "--mode", mode],
                cwd=LAB_DIR, env=env,
                stderr=open(SERVER_LOG, 'a', buffering=1)
            )
            current_lab_mode = mode
            return web.json_response({"status": "success", "pid": lab_process.pid})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_stop(self, request):
        await self.cleanup_silicon()
        return web.json_response({"status": "success"})

    async def handle_cleanup(self, request):
        if os.path.exists(SERVER_LOG):
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            os.rename(SERVER_LOG, f"{SERVER_LOG}.{ts}")
        return web.json_response({"status": "success"})

    async def handle_hard_reset(self, request):
        """Total scorched earth reset."""
        await self.cleanup_silicon()
        return web.json_response({"status": "success", "message": "Silicon zeroed."})

    async def handle_logs(self, request):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, 'r') as f:
                return web.Response(text=f.read()[-10000:], content_type='text/plain')
        return web.json_response({"status": "not_found"}, status=404)

    async def run(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', ATTENDANT_PORT).start()
        logger.info(f"[BOOT] Attendant online on {ATTENDANT_PORT}")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(LabAttendant().run())
