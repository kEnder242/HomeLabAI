import os
import subprocess
import signal
import json
import asyncio
import datetime
import logging
import psutil
import aiohttp
from aiohttp import web
import time

# --- Configuration ---
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
SERVER_LOG = f"{LAB_DIR}/server.log"
SERVER_PID_FILE = f"{LAB_DIR}/server.pid"
STATUS_JSON = f"{PORTFOLIO_DIR}/field_notes/data/status.json"
CHARACTERIZATION_FILE = f"{PORTFOLIO_DIR}/field_notes/data/vram_characterization.json"
ROUND_TABLE_LOCK = f"{LAB_DIR}/round_table.lock"
VLLM_START_PATH = f"{LAB_DIR}/src/start_vllm.sh"
LAB_SERVER_PATH = f"{LAB_DIR}/src/acme_lab.py"
LAB_VENV_PYTHON = f"{LAB_DIR}/.venv/bin/python3"
ATTENDANT_PORT = 9999

# --- Global State ---
lab_process = None
vllm_process = None
current_lab_mode = "OFFLINE"
current_model = None

# --- Logger ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ATTENDANT] %(levelname)s - %(message)s')
logger = logging.getLogger("lab_attendant")

class LabAttendant:
    def __init__(self):
        self.app = web.Application()
        self.app.router.add_post("/start", self.handle_start)
        self.app.router.add_post("/stop", self.handle_stop)
        self.app.router.add_post("/cleanup", self.handle_cleanup)
        self.app.router.add_post("/hard_reset", self.handle_hard_reset)
        self.app.router.add_post("/refresh", self.handle_refresh)
        self.app.router.add_get("/wait_ready", self.handle_wait_ready)
        self.app.router.add_get("/heartbeat", self.handle_heartbeat)
        self.app.router.add_get("/logs", self.handle_logs)
        self.app.router.add_get("/blocking_status", self.handle_blocking_status)
        self.ready_event = asyncio.Event()
        self.monitor_task = None
        self.vram_config = {}
        self.refresh_vram_config()

    def refresh_vram_config(self):
        """Loads dynamic thresholds and model mappings from characterization file."""
        if os.path.exists(CHARACTERIZATION_FILE):
            try:
                with open(CHARACTERIZATION_FILE, 'r') as f:
                    self.vram_config = json.load(f)
                logger.info("[VRAM] Config and Model Map refreshed from disk.")
            except Exception as e:
                logger.error(f"[VRAM] Failed to load config: {e}")

    async def vram_watchdog_loop(self):
        """SIGTERM & Engine Tiering: Manage engine lifecycle based on hardware pressure."""
        logger.info("[VRAM] Watchdog active and polling.")
        try:
            while True:
                await asyncio.sleep(2)
                used, total = await self._get_vram_info()
                
                # Consult dynamic thresholds
                safe_tiers = self.vram_config.get("safe_tiers", {})
                warn_limit = safe_tiers.get("warning", total * 0.85)
                down_limit = safe_tiers.get("downshift", total * 0.90) 
                crit_limit = safe_tiers.get("critical", total * 0.95)
                
                logger.info(f"[VRAM] Used: {used} MiB | Limits: Warn={warn_limit}, Down={down_limit}, Crit={crit_limit} | Mode: {current_lab_mode}")
                
                model_map = self.vram_config.get("model_map", {})
                small_model = model_map.get("SMALL", {}).get("ollama")
                medium_model = model_map.get("MEDIUM", {}).get("ollama")

                # 1. CRITICAL: Graceful Suspension (Tier 4)
                if used > crit_limit:
                    logger.warning(f"[VRAM] Critical Pressure: {used}/{total} MiB. Triggering Suspension.")
                    await self.cleanup_silicon()
                    await self.update_status_json("Mind SUSPENDED (Critical VRAM)")
                    continue

                # 2. DOWNSHIFT: Model Swap (MEDIUM -> SMALL)
                if used > down_limit and current_lab_mode == "OLLAMA" and current_model != small_model:
                    logger.warning(f"[VRAM] Downshift Pressure: {used}/{total} MiB. Triggering Tier 3 Downshift.")
                    asyncio.create_task(self.handle_downshift(small_model))
                    continue

                # 3. ENGINE SWAP: (vLLM -> Ollama MEDIUM)
                if used > warn_limit and current_lab_mode == "vLLM":
                    logger.warning(f"[VRAM] Warning Pressure: {used}/{total} MiB. Triggering Engine Swap.")
                    asyncio.create_task(self.handle_engine_swap(medium_model))
                    continue
        except Exception as e:
            logger.error(f"[VRAM] Watchdog CRASHED: {e}")

    async def handle_engine_swap(self, target_model):
        """Hot-swaps vLLM for Ollama fallback."""
        global current_lab_mode
        logger.info(f"[SWAP] Initiating engine swap to Ollama ({target_model})...")
        current_lab_mode = "SWAPPING"
        await self.cleanup_silicon()
        
        swap_payload = {
            "engine": "OLLAMA",
            "model": target_model,
            "mode": "SERVICE_UNATTENDED",
            "disable_ear": True
        }
        class MockRequest:
            async def json(self): return swap_payload
        await self.handle_start(MockRequest())
        await self.update_status_json("Mind SWAPPED (VRAM Warning)")

    async def handle_downshift(self, target_model):
        """Hot-swaps Ollama models to survive extreme pressure."""
        global current_lab_mode, current_model
        logger.info(f"[DOWNSHIFT] Initiating model downshift to {target_model}...")
        current_lab_mode = "DOWNSHIFTING"
        await self.cleanup_silicon()
        
        down_payload = {
            "engine": "OLLAMA",
            "model": target_model,
            "mode": "SERVICE_UNATTENDED",
            "disable_ear": True
        }
        class MockRequest:
            async def json(self): return down_payload
        await self.handle_start(MockRequest())
        current_model = target_model
        await self.update_status_json("Mind DOWNSHIFTED (Tier 3)")

    async def log_monitor_loop(self):
        """Persistent watch for READY signal."""
        logger.info("[MONITOR] Starting log monitor...")
        self.ready_event.clear()
        while True:
            if os.path.exists(SERVER_LOG):
                try:
                    with open(SERVER_LOG, 'r') as f:
                        # Move to the end initially if needed, but here we want to see new entries
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
                                await self.update_status_json()
                                return
                            if "[FATAL]" in line:
                                logger.error("[MONITOR] Signal Detected: FATAL")
                                return
                except Exception as e:
                    logger.error(f"[MONITOR] Error: {e}")
            await asyncio.sleep(1)

    async def handle_start(self, request):
        global lab_process, vllm_process, current_lab_mode, current_model
        data = await request.json()
        preferred_engine = data.get("engine", "OLLAMA")
        tier_or_model = data.get("model") 

        model_map = self.vram_config.get("model_map", {})
        if tier_or_model in model_map:
            resolved_model = model_map[tier_or_model].get(preferred_engine.lower())
        else:
            resolved_model = tier_or_model

        current_lab_mode = preferred_engine 
        
        # Determine actual model for state tracking (Default to MEDIUM if not specified)
        if not resolved_model:
            resolved_model = model_map.get("MEDIUM", {}).get(preferred_engine.lower())
            
        current_model = resolved_model

        await self.cleanup_silicon()

        if preferred_engine == "vLLM":
            logger.info(f"[VRAM] Ensuring vLLM is active with model {current_model}...")
            subprocess.run(["bash", VLLM_START_PATH, current_model])
            await asyncio.sleep(10)

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
        env["USE_BRAIN_VLLM"] = "1" if preferred_engine == "vLLM" else "0"
        env["BRAIN_MODEL"] = current_model
        env["PINKY_MODEL"] = current_model
        env["ARCHIVE_MODEL"] = current_model
        env["ARCHITECT_MODEL"] = current_model
            
        if data.get("disable_ear", True):
            env["DISABLE_EAR"] = "1"

        with open(SERVER_LOG, 'w') as f:
            f.write('')

        try:
            lab_process = subprocess.Popen(
                [
                    LAB_VENV_PYTHON, LAB_SERVER_PATH,
                    "--mode", data.get("mode", "SERVICE_UNATTENDED"),
                    "--afk-timeout", str(data.get("afk_timeout", 300))
                ],
                cwd=LAB_DIR, env=env,
                stderr=open(SERVER_LOG, 'a', buffering=1)
            )
            logger.info(f"[START] Lab process {lab_process.pid} launched in {current_lab_mode} mode ({current_model}).")
            self.monitor_task = asyncio.create_task(self.log_monitor_loop())
            return web.json_response({"status": "success", "pid": lab_process.pid})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

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

    async def handle_refresh(self, request):
        self.refresh_vram_config()
        return web.json_response({"status": "success", "message": "VRAM Configuration reloaded."})

    async def handle_wait_ready(self, request):
        timeout = int(request.query.get("timeout", 60))
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
            vitals = await self._get_current_vitals()
            return web.json_response({"status": "ready", "vitals": vitals})
        except asyncio.TimeoutError:
            vitals = await self._get_current_vitals()
            return web.json_response({"status": "timeout", "vitals": vitals}, status=408)

    async def handle_heartbeat(self, request):
        vitals = await self._get_current_vitals()
        await self.update_status_json()
        return web.json_response(vitals)

    async def handle_logs(self, request):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, 'r') as f:
                return web.Response(text=f.read()[-5000:], content_type='text/plain')
        return web.json_response({"status": "not_found"}, status=404)

    async def handle_blocking_status(self, request):
        timeout_str = request.query.get("timeout")
        if timeout_str is None:
            return web.json_response({"error": "Mandatory 'timeout' parameter missing."}, status=400)
        timeout = int(timeout_str)
        start_t = time.time()
        while time.time() - start_t < timeout:
            vitals = await self._get_current_vitals()
            if not vitals["lab_server_running"] or vitals["last_error"] or vitals["full_lab_ready"]:
                return web.json_response(vitals)
            await asyncio.sleep(1)
        vitals = await self._get_current_vitals()
        return web.json_response(vitals)

    async def _get_vram_info(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            used = info.used // 1024 // 1024
            total = info.total // 1024 // 1024
            pynvml.nvmlShutdown()
            return used, total
        except Exception:
            return 0, 0

    async def _get_current_vitals(self):
        vitals = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "vllm_running": False,
            "lab_mode": current_lab_mode,
            "model": current_model,
            "full_lab_ready": self.ready_event.is_set(),
            "last_error": None
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8088/v1/models", timeout=0.5) as r:
                    if r.status == 200: vitals["vllm_running"] = True
        except Exception: pass
        global lab_process
        if lab_process and lab_process.poll() is None:
            vitals["lab_server_running"] = True
        elif lab_process and lab_process.poll() is not None:
            vitals["last_error"] = f"Process died: {lab_process.poll()}"
        return vitals

    async def update_status_json(self, custom_message=None):
        vitals = await self._get_current_vitals()
        try:
            v_used, v_total = await self._get_vram_info()
            v_pct = (v_used / v_total * 100) if v_total > 0 else 0
            msg = custom_message if custom_message else ("Mind is " + ("READY" if vitals["full_lab_ready"] else "BOOTING"))
            live_data = {
                "status": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
                "message": msg,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "vitals": {
                    "brain": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
                    "vram": f"{v_pct:.1f}%",
                    "model": current_model,
                    "mode": current_lab_mode
                }
            }
            with open(STATUS_JSON, "w") as f:
                json.dump(live_data, f)
        except Exception: pass

    async def cleanup_silicon(self):
        targets = ["vllm", "ollama", "acme_lab.py", "archive_node.py"]
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                line = " ".join(proc.info['cmdline'] or [])
                if any(t in line for t in targets):
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass

    async def run(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', ATTENDANT_PORT).start()
        logger.info(f"[BOOT] Attendant online on {ATTENDANT_PORT}")
        asyncio.create_task(self.vram_watchdog_loop())
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(LabAttendant().run())
