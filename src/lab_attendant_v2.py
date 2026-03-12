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
import uuid
import sys
import contextlib
import signal
from mcp.server.fastmcp import FastMCP

# --- Configuration ---
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
SERVER_LOG = f"{LAB_DIR}/server.log"
ATTENDANT_LOG = f"{LAB_DIR}/attendant.log"
SERVER_PID_FILE = f"{LAB_DIR}/server.pid"
STATUS_JSON = f"{PORTFOLIO_DIR}/field_notes/data/status.json"
CHARACTERIZATION_FILE = f"{PORTFOLIO_DIR}/field_notes/data/vram_characterization.json"
INFRASTRUCTURE_FILE = f"{LAB_DIR}/config/infrastructure.json"
ROUND_TABLE_LOCK = f"{LAB_DIR}/round_table.lock"
MAINTENANCE_LOCK = f"{PORTFOLIO_DIR}/field_notes/data/maintenance.lock"
PAGER_ACTIVITY_FILE = f"{PORTFOLIO_DIR}/field_notes/data/pager_activity.json"
GATEKEEPER_PATH = f"{PORTFOLIO_DIR}/monitor/notify_gatekeeper.py"
VLLM_START_PATH = f"{LAB_DIR}/src/start_vllm.sh"
LAB_SERVER_PATH = f"{LAB_DIR}/src/acme_lab.py"
LAB_VENV_PYTHON = f"{LAB_DIR}/.venv/bin/python3"
ATTENDANT_PORT = 9999

MONITOR_CONTAINERS = [
    "field_prometheus", "field_grafana", "field_node_exporter", 
    "field_rapl_sim", "field_dcgm_exporter", "field_loki", "field_promtail", "jellyfin", "navidrome"
]

# --- Global State ---
lab_process = None
current_lab_mode = "OFFLINE"
current_model = None

# --- THE MONTANA PROTOCOL ---
_logger_initialized = False
_BOOT_HASH = uuid.uuid4().hex[:4].upper()

def get_git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], 
                                        cwd=LAB_DIR, text=True).strip()
    except Exception:
        return "unknown"

def get_fingerprint(role="ATTENDANT"):
    return f"[{_BOOT_HASH}:{get_git_commit()}:{role}]"

def reclaim_logger(role="ATTENDANT"):
    global _logger_initialized
    if _logger_initialized:
        return

    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    fmt = logging.Formatter(f"%(asctime)s - {get_fingerprint(role)} %(levelname)s - %(message)s")

    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    fh = logging.FileHandler(ATTENDANT_LOG, mode="a", delay=False)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    root.setLevel(logging.INFO)
    _logger_initialized = True

# --- Logger ---
reclaim_logger()
logger = logging.getLogger("lab_attendant_v2")

# --- FastMCP Server ---
mcp = FastMCP("Acme Lab Attendant", dependencies=["mcp", "psutil", "aiohttp", "pynvml"])

@web.middleware
async def cors_middleware(request, handler):
    # This is a simplified version for local dev; we can harden it later.
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        response = await handler(request)
    
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Lab-Key'
    return response

class LabAttendantV2:
    def __init__(self):
        self.app = web.Application(middlewares=[cors_middleware])
        self.app.router.add_post("/start", self.handle_start_rest)
        self.app.router.add_post("/stop", self.handle_stop_rest)
        self.app.router.add_post("/cleanup", self.handle_cleanup_rest)
        self.app.router.add_post("/hard_reset", self.handle_hard_reset_rest)
        self.app.router.add_post("/refresh", self.handle_refresh_rest)
        
        # [FEAT-142/143/144] Laboratory Experiment Suite
        self.app.router.add_post("/quiesce", self.handle_quiesce_rest)
        self.app.router.add_post("/ignition", self.handle_ignition_rest)
        self.app.router.add_post("/ping", self.handle_ping_rest)
        
        self.app.router.add_get("/wait_ready", self.handle_wait_ready_rest)
        self.app.router.add_get("/heartbeat", self.handle_heartbeat_rest)
        self.app.router.add_get("/mutex", self.handle_mutex_rest)
        self.app.router.add_get("/logs", self.handle_logs_rest)
        self.app.router.add_get("/blocking_status", self.handle_blocking_status_rest)
        
        # [FEAT-156] SSE: Event Stream for remote tools
        self.app.router.add_get("/events", self.handle_events_rest)
        self.event_queues: Set[asyncio.Queue] = set()

        self.ready_event = asyncio.Event()
        self.monitor_task = None
        self.vram_config = {}
        self.model_manifest = {}
        self.refresh_vram_config()

    async def broadcast_event(self, event_type, data):
        """Broadcasts a JSON event to all connected SSE clients."""
        payload = json.dumps({"type": event_type, "data": data, "timestamp": datetime.datetime.now().isoformat()})
        for queue in list(self.event_queues):
            await queue.put(payload)

    async def handle_events_rest(self, request):
        """[FEAT-156] SSE Endpoint: Streams status and log events."""
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            }
        )
        await response.prepare(request)
        queue = asyncio.Queue()
        self.event_queues.add(queue)
        logger.info(f"[SSE] New client connected. Active: {len(self.event_queues)}")
        
        try:
            # Initial status event
            vitals = await self.mcp_heartbeat()
            await response.write(f"data: {json.dumps({'type': 'init', 'vitals': vitals})}\n\n".encode('utf-8'))
            
            while True:
                data = await queue.get()
                await response.write(f"data: {data}\n\n".encode('utf-8'))
        except Exception:
            pass
        finally:
            self.event_queues.remove(queue)
            logger.info(f"[SSE] Client disconnected. Active: {len(self.event_queues)}")
        return response

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

    # --- MCP Tools Implementation ---
    async def mcp_heartbeat(self):
        vitals = await self._get_current_vitals()
        vitals["fingerprint"] = get_fingerprint()
        vitals["timestamp"] = datetime.datetime.now().isoformat()
        return vitals

    async def mcp_start(self, engine: str = "OLLAMA", model: str = "MEDIUM", mode: str = "SERVICE_UNATTENDED"):
        payload = {"engine": engine, "model": model, "mode": mode}
        # Mimic REST request
        class MockReq:
            async def json(self): return payload
        res = await self.handle_start_rest(MockReq())
        return json.loads(res.text)

    async def mcp_stop(self):
        await self.cleanup_silicon()
        await self.update_status_json()
        return {"status": "success", "message": "Lab stopped."}

    async def mcp_quiesce(self):
        logger.warning("[QUIESCE] Lockdown initiated. Setting maintenance lock.")
        with open(MAINTENANCE_LOCK, "w") as f:
            f.write(datetime.datetime.now().isoformat())
        await self.cleanup_silicon()
        await self.update_status_json("MAINTENANCE MODE (Locked)")
        return {"status": "locked", "message": "Lab frozen. Watchdog passive."}

    async def mcp_ignition(self):
        logger.info("[IGNITION] Manual ignition triggered. Clearing lock.")
        if os.path.exists(MAINTENANCE_LOCK):
            os.remove(MAINTENANCE_LOCK)
        asyncio.create_task(self._safe_pilot_ignition(grace=0))
        return {"status": "igniting", "message": "Lock cleared. Ignition sequence active."}

    # --- REST Handlers (Existing Logic) ---
    async def handle_start_rest(self, request):
        global lab_process, current_lab_mode, current_model
        try:
            data = await request.json()
        except:
            data = {}
            
        pref_eng = data.get("engine", "OLLAMA")
        tier_or_mod = data.get("model", "MEDIUM")
        
        custom_venv = data.get("venv_path")
        python_bin = os.path.join(custom_venv, "bin/python3") if custom_venv else LAB_VENV_PYTHON
        
        model_map = self.vram_config.get("model_map", {})
        
        if tier_or_mod in model_map:
            res_mod = model_map[tier_or_mod].get(pref_eng.lower())
        else:
            res_mod = tier_or_mod
            
        current_lab_mode = pref_eng
        current_model = res_mod if res_mod else (
            model_map.get("MEDIUM", {}).get(pref_eng.lower())
        )

        if current_lab_mode == "VLLM" and current_model and not current_model.startswith("/"):
            potential_path = os.path.join("/speedy/models", current_model)
            if os.path.exists(potential_path):
                current_model = potential_path
            else:
                current_model = f"/speedy/models/{current_model}"

        # [FEAT-119] The Assassin: Refined check
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', 8765)) == 0:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get("http://localhost:8765/heartbeat", timeout=1) as resp:
                            if resp.status == 200:
                                logger.info("[START] Lab already healthy on 8765. Attaching.")
                                return web.json_response({"status": "attached"})
                except Exception:
                    logger.warning("[ASSASSIN] Zombie detected on 8765. Executing cleanup.")
                    await self.cleanup_silicon()

        self.ready_event.clear()

        async def boot_sequence():
            await self.cleanup_silicon()
            await asyncio.sleep(2.0)

            global lab_process
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
            env["LAB_MODE"] = pref_eng
            
            if pref_eng == "VLLM":
                env["VLLM_ATTENTION_BACKEND"] = "XFORMERS"
                env["NCCL_P2P_DISABLE"] = "1"
                env["NCCL_SOCKET_IFNAME"] = "lo"
                env["VLLM_USE_V1"] = "0"
                
                user_args = data.get("extra_args", "")
                if "--gpu-memory-utilization" not in user_args:
                    env["VLLM_EXTRA_ARGS"] = f"{user_args} --gpu-memory-utilization 0.4 --enforce-eager --dtype float16 --max-model-len 4096 --max-num-seqs 1"
                else:
                    env["VLLM_EXTRA_ARGS"] = user_args

                logger.info(f"[VLLM] Igniting Sovereign Node: {current_model}")
                subprocess.Popen(
                    ["bash", VLLM_START_PATH, current_model, sys.executable],
                    env=env, cwd=LAB_DIR
                )
                # [FEAT-145] Engine Sync
                await self._wait_for_vllm()

            brain_pref = data.get("brain_model")
            
            if tier_or_mod in model_map:
                env["BRAIN_MODEL"] = brain_pref if brain_pref else ("LARGE" if pref_eng == "OLLAMA" else current_model)
                env["PINKY_MODEL"] = tier_or_mod
            else:
                env["BRAIN_MODEL"] = brain_pref if brain_pref else current_model
                env["PINKY_MODEL"] = current_model
                
            if data.get("disable_ear", True):
                env["DISABLE_EAR"] = "1"

            extra_args = data.get("extra_args", "")
            
            try:
                cmd = [
                    python_bin,
                    LAB_SERVER_PATH,
                    "--mode", data.get("mode", "SERVICE_UNATTENDED"),
                    "--afk-timeout", str(data.get("afk_timeout", 300)),
                ]
                if data.get("disable_ear", True):
                    cmd.append("--disable-ear")
                
                if pref_eng == "VLLM":
                    env["VLLM_EXTRA_ARGS"] = f"--enable-lora --max-loras 4 {extra_args}"

                lab_process = subprocess.Popen(
                    cmd, cwd=LAB_DIR, env=env,
                    stderr=open(SERVER_LOG, "a", buffering=1),
                    preexec_fn=os.setpgrp
                )
                self.monitor_task = asyncio.create_task(self.log_monitor_loop())
                logger.info(f"[START] Lab Server started with PID: {lab_process.pid}")
            except Exception as e:
                logger.error(f"[START] Failed to launch Lab Server: {e}")

        asyncio.create_task(boot_sequence())
        return web.json_response({
            "status": "success", 
            "message": "Boot sequence initiated.",
            "wait_url": f"http://localhost:{ATTENDANT_PORT}/wait_ready?timeout=180"
        })

    async def _wait_for_vllm(self, timeout=180):
        """[FEAT-145] Engine Sync: Polls the vLLM port until it responds or times out."""
        start_t = time.time()
        logger.info("[VLLM] Waiting for engine on port 8088...")
        while time.time() - start_t < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:8088/v1/models", timeout=1.0) as r:
                        if r.status == 200:
                            logger.info("[VLLM] Engine is READY.")
                            return True
            except Exception:
                pass
            await asyncio.sleep(2.0)
        logger.error(f"[VLLM] Engine failed to respond in {timeout}s.")
        return False

    async def cleanup_silicon(self):
        """[FEAT-119] The Assassin: Refined parallel SIGKILL + 2s settle."""
        
        # [ROOT CAUSE FIX] Purge-Before-Poll
        # Explicitly kill any process holding the core ports first to ensure
        # that subsequent readiness checks aren't fooled by zombie processes.
        for port in [8088, 8765]:
            try:
                subprocess.run(["sudo", "fuser", "-k", f"{port}/tcp"], capture_output=True)
            except Exception:
                pass

        protected_pgids = {os.getpgid(os.getpid())}
        protected_pids = {os.getpid(), os.getppid()}
        pids_to_kill = set()

        try:
            for conn in psutil.net_connections(kind="tcp"):
                if conn.laddr.port in [8765, 8088]:
                    if conn.pid and conn.pid not in protected_pids:
                        with contextlib.suppress(Exception):
                            pgid = os.getpgid(conn.pid)
                            if pgid not in protected_pgids:
                                pids_to_kill.add((conn.pid, pgid))
        except Exception as e:
            logger.error(f"[ASSASSIN] Port check failed: {e}")

        targets = ["acme_lab.py", "archive_node.py", "pinky_node.py", "brain_node.py", "vllm", "ollama"]
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["pid"] in protected_pids:
                    continue
                cmdline = " ".join(proc.info["cmdline"] or []).lower()
                if any(t in cmdline for t in targets):
                    pgid = os.getpgid(proc.info["pid"])
                    if pgid not in protected_pgids:
                        pids_to_kill.add((proc.info["pid"], pgid))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if pids_to_kill:
            logger.warning(f"[ASSASSIN] Executing parallel purge of {len(pids_to_kill)} process groups.")
            for pid, pgid in pids_to_kill:
                with contextlib.suppress(Exception):
                    os.killpg(pgid, signal.SIGKILL)
            
            await asyncio.sleep(2.0)
            logger.info("[ASSASSIN] Silicon scrub complete.")

    async def _get_current_vitals(self):
        vitals = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "engine_running": False,
            "lab_mode": current_lab_mode,
            "model": current_model,
            "full_lab_ready": self.ready_event.is_set(),
            "last_error": None,
            "boot_hash": _BOOT_HASH,
            "commit": get_git_commit()
        }
        
        # Check Hub Port
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', 8765), timeout=0.5)
            vitals["lab_server_running"] = True
            writer.close()
            await writer.wait_closed()
        except:
            pass

        # Check Engine Port
        engine_port = 8088 if current_lab_mode == "VLLM" else 11434
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{engine_port}/api/tags" if engine_port == 11434 else f"http://localhost:8088/v1/models", timeout=0.5) as r:
                    if r.status == 200:
                        vitals["engine_running"] = True
        except:
            pass

        return vitals

    async def update_status_json(self, custom_message=None):
        vitals = await self._get_current_vitals()
        try:
            v_used, v_total = await self._get_vram_info()
            v_pct = (v_used / v_total * 100) if v_total > 0 else 0
            
            msg = custom_message or ("Mind is READY" if vitals["full_lab_ready"] else "Mind is BOOTING")
            if not vitals["lab_server_running"]: msg = "Mind is OFFLINE"

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
        except: pass

    async def vram_watchdog_loop(self):
        """
        [FEAT-180] Graceful Resource Governance: Replaces fallbacks with a Hard Stop.
        """
        while True:
            await asyncio.sleep(5) # Increased frequency for Phase 12 hardening
            if os.path.exists(MAINTENANCE_LOCK): continue
            
            # 1. VRAM Check
            used, total = await self._get_vram_info()
            critical_vram = total > 0 and used > (total * 0.95)
            
            # 2. Load Check
            load1, _, _ = os.getloadavg()
            critical_load = load1 > 8.0
            
            if critical_vram or critical_load:
                reason = "Critical VRAM" if critical_vram else "Critical System Load"
                logger.error(f"[WATCHDOG] {reason} ({used}MiB / {load1}). Executing SIGTERM.")
                
                # Execute [TASK-008] Hard Stop
                await self.cleanup_silicon()
                await self.update_status_json(f"Mind TERMINATED ({reason})")
                
                # Notify active clients via Pager
                try:
                    with open(os.path.expanduser("~/Dev_Lab/Portfolio_Dev/monitor/pager_activity.json"), "a") as f:
                        f.write(json.dumps({
                            "severity": "CRITICAL",
                            "message": f"Lab Hub hard-stopped due to {reason} to preserve silicon integrity.",
                            "timestamp": datetime.datetime.now().isoformat()
                        }) + "\n")
                except: pass

    async def _get_vram_info(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            used, total = info.used // 1024 // 1024, info.total // 1024 // 1024
            pynvml.nvmlShutdown()
            return used, total
        except: return 0, 0

    async def log_monitor_loop(self):
        self.ready_event.clear()
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, "r") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        if not lab_process or lab_process.poll() is not None: break
                        continue
                    if "[READY] Lab is Open" in line:
                        self.ready_event.set()
                        logger.info("[WATCHDOG] Lab reported READY signal.")
                        await self.update_status_json()
                        return
        await asyncio.sleep(1)

    async def _safe_pilot_ignition(self, grace=60):
        if grace > 0: await asyncio.sleep(grace)
        vitals = await self._get_current_vitals()
        if vitals["lab_server_running"]: return
        used, total = await self._get_vram_info()
        if used > 6000: return
        
        class MockReq:
            async def json(self): return {"mode": "SERVICE_UNATTENDED", "engine": "OLLAMA", "model": "MEDIUM", "disable_ear": True}
        await self.handle_start_rest(MockReq())

    # --- REST Handlers for other endpoints ---
    async def handle_stop_rest(self, request): return web.json_response(await self.mcp_stop())
    async def handle_cleanup_rest(self, request):
        if os.path.exists(SERVER_LOG):
            os.rename(SERVER_LOG, f"{SERVER_LOG}.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        return web.json_response({"status": "success"})
    async def handle_hard_reset_rest(self, request): return await self.handle_stop_rest(request)
    async def handle_refresh_rest(self, request):
        self.refresh_vram_config()
        return web.json_response({"status": "success"})
    async def handle_quiesce_rest(self, request): return web.json_response(await self.mcp_quiesce())
    async def handle_ignition_rest(self, request): return web.json_response(await self.mcp_ignition())
    async def handle_ping_rest(self, request):
        vitals = await self.mcp_heartbeat()
        return web.json_response(vitals)
    async def handle_wait_ready_rest(self, request):
        timeout = int(request.query.get("timeout", 60))
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
            return web.json_response({"status": "ready", "vitals": await self.mcp_heartbeat()})
        except: return web.json_response({"status": "timeout"}, status=408)
    async def handle_heartbeat_rest(self, request): return web.json_response(await self.mcp_heartbeat())
    async def handle_mutex_rest(self, request):
        exists = os.path.exists(ROUND_TABLE_LOCK)
        return web.json_response({"round_table_lock_exists": exists, "lab_ready": self.ready_event.is_set()})
    async def handle_logs_rest(self, request):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, "r") as f: return web.Response(text=f.read()[-5000:], content_type="text/plain")
        return web.json_response({"status": "not_found"}, status=404)
    async def handle_blocking_status_rest(self, request):
        timeout = int(request.query.get("timeout", 30))
        start_t = time.time()
        while time.time() - start_t < timeout:
            vitals = await self._get_current_vitals()
            if vitals["full_lab_ready"]: return web.json_response(vitals)
            await asyncio.sleep(1)
        return web.json_response(await self._get_current_vitals())


# --- Global Instance and MCP Wrappers ---
attendant = LabAttendantV2()

@mcp.tool()
async def lab_heartbeat():
    """Returns the current Lab vitals, VRAM status, and fingerprint."""
    return await attendant.mcp_heartbeat()

@mcp.tool()
async def lab_start(engine: str = "OLLAMA", model: str = "MEDIUM", mode: str = "SERVICE_UNATTENDED"):
    """Starts the Lab reasoning engines and resident nodes."""
    return await attendant.mcp_start(engine, model, mode)

@mcp.tool()
async def lab_stop():
    """Executes the Parallel Assassin to purge all Lab processes."""
    return await attendant.mcp_stop()

@mcp.tool()
async def lab_quiesce():
    """Freezes the Lab for maintenance (sets lock and kills processes)."""
    return await attendant.mcp_quiesce()

@mcp.tool()
async def lab_ignition():
    """Manual override to clear maintenance locks and start the Lab."""
    return await attendant.mcp_ignition()

async def run_bilingual():
    # Start REST API in background
    runner = web.AppRunner(attendant.app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", ATTENDANT_PORT).start()
    logger.info(f"[BOOT] REST API online on {ATTENDANT_PORT}")
    
    # Run Background Loops
    asyncio.create_task(attendant.vram_watchdog_loop())
    asyncio.create_task(attendant._safe_pilot_ignition())
    
    # Start MCP Server only if not in a service context or if explicitly requested
    # If stdin is not a TTY, and we aren't being called by another process, 
    # we should just wait for the REST API.
    if sys.stdin.isatty():
        logger.info("[BOOT] MCP Server initiating (STDIO)...")
        await mcp.run_stdio_async()
    else:
        # Check if we are likely being called as a tool (e.g. by Gemini CLI)
        # Gemini CLI usually provides stdin.
        # However, systemd services have stdin redirected to /dev/null.
        try:
            # If we can't run stdio, we just wait for the REST server.
            logger.info("[BOOT] Service mode detected. Waiting for REST traffic.")
            await asyncio.Event().wait()
        except Exception as e:
            logger.error(f"[BOOT] Runtime error: {e}")

if __name__ == "__main__":
    asyncio.run(run_bilingual())
