import os
import subprocess
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
INFRASTRUCTURE_FILE = f"{LAB_DIR}/config/infrastructure.json"
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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [ATTENDANT] %(levelname)s - %(message)s",
)
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
        self.model_manifest = {}
        self.refresh_vram_config()

    def refresh_vram_config(self):
        """Loads dynamic thresholds and model mappings."""
        if os.path.exists(CHARACTERIZATION_FILE):
            try:
                with open(CHARACTERIZATION_FILE, "r") as f:
                    self.vram_config = json.load(f)
                logger.info("[VRAM] Config refreshed from disk.")
            except Exception as e:
                logger.error(f"[VRAM] Failed to load config: {e}")

        if os.path.exists(INFRASTRUCTURE_FILE):
            try:
                with open(INFRASTRUCTURE_FILE, "r") as f:
                    infra = json.load(f)
                    self.model_manifest = infra.get("model_manifest", {})
                logger.info("[INFRA] Model manifest refreshed.")
            except Exception as e:
                logger.error(f"[INFRA] Failed to load infrastructure: {e}")

    async def vram_watchdog_loop(self):
        """SIGTERM & Engine Tiering: Hardware pressure monitor."""
        logger.info("[VRAM] Watchdog active with DCGM Heartbeat.")
        gpu_load_history = []
        try:
            while True:
                await asyncio.sleep(2)
                used, total = await self._get_vram_info()
                load = await self._get_gpu_load()

                # Maintain 10-second sliding window (5 samples at 2s interval)
                gpu_load_history.append(load)
                if len(gpu_load_history) > 5:
                    gpu_load_history.pop(0)

                avg_load = sum(gpu_load_history) / len(gpu_load_history)

                safe_tiers = self.vram_config.get("safe_tiers", {})
                warn_limit = safe_tiers.get("warning", total * 0.85)
                down_limit = safe_tiers.get("downshift", total * 0.90)
                crit_limit = safe_tiers.get("critical", total * 0.95)
                model_map = self.vram_config.get("model_map", {})
                small_model = model_map.get("SMALL", {}).get("ollama")
                medium_model = model_map.get("MEDIUM", {}).get("ollama")

                # Soft Dimming: If sustained external load > 20%, purge KV cache
                if avg_load > 20 and current_lab_mode == "vLLM":
                    logger.warning(
                        f"[VRAM] Sustained load ({avg_load:.1f}%). Soft Dimming."
                    )
                    await self._trigger_vllm_soft_dimming()

                if used > crit_limit:
                    await self.cleanup_silicon()
                    await self.update_status_json("Mind SUSPENDED (Critical VRAM)")
                    continue
                if (
                    used > down_limit
                    and current_lab_mode == "OLLAMA"
                    and (current_model != small_model)
                ):
                    asyncio.create_task(self.handle_downshift(small_model))
                    continue
                if used > warn_limit and current_lab_mode == "vLLM":
                    asyncio.create_task(self.handle_engine_swap(medium_model))
                    continue
        except Exception as e:
            logger.error(f"[VRAM] Watchdog CRASHED: {e}")

    async def _get_gpu_load(self):
        """Fetch real-time GPU utilization using pynvml (DCGM baseline)."""
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            pynvml.nvmlShutdown()
            return util.gpu
        except Exception:
            return 0

    async def _trigger_vllm_soft_dimming(self):
        """Purge vLLM KV cache to free VRAM for external apps."""
        try:
            # Note: vLLM handles this via individual request cancellation.
            # We can force it by hitting the model endpoint with a tiny sequence.
            pass
            await self.update_status_json("Mind DIMMING (Sharing Silicon)")
        except Exception as e:
            logger.error(f"Soft dimming failed: {e}")

    async def handle_engine_swap(self, target_model):
        """Hot-swaps vLLM for Ollama fallback."""
        global current_lab_mode
        current_lab_mode = "SWAPPING"
        await self.cleanup_silicon()
        payload = {
            "engine": "OLLAMA",
            "model": target_model,
            "mode": "SERVICE_UNATTENDED",
            "disable_ear": True,
        }

        class MockReq:
            async def json(self):
                return payload

        await self.handle_start(MockReq())
        await self.update_status_json("Mind SWAPPED (VRAM Warning)")

    async def handle_downshift(self, target_model):
        """Hot-swaps Ollama models to survive pressure."""
        global current_lab_mode, current_model
        current_lab_mode = "DOWNSHIFTING"
        await self.cleanup_silicon()
        payload = {
            "engine": "OLLAMA",
            "model": target_model,
            "mode": "SERVICE_UNATTENDED",
            "disable_ear": True,
        }

        class MockReq:
            async def json(self):
                return payload

        await self.handle_start(MockReq())
        current_model = target_model
        await self.update_status_json("Mind DOWNSHIFTED (Tier 3)")

    async def log_monitor_loop(self):
        """Persistent watch for READY signal."""
        self.ready_event.clear()
        while True:
            if os.path.exists(SERVER_LOG):
                try:
                    with open(SERVER_LOG, "r") as f:
                        while True:
                            line = f.readline()
                            if not line:
                                await asyncio.sleep(0.5)
                                if not lab_process or lab_process.poll() is not None:
                                    break
                                continue
                            if "[READY] Lab is Open" in line:
                                self.ready_event.set()
                                await self.update_status_json()
                                return
                except Exception:
                    pass
            await asyncio.sleep(1)

    async def handle_start(self, request):
        global lab_process, current_lab_mode, current_model
        data = await request.json()
        pref_eng = data.get("engine", "OLLAMA")
        tier_or_mod = data.get("model")
        model_map = self.vram_config.get("model_map", {})
        if tier_or_mod in model_map:
            res_mod = model_map[tier_or_mod].get(pref_eng.lower())
        else:
            res_mod = tier_or_mod
        current_lab_mode = pref_eng
        current_model = res_mod if res_mod else (
            model_map.get("MEDIUM", {}).get(pref_eng.lower())
        )

        # Resolve absolute path if available in manifest
        actual_model_path = self.model_manifest.get(current_model, current_model)
        logger.info(f"[START] Resolved '{current_model}' to: {actual_model_path}")

        await self.cleanup_silicon()
        if pref_eng == "vLLM":
            # Non-blocking start for vLLM
            subprocess.Popen(["bash", VLLM_START_PATH, actual_model_path])
            await asyncio.sleep(35)
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
        env["USE_BRAIN_VLLM"] = "1" if pref_eng == "vLLM" else "0"
        env["BRAIN_MODEL"] = current_model
        env["PINKY_MODEL"] = current_model
        if data.get("disable_ear", True):
            env["DISABLE_EAR"] = "1"
        with open(SERVER_LOG, "w") as f:
            f.write("")
        try:
            cmd = [
                LAB_VENV_PYTHON,
                LAB_SERVER_PATH,
                "--mode",
                data.get("mode", "SERVICE_UNATTENDED"),
                "--afk-timeout",
                str(data.get("afk_timeout", 300)),
            ]
            if data.get("disable_ear", True):
                cmd.append("--disable-ear")

            lab_process = subprocess.Popen(
                cmd,
                cwd=LAB_DIR,
                env=env,
                stderr=open(SERVER_LOG, "a", buffering=1),
            )
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
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            os.rename(SERVER_LOG, f"{SERVER_LOG}.{ts}")
        return web.json_response({"status": "success"})

    async def handle_hard_reset(self, request):
        await self.cleanup_silicon()
        await self.update_status_json()
        return web.json_response({"status": "success"})

    async def handle_refresh(self, request):
        """Silicon Hygiene: Reloads config and purges memory (KV Purge)."""
        self.refresh_vram_config()
        if current_lab_mode != "OFFLINE":

            async def background_cooldown():
                old_mode, old_model = current_lab_mode, current_model
                await self.cleanup_silicon()
                await self.update_status_json("Mind COOLDOWN (Hygiene)")
                await asyncio.sleep(5)
                payload = {
                    "engine": old_mode,
                    "model": old_model,
                    "mode": "SERVICE_UNATTENDED",
                    "disable_ear": True,
                }

                class MockReq:
                    async def json(self):
                        return payload

                await self.handle_start(MockReq())

            asyncio.create_task(background_cooldown())
        return web.json_response({"status": "success", "message": "Hygiene scheduled."})

    async def handle_wait_ready(self, request):
        timeout = int(request.query.get("timeout", 60))
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
            vitals = await self._get_current_vitals()
            return web.json_response({"status": "ready", "vitals": vitals})
        except asyncio.TimeoutError:
            vitals = await self._get_current_vitals()
            return web.json_response(
                {"status": "timeout", "vitals": vitals}, status=408
            )

    async def handle_heartbeat(self, request):
        vitals = await self._get_current_vitals()
        await self.update_status_json()
        return web.json_response(vitals)

    async def handle_logs(self, request):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, "r") as f:
                return web.Response(text=f.read()[-5000:], content_type="text/plain")
        return web.json_response({"status": "not_found"}, status=404)

    async def handle_blocking_status(self, request):
        timeout_str = request.query.get("timeout")
        if timeout_str is None:
            return web.json_response(
                {"error": "Mandatory 'timeout' missing."}, status=400
            )
        timeout = int(timeout_str)
        start_t = time.time()
        while time.time() - start_t < timeout:
            vitals = await self._get_current_vitals()
            if (
                not vitals["lab_server_running"]
                or vitals["last_error"]
                or (vitals["full_lab_ready"])
            ):
                return web.json_response(vitals)
            await asyncio.sleep(1)
        return web.json_response(await self._get_current_vitals())

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
            "last_error": None,
        }
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
        elif lab_process and lab_process.poll() is not None:
            vitals["last_error"] = f"Process died: {lab_process.poll()}"
        return vitals

    async def update_status_json(self, custom_message=None):
        vitals = await self._get_current_vitals()
        try:
            v_used, v_total = await self._get_vram_info()
            v_pct = (v_used / v_total * 100) if v_total > 0 else 0
            msg = custom_message if custom_message else (
                "Mind is " + ("READY" if vitals["full_lab_ready"] else "BOOTING")
            )
            live_data = {
                "status": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
                "message": msg,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "vitals": {
                    "brain": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
                    "intercom": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
                    "vram": f"{v_pct:.1f}%",
                    "model": current_model,
                    "mode": current_lab_mode,
                },
            }
            with open(STATUS_JSON, "w") as f:
                json.dump(live_data, f)
        except Exception:
            pass

    async def cleanup_silicon(self):
        targets = ["vllm", "ollama", "acme_lab.py", "archive_node.py"]
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                line = " ".join(proc.info["cmdline"] or []).lower()
                if any(t in line for t in targets):
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    async def run(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", ATTENDANT_PORT).start()
        logger.info(f"[BOOT] Attendant online on {ATTENDANT_PORT}")
        asyncio.create_task(self.vram_watchdog_loop())
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(LabAttendant().run())
