import os
import subprocess
import json
import asyncio
import datetime
import logging
import psutil
import aiohttp
import hashlib
from aiohttp import web
import time
import uuid
import sys
import contextlib
import signal
from mcp.server.fastmcp import FastMCP
from infra.montana import reclaim_logger

# [BKM-022] Atomic IO & [FEAT-151] Trace Monitoring
from infra.atomic_io import atomic_write_json
from debug.trace_monitor import TraceMonitor

# --- Path Self-Awareness ---
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
if _SELF_DIR not in sys.path:
    sys.path.insert(0, _SELF_DIR)

# --- Configuration ---
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
SERVER_LOG = f"{LAB_DIR}/server.log"
ATTENDANT_LOG = f"{LAB_DIR}/attendant.log"
STATUS_JSON = f"{PORTFOLIO_DIR}/field_notes/data/status.json"
CHARACTERIZATION_FILE = f"{PORTFOLIO_DIR}/field_notes/data/vram_characterization.json"
INFRASTRUCTURE_FILE = f"{LAB_DIR}/config/infrastructure.json"
EXPERTISE_DIR = f"{LAB_DIR}/src/forge/expertise"
ROUND_TABLE_LOCK = f"{LAB_DIR}/round_table.lock"
MAINTENANCE_LOCK = f"{PORTFOLIO_DIR}/field_notes/data/maintenance.lock"
PAGER_ACTIVITY_FILE = f"{PORTFOLIO_DIR}/field_notes/data/pager_activity.json"
VLLM_START_PATH = f"{LAB_DIR}/src/start_vllm.sh"
LAB_SERVER_PATH = f"{LAB_DIR}/src/acme_lab.py"
LAB_VENV_PYTHON = f"{LAB_DIR}/.venv/bin/python3"
STYLE_CSS = f"{PORTFOLIO_DIR}/field_notes/style.css"
ATTENDANT_PORT = 9999

# --- Global State ---
lab_process = None
current_lab_mode = "OFFLINE"
current_model = None
_BOOT_HASH = uuid.uuid4().hex[:4].upper()

# [BKM-002] Montana Protocol: Aggressive Logger Authority
reclaim_logger(role="ATTENDANT")
logger = logging.getLogger("lab_attendant_v3")

def get_style_key():
    """Generates the 'Moving Target' key from the style.css hash."""
    if not os.path.exists(STYLE_CSS):
        logger.error(f"[SECURITY] STYLE_CSS missing: {STYLE_CSS}")
        return "missing"
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

def get_git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], 
                                        cwd=LAB_DIR, text=True).strip()
    except Exception:
        return "unknown"

def get_fingerprint(role="ATTENDANT"):
    return f"[{_BOOT_HASH}:{get_git_commit()}:{role}]"

# --- FastMCP Server ---
mcp = FastMCP("Acme Lab Attendant", dependencies=["mcp", "psutil", "aiohttp", "pynvml"])

@web.middleware
async def key_middleware(request, handler):
    """[FEAT-219] Silicon Handshake: Validates the Lab Key (Query or Header)."""
    # Allow OPTIONS for CORS
    if request.method == "OPTIONS":
        return await handler(request)
        
    # Heartbeat and Ping are public-read for the dashboard
    if any(request.path.endswith(p) for p in ["/heartbeat", "/ping", "/mutex", "/wait_ready"]):
        return await handler(request)

    expected_key = get_style_key()
    provided_key = request.query.get("key") or request.headers.get("LabKey") or request.headers.get("X-Lab-Key")

    if provided_key != expected_key:
        logger.warning(f"[SECURITY] Invalid Key: {provided_key} (Expected: {expected_key}) from {request.remote}")
        return web.json_response({"status": "error", "message": "Invalid Lab Key. Unauthorized."}, status=401)
    
    return await handler(request)

@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Lab-Key'
    return response

class LabAttendantV3:
    def __init__(self):
        self.app = web.Application(middlewares=[cors_middleware, key_middleware])
        
        # [SERVICE] Control & Monitoring Endpoints (Dual-Registration for Option B)
        self.register_route("POST", "/start", self.handle_start_rest)
        self.register_route("POST", "/stop", self.handle_stop_rest)
        self.register_route("POST", "/quiesce", self.handle_quiesce_rest)
        self.register_route("POST", "/ignition", self.handle_ignition_rest)
        self.register_route("POST", "/refresh", self.handle_ignition_rest)
        self.register_route("POST", "/train", self.handle_train_rest)
        self.register_route("POST", "/hard_reset", self.handle_stop_rest)
        self.register_route("GET", "/heartbeat", self.handle_heartbeat_rest)
        self.register_route("GET", "/ping", self.handle_ping_rest)
        self.register_route("GET", "/wait_ready", self.handle_wait_ready_rest)
        self.register_route("GET", "/logs", self.handle_logs_rest)
        self.register_route("GET", "/mutex", self.handle_mutex_rest)
        
        self.trace_monitor = TraceMonitor([SERVER_LOG, ATTENDANT_LOG])
        self.ready_event = asyncio.Event()
        self.vram_config = {}
        self.refresh_vram_config()

    def register_route(self, method, path, handler):
        """[FEAT-219] Silicon Handshake: Multi-Path Router."""
        if method == "POST":
            self.app.router.add_post(path, handler)
            self.app.router.add_post(f"/attendant{path}", handler)
        else:
            self.app.router.add_get(path, handler)
            self.app.router.add_get(f"/attendant{path}", handler)

    def refresh_vram_config(self):
        if os.path.exists(CHARACTERIZATION_FILE):
            try:
                with open(CHARACTERIZATION_FILE, "r") as f:
                    self.vram_config = json.load(f)
            except Exception:
                pass

    # --- Pager Helper ---
    def log_event(self, message, severity="INFO"):
        """Appends a milestone event to the interleaved Forensic Ledger."""
        try:
            alert = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "source": "LabAttendant",
                "severity": severity,
                "message": message
            }
            data = []
            if os.path.exists(PAGER_ACTIVITY_FILE):
                with open(PAGER_ACTIVITY_FILE, "r") as f:
                    data = json.load(f)
            data.append(alert)
            data = data[-100:] # Keep last 100
            with open(PAGER_ACTIVITY_FILE + ".tmp", "w") as f:
                json.dump(data, f, indent=2)
            os.replace(PAGER_ACTIVITY_FILE + ".tmp", PAGER_ACTIVITY_FILE)
        except Exception as e:
            logger.error(f"[PAGER] Failed to log event: {e}")

    # --- Pulse Loop ---
    async def pulse_loop(self):
        """Continuous background vitals pulse for the dashboard."""
        logger.info("[PULSE] Background status cycle active (2s).")
        while True:
            await self.update_status_json()
            await asyncio.sleep(2)

    # --- Proxy Helper ---
    async def _proxy_request(self, method, endpoint, data=None):
        """Redirects tool calls from the Proxy process to the Master Service."""
        key = get_style_key()
        connector = "&" if "?" in endpoint else "?"
        url = f"http://localhost:{ATTENDANT_PORT}/{endpoint}{connector}key={key}"
        async with aiohttp.ClientSession() as session:
            try:
                if method == "POST":
                    async with session.post(url, json=data) as r:
                        return await r.json()
                else:
                    async with session.get(url) as r:
                        return await r.json()
            except Exception as e:
                return {"status": "error", "message": f"Proxy connection to Master failed: {e}"}

    # --- MCP Tools Implementation ---
    async def mcp_heartbeat(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("GET", "heartbeat")
        vitals = await self._get_current_vitals()
        vitals["fingerprint"] = get_fingerprint()
        vitals["timestamp"] = datetime.datetime.now().isoformat()
        return vitals

    async def mcp_start(self, engine: str = "OLLAMA", model: str = "MEDIUM", disable_ear: bool = True, op_mode: str = "SERVICE_UNATTENDED"):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "start", {"engine": engine, "model": model, "disable_ear": disable_ear, "op_mode": op_mode})
        
        global current_lab_mode, current_model, lab_process
        logger.info(f"[IGNITION] Starting {model} via {engine} (Mode: {op_mode})")
        
        self.refresh_vram_config() # Reload latest model mappings
        
        # Resolve model path and config from map
        model_map = self.vram_config.get("model_map", {})
        tier_config = model_map.get(model, model_map.get("UNIFIED", {}))
        
        target_model = tier_config.get("vllm" if engine == "VLLM" else "ollama", model)
        utilization = tier_config.get("gpu_memory_utilization", 0.4)
        backend = tier_config.get("attention_backend", "TRITON_ATTN")

        current_lab_mode = engine
        current_model = target_model
        
        await self.cleanup_silicon()
        self.ready_event.clear()
        self.trace_monitor.refresh_marks()
        
        env = os.environ.copy()
        env["LAB_MODE"] = str(engine)
        # [FEAT-220] Silicon Handshake: Inject Immunity Token into all spawned families
        env["LAB_IMMUNITY_TOKEN"] = str(_BOOT_HASH)
        
        if disable_ear:
            env["DISABLE_EAR"] = "1"
        
        # Sanitize: subprocess.Popen requires all env values to be strings and not None
        env = {k: str(v) for k, v in env.items() if v is not None}
        
        if engine == "VLLM":
            # [SPR-13.0] Verified Stable Config from characterization.json
            env["NCCL_P2P_DISABLE"] = "1"
            env["NCCL_SOCKET_IFNAME"] = "lo"
            env["VLLM_ATTENTION_BACKEND"] = backend
            # VLLM_EXTRA_ARGS must include the backend flag as the env var is ignored in 0.17
            env["VLLM_EXTRA_ARGS"] = f"--gpu-memory-utilization {utilization} --enforce-eager --attention-backend {backend} --enable-lora --max-loras 4"
            
            logger.info(f"[VLLM] Igniting Sovereign Node: {target_model} (Util: {utilization}, Backend: {backend})")
            self.log_event(f"Ignition: {engine}/{target_model} (Mode: {op_mode})")
            subprocess.Popen(["bash", VLLM_START_PATH, target_model, sys.executable], env=env, cwd=LAB_DIR)
            await self._wait_for_vllm()

        # Start Hub
        cmd = [sys.executable, LAB_SERVER_PATH, "--mode", op_mode]
        if disable_ear:
            cmd.append("--disable-ear")
        
        # [FEAT-213] Engine Warm-up Delay
        await asyncio.sleep(3)
        
        with open(SERVER_LOG, "a", buffering=1) as log_f:
            lab_process = subprocess.Popen(cmd, cwd=LAB_DIR, env=env, stderr=log_f, start_new_session=True)
            
        asyncio.create_task(self.log_monitor_loop())
        logger.info(f"[IGNITION] Hub process spawned with PID: {lab_process.pid} (Immunity: {_BOOT_HASH})")
        return {"status": "success", "message": f"Ignited {model} via {engine} in mode {op_mode}"}

    async def _deferred_cleanup(self, status_message):
        """[FEAT-248] Helper to run cleanup in background so REST response can complete."""
        await asyncio.sleep(0.5) # allow HTTP response to flush to client
        await self.cleanup_silicon()
        await self.update_status_json(status_message)

    async def mcp_stop(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "stop")
        self.log_event("Shutdown: Manual signal received.")
        asyncio.create_task(self._deferred_cleanup("OFFLINE (Manual Stop)"))
        return {"status": "success", "message": "Lab stopping..."}

    async def mcp_quiesce(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "quiesce")
        logger.warning("[QUIESCE] Lockdown initiated. Setting maintenance lock.")
        self.log_event("Quiesce: Lab locked for maintenance.", severity="WARNING")
        with open(MAINTENANCE_LOCK, "w") as f:
            f.write(datetime.datetime.now().isoformat())
        asyncio.create_task(self._deferred_cleanup("MAINTENANCE MODE (Locked)"))
        return {"status": "locked", "message": "Lab freezing. Watchdog passive."}

    async def mcp_ignition(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "ignition")
        
        # [FEAT-213] Re-Ignition must clear the maintenance lock first
        if os.path.exists(MAINTENANCE_LOCK):
            os.remove(MAINTENANCE_LOCK)
            self.log_event("Ignition: Maintenance lock cleared.")
            
        # [SPR-13.0] Restoration using current state or defaults
        engine = os.environ.get("LAB_MODE", "OLLAMA")
        model = os.environ.get("LAB_MODEL", "MEDIUM")
        disable_ear = os.environ.get("DISABLE_EAR") == "1"
        
        return await self.mcp_start(engine, model, disable_ear, "SERVICE_UNATTENDED")

    async def mcp_train_adapter(self, adapter_name: str, steps: int = 60):
        """[FEAT-213/218] Autonomous VRAM Handover for Sequenced Batch Forging."""
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            # For proxy mode, we forward to the Master Attendant (which will then handle the batch logic)
            return await self._proxy_request("POST", "train", {"adapter": adapter_name, "steps": steps})
        
        # Support batch mode (comma-separated list)
        adapters = [a.strip() for a in adapter_name.split(",")]
        logger.info(f"[FORGE] Initiating sequenced batch training for: {adapters} ({steps} steps each).")
        self.log_event(f"Forge: Starting batch training for {len(adapters)} adapters.")
        
        # 1. Quiesce once for the entire batch
        await self.mcp_quiesce()
        await asyncio.sleep(5)
        
        # [FEAT-213] VRAM Guard: Verify silicon is ready for Unsloth
        self.refresh_vram_config()
        max_vram = self.vram_config.get("unsloth_threshold_mb", 10000)
        used_mb, total_mb = await self._get_vram_info()
        
        if used_mb > max_vram:
            logger.error(f"[FORGE] VRAM Guard Triggered: {used_mb}MB used, threshold is {max_vram}MB. Aborting.")
            self.log_event(f"Forge: VRAM Guard Triggered ({used_mb}MB). Aborting.", severity="WARNING")
            await self.mcp_ignition()
            return {"status": "error", "message": f"Silicon contention: {used_mb}MB used."}
        
        results = []
        for target in adapters:
            # 2. Identify Dataset
            dataset_map = {
                "lab_history": f"{EXPERTISE_DIR}/lab_history_training.jsonl",
                "cli_voice": f"{EXPERTISE_DIR}/cli_voice_training.jsonl",
                "lab_sentinel": f"{EXPERTISE_DIR}/lab_sentinel_training.jsonl"
            }
            dataset = dataset_map.get(target)
            output_dir = f"/speedy/models/adapters/{target}"
            
            if not dataset or not os.path.exists(dataset):
                logger.error(f"[FORGE] Dataset not found: {dataset}")
                self.log_event(f"Forge: Dataset missing for {target}", severity="WARNING")
                results.append({"adapter": target, "status": "missing_dataset"})
                continue

            # 3. Execute Forge (Unsloth)
            logger.info(f"[FORGE] Training {target}...")
            self.log_event(f"Forge: Training {target}...")
            try:
                cmd = [LAB_VENV_PYTHON, f"{LAB_DIR}/src/forge/train_expert.py", dataset, output_dir, str(steps)]
                process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    logger.info(f"[FORGE] {target} completed successfully.")
                    self.log_event(f"Forge: {target} completed successfully.")
                    results.append({"adapter": target, "status": "complete"})
                else:
                    logger.error(f"[FORGE] {target} failed: {stderr.decode()}")
                    self.log_event(f"Forge: {target} FAILED.", severity="WARNING")
                    results.append({"adapter": target, "status": "failed"})
            except Exception as e:
                logger.error(f"[FORGE] Execution error for {target}: {e}")
                self.log_event(f"Forge: Execution error for {target}", severity="WARNING")
                results.append({"adapter": target, "status": "error", "message": str(e)})
        
        # 4. Re-Ignite Hub once after all adapters are processed
        await self.mcp_ignition()
        self.log_event("Forge: Batch complete. Hub re-ignited.")
        return {"status": "batch_complete", "results": results}

    async def mcp_wait_ready(self, timeout: int = 60):
        """[FEAT-136] Blocking wait for the Lab Hub to reach the READY state."""
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("GET", f"wait_ready?timeout={timeout}")
        
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
            return {"status": "ready", "message": "Lab is Open."}
        except asyncio.TimeoutError:
            return {"status": "timeout", "message": f"Lab failed to reach READY within {timeout}s"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def cleanup_silicon(self):
        """[FEAT-119] Broad-Spectrum Assassin: Reclaim hardware handles by PGID with Immunity."""
        pgids_to_kill = set()
        my_pgid = os.getpgid(os.getpid())
        
        # 1. Port-Based Discovery
        for port in [8088, 8765]:
            try:
                res = subprocess.check_output(["sudo", "fuser", f"{port}/tcp"], stderr=subprocess.STDOUT, text=True)
                for line in res.split("\n"):
                    if ":" in line:
                        pid_str = line.split(":")[1].strip()
                        for p in pid_str.split():
                            p_int = int(p)
                            if self._is_immune(p_int): continue
                            pgids_to_kill.add(os.getpgid(p_int))
            except Exception:
                pass

        # 2. Name-Based Discovery
        targets = ["acme_lab.py", "archive_node.py", "pinky_node.py", "brain_node.py", "vllm", "ollama"]
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or []).lower()
                if any(t in cmdline for t in targets):
                    if self._is_immune(proc.info["pid"]): continue
                    pgids_to_kill.add(os.getpgid(proc.info["pid"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if pgids_to_kill:
            # Final Safety Catch: Never kill our own group
            pgids_to_kill.discard(my_pgid)
            if pgids_to_kill:
                logger.warning(f"[ASSASSIN] Purging {len(pgids_to_kill)} process groups: {pgids_to_kill}")
                for pgid in pgids_to_kill:
                    with contextlib.suppress(Exception):
                        os.killpg(pgid, signal.SIGKILL)
        
        await asyncio.sleep(2.0)

    def _is_immune(self, pid):
        """[FEAT-220] Checks if a process carries the current Diplomatic Immunity token."""
        try:
            if pid == os.getpid(): return True
            proc = psutil.Process(pid)
            # Check environment for the current boot hash
            env = proc.environ()
            token = env.get("LAB_IMMUNITY_TOKEN")
            if token == _BOOT_HASH:
                logger.info(f"[ASSASSIN] Sparing immune process {pid} ({proc.name()})")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return False

    async def _get_current_vitals(self):
        lab_server_running = False
        engine_running = False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8765/heartbeat", timeout=2.0) as r:
                    if r.status == 200:
                        lab_server_running = True
                port = 8088 if current_lab_mode == "VLLM" else 11434
                async with session.get(f"http://localhost:{port}/v1/models" if port == 8088 else f"http://localhost:{port}/api/tags", timeout=2.0) as r:
                    if r.status == 200:
                        engine_running = True
        except Exception:
            pass

        used_mb, total_mb = await self._get_vram_info()
        vram_pct = f"{(used_mb / total_mb * 100):.1f}%" if total_mb > 0 else "0.0%"

        return {
            "attendant_pid": os.getpid(),
            "mode": current_lab_mode,
            "model": current_model,
            "intercom": "ONLINE" if lab_server_running else "OFFLINE",
            "brain": "ONLINE" if engine_running else "OFFLINE",
            "vram": vram_pct,
            "full_lab_ready": self.ready_event.is_set(),
            "boot_hash": _BOOT_HASH
        }

    async def _get_vram_info(self):
        """[FEAT-213] Silicon Health Check: Returns (used_mb, total_mb)"""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            pynvml.nvmlShutdown()
            return int(info.used / 1024 / 1024), int(info.total / 1024 / 1024)
        except Exception as e:
            logger.error(f"[VRAM] Failed to probe silicon: {e}")
            return 0, 0

    async def update_status_json(self, msg=None):
        vitals = await self._get_current_vitals()
        live_data = {
            "status": "ONLINE" if vitals["intercom"] == "ONLINE" else "OFFLINE",
            "message": msg or ("READY" if vitals["full_lab_ready"] else "BOOTING"),
            "timestamp": datetime.datetime.now().isoformat(),
            "vitals": vitals
        }
        atomic_write_json(STATUS_JSON, live_data)

    async def log_monitor_loop(self):
        self.ready_event.clear()
        if not os.path.exists(SERVER_LOG):
            logger.warning(f"[WATCHDOG] Log file missing: {SERVER_LOG}")
            return

        with open(SERVER_LOG, "r") as f:
            # Seek to end initially to only catch new signals
            f.seek(0, os.SEEK_END)
            while True:
                if not lab_process or lab_process.poll() is not None:
                    logger.warning("[WATCHDOG] Lab process ended. Terminating log monitor.")
                    break
                
                line = f.readline()
                if not line:
                    await asyncio.sleep(1.0)
                    continue
                
                if "[READY] Lab is Open" in line:
                    self.ready_event.set()
                    logger.info("[WATCHDOG] Lab reported READY signal.")
                    await self.update_status_json("Mind is READY")
                    return

    async def _wait_for_vllm(self, timeout=120):
        start_t = time.time()
        while time.time() - start_t < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:8088/v1/models", timeout=1.0) as r:
                        if r.status == 200:
                            return True
            except Exception:
                pass
            await asyncio.sleep(2)
        return False

    async def vram_watchdog_loop(self):
        """[FEAT-180] Resilience Ladder: Passive Monitoring."""
        while True:
            await asyncio.sleep(10)
            if os.path.exists(MAINTENANCE_LOCK):
                continue
            pass

    # --- REST Handlers ---
    async def handle_start_rest(self, r): 
        data = await r.json()
        engine = data.get("engine", "OLLAMA")
        model = data.get("model", "MEDIUM")
        disable_ear = data.get("disable_ear", True)
        op_mode = data.get("op_mode", "SERVICE_UNATTENDED")
        return web.json_response(await self.mcp_start(engine, model, disable_ear, op_mode))
    async def handle_stop_rest(self, r):
        return web.json_response(await self.mcp_stop())
    async def handle_quiesce_rest(self, r):
        return web.json_response(await self.mcp_quiesce())
    async def handle_ignition_rest(self, r):
        return web.json_response(await self.mcp_ignition())
    async def handle_train_rest(self, r):
        data = await r.json()
        return web.json_response(await self.mcp_train_adapter(data.get("adapter"), data.get("steps", 60)))
    async def handle_heartbeat_rest(self, r):
        return web.json_response(await self.mcp_heartbeat())
    async def handle_ping_rest(self, r):
        return web.json_response(await self.mcp_heartbeat())
    async def handle_wait_ready_rest(self, r):
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=int(r.query.get("timeout", 60)))
            return web.json_response({"status": "ready"})
        except Exception:
            return web.json_response({"status": "timeout"}, status=408)
    async def handle_logs_rest(self, r):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, "r") as f:
                return web.Response(text=f.read()[-5000:])
        return web.Response(status=404)
    async def handle_mutex_rest(self, r):
        return web.json_response({"round_table_lock_exists": os.path.exists(ROUND_TABLE_LOCK)})

# --- Global Instance and MCP Wrappers ---
attendant = LabAttendantV3()
@mcp.tool()
async def lab_heartbeat():
    return await attendant.mcp_heartbeat()
@mcp.tool()
async def lab_start(engine: str = "OLLAMA", model: str = "MEDIUM", disable_ear: bool = True, op_mode: str = "SERVICE_UNATTENDED"):
    return await attendant.mcp_start(engine, model, disable_ear, op_mode)
@mcp.tool()
async def lab_stop():
    return await attendant.mcp_stop()
@mcp.tool()
async def lab_quiesce():
    return await attendant.mcp_quiesce()
@mcp.tool()
async def lab_ignition():
    return await attendant.mcp_ignition()

@mcp.tool()
async def lab_train_adapter(adapter_name: str, steps: int = 60):
    """Perform an autonomous training run for a specific adapter."""
    return await attendant.mcp_train_adapter(adapter_name, steps)

@mcp.tool()
async def lab_wait_ready(timeout: int = 60):
    """Wait for the Lab Hub to reach the READY state."""
    return await attendant.mcp_wait_ready(timeout)

async def run_bilingual():
    # [FEAT-219] Silicon Handshake: Role-Based Execution
    role = os.environ.get("LAB_ATTENDANT_ROLE")
    is_tool = not sys.stdin.isatty()
    
    if role == "MASTER":
        # Full Master Mode: REST API + Pulse + Watchdog
        runner = web.AppRunner(attendant.app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", ATTENDANT_PORT).start()
        logger.info(f"[BOOT] Lab Attendant V3 (Master) active on {ATTENDANT_PORT}")
        asyncio.create_task(attendant.vram_watchdog_loop())
        asyncio.create_task(attendant.pulse_loop())
        
        # If in a TTY, also allow local tools, otherwise just wait
        if sys.stdin.isatty():
            await mcp.run_stdio_async()
        else:
            await asyncio.Event().wait()
    else:
        # Proxy Mode: Tool execution forwards to the Master
        os.environ["LAB_ATTENDANT_ROLE"] = "PROXY" 
        await mcp.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(run_bilingual())
