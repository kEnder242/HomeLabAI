import os
import subprocess
import json
import asyncio
import datetime
import logging
import psutil
import aiohttp
import hashlib
import re
from aiohttp import web
import time
import uuid
import sys
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
DATA_DIR = os.path.join(LAB_DIR, "data") 
SERVER_LOG = f"{LAB_DIR}/server.log"
ATTENDANT_LOG = f"{LAB_DIR}/attendant.log"
VLLM_SERVER_LOG = f"{LAB_DIR}/vllm_server.log"
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

# [FEAT-180] Resilience Metadata
MONITOR_CONTAINERS = ["field_prometheus", "field_grafana", "field_node_exporter"]

# --- Global State ---
lab_process = None
current_lab_mode = "OFFLINE"
current_model = None
is_hibernating = False
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

# --- Global Singleton Lock ---
def check_singleton():
    lock_file = "/tmp/lab_attendant.lock"
    try:
        if os.path.exists(lock_file):
            with open(lock_file, "r") as f:
                pid_str = f.read().strip()
                if pid_str:
                    pid = int(pid_str)
                    if psutil.pid_exists(pid):
                        print(f"[FATAL] Lab Attendant already running as PID {pid}. Aborting.")
                        sys.exit(0)
    except Exception:
        pass

    # Atomic Reclaim
    try:
        with open(lock_file + ".tmp", "w") as f:
            f.write(str(os.getpid()))
        os.replace(lock_file + ".tmp", lock_file)
    except Exception as e:
        print(f"[ERROR] Failed to establish singleton lock: {e}")

# --- Silicon Telemetry (NVML) ---
try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_ACTIVE = True
except Exception as e:
    _NVML_ACTIVE = False
    print(f"[BOOT] NVML Initialization failed (Hardware/Driver missing): {e}")

# --- FastMCP Server ---
mcp = FastMCP("Acme Lab Attendant", dependencies=["mcp", "psutil", "aiohttp", "pynvml"])

@web.middleware
async def key_middleware(request, handler):
    """[FEAT-219] Silicon Handshake: Validates the Lab Key (Query or Header)."""
    # Allow OPTIONS for CORS
    if request.method == "OPTIONS":
        return web.Response(status=200)
        
    # Heartbeat and Ping are public-read for the dashboard
    if any(request.path.endswith(p) for p in ["/heartbeat", "/ping", "/mutex", "/wait_ready"]):
        return await handler(request)

    expected_key = get_style_key()
    provided_key = request.query.get("key") or request.headers.get("LabKey") or request.headers.get("X-Lab-Key")

    # [FEAT-252] Dynamic Auth: Allow either the STYLE_HASH or the current SESSION_TOKEN
    attendant_instance = request.app.get('attendant')
    session_token = attendant_instance.session_token if attendant_instance else None
    
    if provided_key not in [expected_key, session_token]:
        # [FEAT-267] Header-Dump for Debugging Cloudflare/CORS issues
        forwarded = request.headers.get("X-Forwarded-For", "Direct")
        ua = request.headers.get("User-Agent", "Unknown")
        logger.warning(f"[SECURITY] 401 Unauthorized: {request.method} {request.path} | Key: {provided_key} | IP: {request.remote} | Fwd: {forwarded} | UA: {ua}")
        return web.json_response({"status": "error", "message": "Invalid Lab Key. Unauthorized."}, status=401)
    
    return await handler(request)

@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Lab-Key'
    return response

class LabAttendantV4:
    def __init__(self):
        self.app = web.Application(middlewares=[cors_middleware, key_middleware])
        self.app['attendant'] = self # [FIX] Register for middleware access
        
        # [SERVICE] Control & Monitoring Endpoints (Dual-Registration for Option B)
        self.register_route("POST", "/start", self.handle_start_rest)
        self.register_route("POST", "/stop", self.handle_stop_rest)
        self.register_route("POST", "/quiesce", self.handle_quiesce_rest)
        self.register_route("POST", "/ignition", self.handle_ignition_rest)
        self.register_route("POST", "/refresh", self.handle_ignition_rest)
        self.register_route("POST", "/train", self.handle_train_rest)
        self.register_route("POST", "/hibernate", self.handle_hibernate_rest)
        self.register_route("POST", "/hard_reset", self.handle_stop_rest)
        self.register_route("GET", "/heartbeat", self.handle_heartbeat_rest)
        self.register_route("GET", "/status", self.handle_heartbeat_rest) # [FIX] Alias for backward compatibility
        self.register_route("GET", "/ping", self.handle_ping_rest)
        self.register_route("GET", "/wait_ready", self.handle_wait_ready_rest)
        self.register_route("GET", "/logs", self.handle_logs_rest)
        self.register_route("GET", "/mutex", self.handle_mutex_rest)
        
        # [FEAT-151] Forensic Trace Monitor: Added vLLM Server log
        self.trace_monitor = TraceMonitor([SERVER_LOG, ATTENDANT_LOG, VLLM_SERVER_LOG])
        self.ready_event = asyncio.Event()
        self.ledger_path = os.path.join(LAB_DIR, 'run/active_pids.json')
        self.token_path = os.path.join(LAB_DIR, 'run/session.token')
        self.active_pids = self._load_ledger()
        self.current_reason = "INIT"
        self.session_token = self._load_or_create_token() # [FEAT-220] Persistent Session Identity
        self.vram_config = {}
        self.refresh_vram_config()
        
        # [WD] State Initialization
        self.failure_count = 0
        self.boot_grace_period = 18 # 180 seconds for vLLM weights
        self._last_docker_check = 0 # [FEAT-180.1] Docker Cooldown

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

    def _load_or_create_token(self):
        """[FEAT-220] Persistent Identity: Survives service restarts."""
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, "r") as f:
                    token = f.read().strip()
                    if token:
                        logger.info(f"[BOOT] Adopting persistent session token: {token}")
                        return token
            except Exception:
                pass
        
        # Fallback to new generation
        token = uuid.uuid4().hex[:8]
        try:
            with open(self.token_path, "w") as f:
                f.write(token)
            logger.info(f"[BOOT] Created new persistent session token: {token}")
        except Exception as e:
            logger.error(f"[BOOT] Failed to persist token: {e}")
        return token

    def handle_sigterm(self, sig, frame):
        """[FEAT-119.5] Synchronous Signal Guard: Blocks exit until silicon is reaped."""
        logger.warning(f"[SIGNAL] Received Signal {sig}. Executing synchronous silicon purge...")
        # Use a new loop or the existing one to run the cleanup
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                loop.create_task(self.cleanup_silicon(mode="SESSION"))
            else:
                loop.run_until_complete(self.cleanup_silicon(mode="SESSION"))
        except Exception as e:
            # Emergency fallback: subshell kill
            logger.error(f"[SIGNAL] Async purge failed, falling back to emergency reap: {e}")
            subprocess.run(["sudo", "fuser", "-k", "9999/tcp", "8765/tcp", "8088/tcp", "11434/tcp"], stderr=subprocess.DEVNULL)
        
        logger.warning("[SIGNAL] Purge complete. Exiting.")
        sys.exit(0)

    # --- Pager Helper ---
    def log_event(self, message, severity="INFO"):
        """Appends a milestone event to the interleaved Forensic Ledger."""
        try:
            alert = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "LabAttendant",
                "severity": severity,
                "message": f"[{self.session_token}] {message}"
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
            # [FEAT-282.6] Passive Pulsing: Continue VRAM telemetry even when hibernating
            await self.update_status_json()
            await asyncio.sleep(2)

    # --- Proxy Helper ---
    async def _proxy_request(self, method, endpoint, data=None, retries=5):
        """[FEAT-258] Resilient Proxy: Redirects tool calls with automatic retry backoff."""
        key = get_style_key()
        connector = "&" if "?" in endpoint else "?"
        url = f"http://127.0.0.1:{ATTENDANT_PORT}/{endpoint}{connector}key={key}"
        
        for i in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    if method == "POST":
                        async with session.post(url, json=data, timeout=5) as r:
                            return await r.json()
                    else:
                        async with session.get(url, timeout=5) as r:
                            return await r.json()
            except Exception as e:
                if i == retries - 1:
                    return {"status": "error", "message": f"Proxy connection to Master failed after {retries} attempts: {e}"}
                await asyncio.sleep(2) # Settling window for Master boot

    def _save_ledger(self):
        """[FEAT-277] Persist Sovereign Ledger to disk."""
        ledger = {
            "authority": {
                "token": self.session_token,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "boot_hash": _BOOT_HASH
            },
            "inventory": self.active_pids
        }
        atomic_write_json(self.ledger_path, ledger)

    def _load_ledger(self):
        """[FEAT-277] Load Sovereign Ledger from disk."""
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, 'r') as f:
                    data = json.load(f)
                    if "inventory" in data:
                        return data["inventory"]
                    return data
            except Exception:
                pass
        return {'hub_pid': None, 'engine_pid': None, 'engine_mode': None, 'family': []}

    # --- Family Sovereignty ---
    def sync_family_ledger(self):
        """[FEAT-220.4] Family Sovereignty: Recursively discovers and authorizes child processes."""
        new_family = set()
        # Include current and known PIDs
        target_pids = [os.getpid(), self.active_pids.get('hub_pid'), self.active_pids.get('engine_pid')]
        
        for pid in target_pids:
            if pid and psutil.pid_exists(pid):
                new_family.add(pid)
                try:
                    proc = psutil.Process(pid)
                    for child in proc.children(recursive=True):
                        new_family.add(child.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        self.active_pids['family'] = list(new_family)
        self._save_ledger()

    # --- MCP Tools Implementation ---
    async def mcp_heartbeat(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("GET", "heartbeat")
        vitals = await self._get_current_vitals()
        
        # [FEAT-249.1] Report Hibernation Status: Engines OFFLINE while Hub is ONLINE
        if vitals.get("brain") == "OFFLINE" and is_hibernating:
            vitals["mode"] = "HIBERNATING"
            
        vitals["fingerprint"] = get_fingerprint()
        vitals["timestamp"] = datetime.datetime.now().isoformat()
        return vitals

    async def mcp_start(self, engine: str = "OLLAMA", model: str = "MEDIUM", disable_ear: bool = True, op_mode: str = "SERVICE_UNATTENDED", engine_only: bool = False, reason: str = "UNSPECIFIED"):
        global current_lab_mode, current_model, lab_process, is_hibernating
        
        # [FIX] Force immediate state flush to allow restoration to proceed
        is_hibernating = False
        self.ready_event.clear()
        self.current_reason = reason
        # We set mode early to ensure heartbeat reflects the TARGET engine immediately
        current_lab_mode = engine 
        
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "start", {
                "engine": engine, "model": model, "disable_ear": disable_ear, 
                "op_mode": op_mode, "engine_only": engine_only, "reason": reason
            })
        
        # [FEAT-119.4] Non-Destructive Restoration
        # If we are only starting engines, we MUST NOT purge port 8765.
        logger.info(f"[{self.session_token}] [IGNITION] [{reason.upper()}] Starting {model} via {engine} (EngineOnly: {engine_only})")
        
        if not engine_only:
            await self.cleanup_silicon(mode="ORPHANS", engine_only=engine_only)
        else:
            # Selective Cleanup: Only purge engine ports to avoid self-reaping
            for port in [8088, 11434]:
                try:
                    subprocess.run(["sudo", "fuser", "-k", "-n", "tcp", str(port)], stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            await asyncio.sleep(1.0)


        self.refresh_vram_config() # Reload latest model mappings
        
        # Resolve model path and config from map
        model_map = self.vram_config.get("model_map", {})
        tier_config = model_map.get(model, model_map.get("UNIFIED", {}))
        
        target_model = tier_config.get("vllm" if engine == "VLLM" else "ollama", model)
        utilization = tier_config.get("gpu_memory_utilization", 0.4)

        # [FEAT-262] Fast Wake Path: If already hibernating, just wake up
        if current_lab_mode == "HIBERNATING" and engine == "VLLM":
            logger.info(f"[IGNITION] [{reason.upper()}] Fast Wake triggered for hibernating vLLM.")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post("http://127.0.0.1:8088/wake_up", timeout=5.0) as r:
                        if r.status == 200:
                            current_lab_mode = op_mode
                            self.ready_event.set()
                            logger.info("[WAKE] vLLM successfully woken from sleep.")
                            return {"status": "success", "message": "vLLM woken from sleep mode."}
            except Exception as e:
                logger.warning(f"[WAKE] Fast-wake failed, proceeding with full ignition: {e}")

        current_lab_mode = op_mode
        current_model = target_model
        # [FEAT-255.1] Export state with Reason
        try:
            with open(os.path.join(DATA_DIR, "status.json"), "w") as f:
                json.dump({
                    "mode": engine, 
                    "model": target_model, 
                    "reason": reason,
                    "session": self.session_token,
                    "timestamp": time.time()
                }, f)
        except Exception:
            pass

        
        # [FEAT-259.2] Fast STUB: Skip physical silicon gates for logic testing
        if engine == "STUB":
            logger.info(f"[{self.session_token}] [IGNITION] STUB mode active. Bypassing physical gates.")
            current_lab_mode = "STUB" # [FIX] Ensure mode is updated for vitals
            is_hibernating = False
            self.ready_event.set() # Instant Ready
            if engine_only:
                return {"status": "success", "message": "STUB engine sparked."}

        # 1. Resolve Required Memory [FEAT-254]
        used_now, total_vram = await self._get_vram_info()
        required_mb = int(total_vram * utilization)
        
        # [FIX] VRAM Guard: Skip if in STUB mode
        if engine != "STUB" and (total_vram - used_now) < required_mb:
            msg = f"SILICON_CONGESTION: {total_vram - used_now}MB free < {required_mb}MB required."
            logger.error(f"[{self.session_token}] {msg}")
            self.log_event(msg, severity="ERROR")
            return {"status": "error", "message": msg, "metrics": {"free": total_vram - used_now, "required": required_mb}}

        # 3. [FEAT-254] The Assassin Audit: Settling Window
        await asyncio.sleep(5.0)
        
        # 4. [FEAT-254.1] The Physical Audit Gate
        used_post, _ = await self._get_vram_info()
        free_mb = total_vram - used_post
        
        if free_mb < required_mb:
            msg = f"SILICON_CONGESTION: {free_mb}MB free < {required_mb}MB required."
            logger.error(f"[IGNITION] {msg}")
            self.log_event(msg, severity="ERROR")
            return {
                "status": "error", 
                "message": msg,
                "metrics": {"free": free_mb, "required": required_mb}
            }

        self.ready_event.clear()
        self.trace_monitor.refresh_marks()
        # [FEAT-255.2] State Clearance: Explicitly reset the Hub's READY signal in the log
        logger.info("[WATCHDOG] Clearing Hub READY state for engine transition.")
        
        env = os.environ.copy()
        env["LAB_MODE"] = str(engine)
        # [FEAT-220] Silicon Handshake: Inject Immunity Token into all spawned families
        env["LAB_IMMUNITY_TOKEN"] = str(self.session_token)
        
        if disable_ear:
            env["DISABLE_EAR"] = "1"
        
        # Sanitize: subprocess.Popen requires all env values to be strings and not None
        env = {k: str(v) for k, v in env.items() if v is not None}
        
        if engine == "VLLM":
            # [SPR-13.0] Verified Stable Config for Turing (RTX 2080 Ti)
            env["NCCL_P2P_DISABLE"] = "1"
            env["NCCL_SOCKET_IFNAME"] = "lo"
            env["VLLM_SERVER_DEV_MODE"] = "1" # [FEAT-262] Required for Extended Debug Endpoints
            env["VLLM_USE_V1"] = "0" # [PLACEBO] Maintain legacy alignment
            
            # [BKM] Consolidate into EXTRA_ARGS for the script to consume
            # Stable Recipe R2: 0.5 util and 4096 context with verified LoRA mounts
            LORA_STR = "--enable-lora --max-loras 4 --lora-modules lab_sentinel_v1=/speedy/models/adapters/lab_sentinel_v1 cli_voice_v1=/speedy/models/adapters/cli_voice_v1 shadow_brain_v2=/speedy/models/adapters/shadow_brain_v2 lab_history_v1=/speedy/models/adapters/lab_history_v1"
            env["VLLM_EXTRA_ARGS"] = f"--gpu-memory-utilization 0.5 --enforce-eager --attention-backend TRITON_ATTN --max-model-len 4096 --enable-sleep-mode {LORA_STR}"
            
            logger.info(f"[VLLM] Igniting Sovereign Node (Recipe R2): {target_model}")
            self.log_event(f"Ignition [{reason.upper()}]: {engine}/{target_model}")
            
            # [DUMB_IGNITION] Bash script handles the backgrounding. We don't hold the process object.
            subprocess.Popen(["bash", VLLM_START_PATH, target_model, sys.executable], 
                             env=env, cwd=LAB_DIR, start_new_session=True)
            
            # [FEAT-277] Shell-Side PID Tracking
            await asyncio.sleep(5) # Allow script to write PID
            try:
                pid_path = os.path.join(LAB_DIR, "run/vllm.pid")
                if os.path.exists(pid_path):
                    with open(pid_path, "r") as f:
                        vllm_pid = int(f.read().strip())
                        self.active_pids['engine_pid'] = vllm_pid
                        self.active_pids['engine_mode'] = 'VLLM'
                        # [FEAT-220.5] Immediate Immunity
                        if vllm_pid not in self.active_pids.get('family', []):
                            self.active_pids['family'].append(vllm_pid)
                        self._save_ledger()
            except Exception:
                pass
            
            # [FEAT-281.2] Cognitive Readiness Gate
            await self._wait_for_vllm_cognitive()
        elif engine == "OLLAMA":
            # [SPR-13.0] OLLAMA Fallback
            logger.info(f"[OLLAMA] Launching Fallback Node: {target_model}")
            self.log_event(f"Ignition [{reason.upper()}]: {engine}/{target_model} (Mode: {op_mode})")
            proc = subprocess.Popen(["ollama", "run", target_model], env=env, start_new_session=True)
            self.active_pids['engine_pid'] = proc.pid
            self.active_pids['engine_mode'] = 'OLLAMA'
            self._save_ledger()
        elif engine == "STUB":
            self.log_event(f"Ignition [{reason.upper()}]: STUB (Mode: {op_mode})")
            # No physical subprocess needed for STUB engine
            pass

        # [FEAT-250] Surgical Ignition: Only skip Hub if it is already running AND immune
        hub_active = False
        try:
            res = subprocess.check_output(["sudo", "fuser", "8765/tcp"], stderr=subprocess.STDOUT, text=True)
            if ":" in res:
                pids = res.split(":")[1].strip().split()
                if pids:
                    pid = int(pids[0])
                    if self._is_current_session_process(pid):
                        hub_active = True
                        logger.info(f"[IGNITION] Immune Hub detected on PID {pid}. Sparing.")
                    else:
                        logger.warning(f"[IGNITION] Reaping non-immune orphan on port 8765 (PID: {pid})")
                        try:
                            os.killpg(os.getpgid(pid), signal.SIGKILL)
                        except Exception:
                            pass
                        await asyncio.sleep(1.0)
        except Exception:
            pass

        if engine_only and hub_active:
            logger.info("[IGNITION] Surgical Spark complete. Foyer spared.")
            return {"status": "success", "message": "Engines sparked. Hub spared."}

        # [FEAT-276.5] The Sequencer: Mandatory Engine-First Ignition
        if engine == "VLLM":
            logger.info(f"[{self.session_token}] [SEQUENCER] Waiting for Engine API (8088) to stabilize...")
            engine_ready_port = False
            for i in range(60): # 120s total wait
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get("http://127.0.0.1:8088/v1/models", timeout=1.0) as r:
                            if r.status == 200:
                                engine_ready_port = True
                                logger.info(f"[{self.session_token}] [SEQUENCER] Engine API confirmed after {i*2}s.")
                                break
                except Exception:
                    pass
                await asyncio.sleep(2)
            
            if not engine_ready_port:
                logger.error(f"[{self.session_token}] [SEQUENCER] Engine failed to bind port 8088. Aborting foyer spark.")
                return {"status": "error", "message": "Engine failed to bind port 8088."}

        # Start Hub
        logger.info(f"[IGNITION] [{reason.upper()}] Igniting Hub foyer...")
        cmd = [sys.executable, LAB_SERVER_PATH, "--mode", op_mode]
        if disable_ear:
            cmd.append("--disable-ear")
        
        # [FEAT-213] Engine Warm-up Delay (Reduced for speed)
        await asyncio.sleep(2.0)
        
        with open(SERVER_LOG, "a", buffering=1) as log_f:
            lab_process = subprocess.Popen(cmd, cwd=LAB_DIR, env=env, stderr=log_f, start_new_session=True)
            self.active_pids['hub_pid'] = lab_process.pid
            self._save_ledger()
            
        asyncio.create_task(self.log_monitor_loop())
        logger.info(f"[IGNITION] Hub process spawned with PID: {lab_process.pid} (Immunity: {_BOOT_HASH})")
        return {"status": "success", "message": f"Ignited {model} via {engine} in mode {op_mode}"}

    async def mcp_stop(self, reason="MANUAL"):
        """[FEAT-119] Atomic Stop: Maintenance Lock -> Silicon Purge."""
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "stop", {"reason": reason})

        self.current_reason = reason
        logger.warning(f"[{self.session_token}] [STOP] Manual stop initiated (Reason: {reason}).")

        # [NUCLEAR RESET] Force immediate and recursive cleanup
        await self.cleanup_silicon(mode="SESSION")

        # [FEAT-277] Clear Ledger on Stop
        self.active_pids = {'hub_pid': None, 'engine_pid': None, 'engine_mode': None}
        self._save_ledger()

        global current_lab_mode, is_hibernating
        current_lab_mode = "OFFLINE"
        is_hibernating = False
        self.ready_event.clear()

        await self.update_status_json(f"OFFLINE ({reason})")
        return {"status": "success", "message": "Lab stopped and silicon scrubbed."}


    async def mcp_hibernate(self, reason: str = "IDLE_TIMEOUT"):
        """[FEAT-262] Eureka Hibernation: Level 2 offload with 100% Graceful requirement."""
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "hibernate", {"reason": reason})

        global is_hibernating, current_lab_mode
        logger.warning(f"[{self.session_token}] [HIBERNATE] Transitioning to Deep Sleep (Reason: {reason})")
        
        # 1. [QUIET WINDOW] Suspend pulse loop to prevent API contention during offload
        self.ready_event.clear()
        
        # 2. Attempt Level 2 Graceful Offload
        success = False
        try:
            async with aiohttp.ClientSession() as session:
                # [FEAT-282] Clear prefix cache before offload
                await session.post("http://127.0.0.1:8088/reset_prefix_cache", timeout=2.0)
                
                # Full weight offload (Level 2)
                # [BKM] Increased timeout to 30s for Z87 PCIe latency
                async with session.post("http://127.0.0.1:8088/sleep?level=2", timeout=30.0) as r:
                    if r.status == 200:
                        logger.warning(f"[{self.session_token}] [SLEEP] vLLM accepted Level 2 offload signal.")
                        success = True
                    else:
                        err_body = await r.text()
                        # [FEAT-283.3] Forensic Hibernation Logging (ERR-09)
                        logger.error(f"[{self.session_token}] [SLEEP] Level 2 rejected ({r.status}): {err_body}")
        except Exception as e:
            logger.error(f"[{self.session_token}] [SLEEP] Offload signal failed: {e}")

        if success:
            current_lab_mode = "HIBERNATING"
            is_hibernating = True
            
            # 3. [FEAT-249.3] Forensic Monitoring: Wait up to 90s for VRAM drop
            # weights (~2.3GB) + KV Cache should move to CPU
            start_vram, _ = await self._get_vram_info()
            logger.info(f"[HIBERNATE] Monitoring offload curve. Starting VRAM: {start_vram}MB")
            
            reclaimed = False
            for i in range(18): # 90s total
                await asyncio.sleep(5)
                used, _ = await self._get_vram_info()
                logger.info(f"  [*] VRAM Check {i+1}/18: {used}MB")
                if used < 3500: # Target: Weights unmapped
                    logger.info(f"[{self.session_token}] [HIBERNATE] VRAM reclamation verified at {used}MB.")
                    reclaimed = True
                    break
            
            if not reclaimed:
                logger.warning(f"[{self.session_token}] [HIBERNATE] VRAM STALL: Weights remained in silicon after 90s.")
            
            await self.update_status_json("HIBERNATING (VRAM Free)" if reclaimed else "HIBERNATING (STALLED)")
            return {"status": "success", "message": "Soft hibernation active."}
        else:
            # [MEMORIAL] Deprecated Sprint 16 Atomic Reap
            # [FEAT-259] The Butler Pattern: Surgical session-based reaping
            # # We previously killed the engine PGID here to guarantee VRAM reclamation
            # # This is now DISABLED to preserve the V1 process state.
            # await self.cleanup_silicon(mode="SESSION", engine_only=True)
            
            current_lab_mode = "HIBERNATING"
            is_hibernating = True
            await self.update_status_json("HIBERNATING (SIGNAL_FAILED)")
            return {"status": "error", "message": "Hibernation signal failed. No reap performed."}

    async def mcp_quiesce(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "quiesce")
        logger.warning("[QUIESCE] Lockdown initiated. Setting maintenance lock.")
        self.log_event("Quiesce: Lab locked for maintenance.", severity="WARNING")
        with open(MAINTENANCE_LOCK, "w") as f:
            f.write(datetime.datetime.now().isoformat())
        asyncio.create_task(self._deferred_cleanup("MAINTENANCE MODE (Locked)"))
        return {"status": "locked", "message": "Lab freezing. Watchdog passive."}

    async def mcp_ignition(self, reason: str = "MANUAL_IGNITION"):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "ignition", {"reason": reason})
        
        # [FEAT-213] Re-Ignition must clear the maintenance lock first
        if os.path.exists(MAINTENANCE_LOCK):
            os.remove(MAINTENANCE_LOCK)
            self.log_event("Ignition: Maintenance lock cleared.")
            
        # [SPR-13.0] Restoration using current state or defaults
        engine = os.environ.get("LAB_MODE", "OLLAMA")
        model = os.environ.get("LAB_MODEL", "MEDIUM")
        disable_ear = os.environ.get("DISABLE_EAR") == "1"
        
        return await self.mcp_start(engine, model, disable_ear, "SERVICE_UNATTENDED", reason=reason)

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

    async def mcp_wait_ready(self, timeout: int = 480):
        """[FEAT-136] Blocking wait for the Lab Hub to reach the READY state with Forensic detection."""
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("GET", f"wait_ready?timeout={timeout}")

        start_t = time.time()

        # [FIX] Immediate check: If already operational, return success
        vitals = await self._get_current_vitals()
        if vitals.get("operational"):
            logger.info(f"[{self.session_token}] [WATCHDOG] Lab already operational. Bypassing wait.")
            return {"status": "init", "message": "Lab is operational."}

        # [FEAT-251.2] Forensic Wait
        while time.time() - start_t < timeout:
            # 1. Physical/Cognitive Probe
            vitals = await self._get_current_vitals()
            if vitals.get("operational"):
                logger.info(f"[{self.session_token}] [WATCHDOG] Lab reached OPERATIONAL after {int(time.time()-start_t)}s")
                return {"status": "init", "message": "Lab is operational."}
            
            # 2. Check for Hub crashes in log
            if os.path.exists(SERVER_LOG):
                try:
                    def read_log():
                        with open(SERVER_LOG, "r") as f:
                            f.seek(0, 2)
                            if f.tell() > 2000:
                                f.seek(-2000, 2)
                            return f.readlines()
                    
                    lines = await asyncio.to_thread(read_log)
                    if any("Traceback" in line or "SyntaxError" in line for line in lines):
                        logger.error(f"[{self.session_token}] [WATCHDOG] Hub crash detected in logs.")
                        return {"status": "crashed", "message": "Hub foyer crashed during ignition."}
                except Exception:
                    pass

            await asyncio.sleep(5)
            
        return {"status": "timeout", "message": f"Lab failed to reach functional READY within {timeout}s"}

    async def cleanup_silicon(self, mode="ORPHANS", engine_only=False):
        """
        [FEAT-119] Broad-Spectrum Assassin: Reclaim hardware handles.
        Handshake Protocol: Processes tagged with [TOKEN] in their title are immune.
        """
        immune_pgids = {os.getpgid(os.getpid())}
        target_pgids = set()
        
        # 1. Target Definition
        ports = [8088, 11434, 8765]
        targets = ["vllm", "ollama", "enginecore", "acme_lab.py", "archive_node.py", "pinky_node.py", "brain_node.py"]

        # 2. First Pass: Handshake Discovery (Title-based)
        for proc in psutil.process_iter(["pid", "name", "cmdline", "environ", "create_time"]):
            try:
                pid = proc.info["pid"]
                pgid = os.getpgid(pid)
                cmd = " ".join(proc.info["cmdline"] or []).lower()
                p_name = str(proc.info["name"] or "").lower()
                
                # [FEAT-275] Grace Window: Spare processes less than 10s old
                if (time.time() - proc.info["create_time"]) < 10.0:
                    immune_pgids.add(pgid)
                    continue

                # [FEAT-220] Silicon Handshake: Search for token in title/cmdline/env
                is_immune = False
                if f"{self.session_token}" in cmd or f"{self.session_token}" in p_name:
                    is_immune = True
                # Format: [HUB:f5e8f53] or [PINKY:f5e8f53]
                elif "[HUB:" in p_name:
                    is_immune = True
                else:
                    try:
                        env = proc.info["environ"] or {}
                        if env.get("LAB_IMMUNITY_TOKEN") == self.session_token:
                            is_immune = True
                    except Exception:
                        pass

                if is_immune:
                    immune_pgids.add(pgid)
                    continue
                
                # Agentic Immunity (Env-based)
                env = proc.info["environ"] or {}
                if env.get("GEMINI_CLI_IMMUNITY") == "1":
                    immune_pgids.add(pgid)
                    continue

                # Identify potential targets
                if any(t in cmd or t in p_name for t in targets):
                    target_pgids.add(pgid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
                continue

        # 3. Second Pass: Port-Based Discovery
        active_ports = set()
        for port in ports:
            try:
                res = subprocess.check_output(["sudo", "fuser", f"{port}/tcp"], stderr=subprocess.STDOUT, text=True)
                if res:
                    active_ports.add(port)
                for line in res.split("\n"):
                    if ":" in line:
                        pids = line.split(":")[1].strip().split()
                        for p in pids:
                            try:
                                pgid = os.getpgid(int(p))
                                # Add to kill list if it's an engine port OR not immune
                                if port != 8765 or pgid not in immune_pgids:
                                    target_pgids.add(pgid)
                            except Exception:
                                pass
            except Exception:
                pass

        # 4. [FEAT-278] VRAM Truth: Correlate VRAM usage to PID Ledger
        if mode == "SESSION":
            try:
                # Query PIDs using GPU memory
                smi_cmd = ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"]
                smi_out = subprocess.check_output(smi_cmd, text=True, stderr=subprocess.DEVNULL)
                
                for line in smi_out.strip().split('\n'):
                    if not line.strip():
                        continue
                    v_pid_str, v_mem_str = line.split(',')
                    v_pid = int(v_pid_str.strip())
                    v_mem = int(v_mem_str.strip())
                    
                    # If process is using > 1GB and NOT in our ledger, it is an orphan
                    is_ours = (v_pid == self.active_pids.get('engine_pid') or v_pid == self.active_pids.get('hub_pid'))
                    
                    if v_mem > 1000 and not is_ours:
                        logger.warning(f"[{self.session_token}] [ASSASSIN] VRAM TRUTH: Reaping high-memory orphan {v_pid} ({v_mem}MB)")
                        try:
                            # Force individual kill first
                            os.kill(v_pid, signal.SIGKILL)
                            target_pgids.add(os.getpgid(v_pid))
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"[ASSASSIN] VRAM Truth audit failed: {e}")

        # 5. [FEAT-276.1] Signature-Based Discovery (Recursive Scrub)
        # We search ALL user processes for the vLLM/Ollama signature
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info["cmdline"] or []).lower()
                p_name = str(proc.info["name"] or "").lower()
                pid = proc.info["pid"]
                
                # Identify rogue engines by signature
                if any(t in cmd or t in p_name for t in ["vllm", "enginecore", "ollama"]):
                    pgid = os.getpgid(pid)
                    if pgid not in immune_pgids:
                        logger.warning(f"[{self.session_token}] [ASSASSIN] Reaping non-immune engine {pid} ({p_name})")
                        try:
                            os.kill(pid, signal.SIGKILL)
                            target_pgids.add(pgid)
                        except Exception:
                            pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 5. Final Purge Logic
        # [FEAT-119.3] Restoration Silence
        is_igniting = (engine_only or self.current_reason.startswith("RESTORE_") or self.current_reason == "SAFE_PILOT")
        if mode == "ORPHANS" and is_igniting:
            logger.info(f"[{self.session_token}] [ASSASSIN] Active ignition window ({self.current_reason}). Skipping orphan purge.")
            return

        # [FEAT-276.6] Targeted Device Reaper: Surgical release of GPU handles
        # We query the device users but filter them strictly to avoid killing Xorg/Gnome.
        if mode == "SESSION" and not is_igniting:
            logger.info(f"[{self.session_token}] [ASSASSIN] Performing targeted device audit on /dev/nvidia0")
            try:
                # Get PIDs using the GPU
                res = subprocess.check_output(["sudo", "fuser", "/dev/nvidia0"], stderr=subprocess.DEVNULL, text=True)
                # Output format is usually "/dev/nvidia0:  PID1 PID2..."
                gpu_pids = res.split(":")[-1].strip().split()
                
                for pid_str in gpu_pids:
                    try:
                        pid = int(re.sub(r'[^0-9]', '', pid_str))
                        proc = psutil.Process(pid)
                        p_name = proc.name().lower()
                        cmd = " ".join(proc.cmdline() or []).lower()
                        
                        # SAFETY GATE: Never kill system/GUI processes
                        if any(sys_proc in p_name for sys_proc in ["xorg", "gnome", "mutter", "sunshine", "steam"]):
                            continue
                            
                        # TARGET GATE: Is it a Lab process or a known engine?
                        is_lab = self.session_token in cmd or self.session_token in p_name
                        is_engine = any(t in cmd or t in p_name for t in ["vllm", "enginecore", "ollama"])
                        
                        if is_lab or is_engine:
                            pgid = os.getpgid(pid)
                            if pgid not in immune_pgids:
                                logger.warning(f"[{self.session_token}] [ASSASSIN] Device Reaper targeting {pid} ({p_name})")
                                target_pgids.add(pgid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
                        pass
            except Exception as e:
                logger.error(f"[{self.session_token}] [ASSASSIN] Device audit failed: {e}")

        final_kill_list = target_pgids - immune_pgids

        if final_kill_list:
            logger.warning(f"[{self.session_token}] [ASSASSIN] [{mode}] Purging non-immune groups: {final_kill_list}")
            for pgid in final_kill_list:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass
        
        await asyncio.sleep(1.0)

    def _is_current_session_process(self, pid):
        """Returns True if the process (or its parent) carries the current session token."""
        try:
            if pid == os.getpid():
                return False
            proc = psutil.Process(pid)
            
            # 1. Recursive Search: Check self and parents
            curr = proc
            while curr:
                try:
                    env = curr.environ()
                    if env.get("LAB_IMMUNITY_TOKEN") == self.session_token:
                        return True
                    if env.get("GEMINI_CLI_IMMUNITY") == "1":
                        return True
                except Exception:
                    pass
                curr = curr.parent()
                
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _is_stale_process(self, pid):
        """[FEAT-220] Checks if a process carries an OLD or MISSING Diplomatic Immunity token."""
        try:
            if pid == os.getpid():
                return False
            proc = psutil.Process(pid)
            # Check environment for the current boot hash
            env = proc.environ()
            token = env.get("LAB_IMMUNITY_TOKEN")
            
            # If token matches the current session, it is IMMUNE (SPARE)
            if token == self.session_token:
                logger.info(f"[ASSASSIN] Sparing immune process {pid} ({proc.name()})")
                return False
                
            # If token is different, or token is missing, it is STALE (KILL)
            # This ensures we clean up "orphans" from previous manual runs or crashes
            if token:
                logger.warning(f"[ASSASSIN] Targeting stale process {pid} ({proc.name()}) with old token {token}")
            else:
                logger.warning(f"[ASSASSIN] Targeting non-immune orphan process {pid} ({proc.name()})")
            
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return False

    async def scavenge_reality(self):
        """[FEAT-220.1] Physical Scavenging: Adopts existing engines or reaps stale ones."""
        logger.info("[BOOT] Performing physical scavenging audit...")
        
        # 1. Identity Validation: Check the existing ledger's authority
        stale_family = []
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, 'r') as f:
                    data = json.load(f)
                    ledger_token = data.get("authority", {}).get("token")
                    if ledger_token and ledger_token != self.session_token:
                        logger.warning(f"[BOOT] Session mismatch! Ledger token {ledger_token} is STALE. Marking family for purge.")
                        stale_family = data.get("inventory", {}).get("family", [])
            except Exception:
                pass

        # 2. Stale Identity Purge [Task 22]
        if stale_family:
            logger.warning(f"[BOOT] Purging {len(stale_family)} stale survivors from previous session.")
            for pid in stale_family:
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
            await asyncio.sleep(1.0) # Wait for release

        ports = {8088: "VLLM", 11434: "OLLAMA", 8765: "HUB"}
        adopted_count = 0

        # 3. Physical Port Sweep (Adoption)
        for port, mode in ports.items():
            try:
                res = subprocess.check_output(["sudo", "fuser", f"{port}/tcp"], stderr=subprocess.STDOUT, text=True)
                if ":" in res:
                    pids = res.split(":")[1].strip().split()
                    for pid_str in pids:
                        pid = int(pid_str)
                        if self._is_current_session_process(pid):
                            logger.info(f"[BOOT] Adopting existing {mode} on PID {pid}.")
                            if mode == "HUB":
                                self.active_pids['hub_pid'] = pid
                            else:
                                self.active_pids['engine_pid'] = pid
                                self.active_pids['engine_mode'] = mode
                            adopted_count += 1
            except Exception:
                pass
        
        if adopted_count > 0:
            self.sync_family_ledger() # Recursively authorize the adopted family
            logger.info(f"[BOOT] Successfully adopted {adopted_count} nodes into the Immunity Ledger.")
            
            # [FEAT-220.3] State Reconstruction
            global current_lab_mode
            current_lab_mode = self.active_pids.get('engine_mode', "SERVICE_UNATTENDED")
            
            vitals = await self._get_current_vitals()
            if vitals.get("operational"):
                logger.info("[BOOT] Lab confirmed OPERATIONAL. Setting READY event.")
                self.ready_event.set()
            elif vitals.get("engine_up") and not vitals.get("engine_vocal"):
                global is_hibernating
                is_hibernating = True
                logger.warning("[BOOT] Engine present but silent. Reconstructing HIBERNATING state.")

    async def _get_current_vitals(self):
        """[FEAT-213] Silicon Health Check: Returns consolidated telemetry."""
        foyer_up = False
        engine_up = False
        engine_vocal = False
        
        # [FIX] Cache successful probes to prevent socket contention with nodes
        now = time.time()
        if not hasattr(self, "_last_engine_check"):
            self._last_engine_check = 0
            self._engine_state_cache = False
            self._vocal_state_cache = False

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Physical Probe (Ports)
                try:
                    async with session.get("http://127.0.0.1:8765/heartbeat", timeout=1.0) as r:
                        if r.status == 200:
                            foyer_up = True
                except Exception:
                    pass
                
                # 2. Engine Probes (with TTL and Hibernation Guard)
                is_igniting = (self.current_reason.startswith("RESTORE_") or self.current_reason.startswith("GAUNTLET_") or self.current_reason == "SAFE_PILOT" or self.current_reason == "MANUAL_IGNITION")
                
                if is_hibernating:
                    # [FEAT-282.6] Passive Mode: Don't poke the engine if it's supposed to be asleep
                    engine_up = False
                    engine_vocal = False
                elif is_igniting or (now - self._last_engine_check > 30): # 30s TTL
                    # Direct Port Probe (Fallback)
                    port = 8088 if current_lab_mode == "VLLM" else 11434
                    try:
                        async with session.get(f"http://127.0.0.1:{port}/v1/models" if port == 8088 else f"http://127.0.0.1:{port}/api/tags", timeout=1.0) as r:
                            if r.status == 200:
                                engine_up = True
                                self._engine_state_cache = True
                    except Exception:
                        self._engine_state_cache = False
                    
                    # Cognitive Probe (Functional)
                    if self._engine_state_cache and port == 8088:
                        try:
                            # [FIX] Use chat endpoint for V1 engine compatibility
                            payload = {
                                "model": "unified-base", 
                                "messages": [{"role": "user", "content": "Respond with the word SUCCESS."}],
                                "max_tokens": 10,
                                "temperature": 0.0
                            }
                            async with session.post("http://127.0.0.1:8088/v1/chat/completions", json=payload, timeout=5.0) as p:
                                if p.status == 200:
                                    engine_vocal = True
                                    self._vocal_state_cache = True
                        except Exception:
                            self._vocal_state_cache = False
                    
                    self._last_engine_check = now
                else:
                    # Use cache
                    engine_up = self._engine_state_cache
                    engine_vocal = self._vocal_state_cache

        except Exception as e:
            logger.debug(f"[PROBE] Overall probe failed: {e}")

        # [FIX] Final vocal state must be the union of local and cached to ensure 'is_op' is accurate
        engine_vocal = engine_vocal or getattr(self, "_vocal_state_cache", False)
        
        used_mb, total_mb = await self._get_vram_info()
        vram_pct = f"{(used_mb / total_mb * 100):.1f}%" if total_mb > 0 else "0.0%"
        
        # [FEAT-276] Persistent VRAM Telemetry
        logger.info(f"[{self.session_token}] [VRAM_TRACE] {used_mb}MB / {total_mb}MB ({vram_pct}) | Foyer:{foyer_up} Eng:{engine_up} Vocal:{engine_vocal}")

        # [FEAT-265.6] Functional Gate: Strict Cognitive Truth
        # A node is ONLY operational if it is vocal (for VLLM) or physically up (for others)
        is_op = (foyer_up and engine_vocal and not is_hibernating) or (current_lab_mode == "STUB" and foyer_up)
        
        # [BKM] No optimistic overrides. If the engine isn't vocal, we aren't operational.
        
        return {
            "attendant_pid": os.getpid(),
            "mode": current_lab_mode,
            "model": current_model,
            "foyer_up": foyer_up,
            "engine_up": engine_up or current_lab_mode == "STUB",
            "engine_vocal": engine_vocal or current_lab_mode == "STUB",
            "vram": vram_pct,
            "operational": is_op,
            "reason": self.current_reason,
            "session": self.session_token,
            "style_key": get_style_key(),
            "boot_hash": _BOOT_HASH
        }

    async def _get_vram_info(self):
        """[FEAT-213] Silicon Health Check: Returns (used_mb, total_mb)"""
        # 1. Primary Path: pynvml (Fresh Probe)
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            used, total = int(info.used / 1024 / 1024), int(info.total / 1024 / 1024)
            pynvml.nvmlShutdown()
            return used, total
        except Exception:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass

        # 2. Fallback Path: nvidia-smi
        try:
            res = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"],
                text=True,
                stderr=subprocess.DEVNULL
            )
            used, total = map(int, res.strip().split(","))
            return used, total
        except Exception as e:
            logger.error(f"[VRAM] Total probe failure (NVML & SMI): {e}")
            return 0, 0

    async def update_status_json(self, msg=None):
        vitals = await self._get_current_vitals()
        live_data = {
            "status": "ONLINE" if vitals.get("foyer_up") else "OFFLINE",
            "message": msg or ("OPERATIONAL" if vitals.get("operational") else "INIT"),
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
                # [FEAT-259.1] Hibernation Awareness: Skip auto-restart if manually hibernated or in maintenance
                if is_hibernating or os.path.exists(MAINTENANCE_LOCK):
                    await asyncio.sleep(5)
                    continue

                if not lab_process or lab_process.poll() is not None:
                    logger.warning("[WATCHDOG] Lab process ended.")
                    # [FEAT-149.1] Parent-Led Recovery: Auto-bounce only unattended services
                    if current_lab_mode == "SERVICE_UNATTENDED":
                        logger.info("[WATCHDOG] Unattended mode active. Triggering recovery in 5s...")
                        async def _tactical_recovery():
                            await asyncio.sleep(5)
                            await self.mcp_start(engine=os.environ.get("LAB_MODE", "VLLM"), engine_only=True, reason="RECOVERY")
                        asyncio.create_task(_tactical_recovery())
                    break
                
                line = f.readline()
                if not line:
                    await asyncio.sleep(1.0)
                    continue
                
                if "[READY] Hub foyer is fully synchronized." in line:
                    self.ready_event.set()
                    logger.info("[WATCHDOG] Lab reported OPERATIONAL signal.")
                    await self.update_status_json("Mind is OPERATIONAL")
                
                # [FEAT-255.2] Continuous Sentinel: Listen for state resets
                if "Clearing Hub READY state" in line:
                    self.ready_event.clear()
                    logger.warning("[WATCHDOG] Hub READY state cleared for transition.")

    async def _wait_for_vllm_cognitive(self, timeout=240):
        """[FEAT-281.2] Cognitive Readiness: Wait for successful token generation."""
        start_t = time.time()
        logger.info("[VLLM] API is UP. Waiting 60s for Triton kernel residence...")
        await asyncio.sleep(60) # [BKM] Mandatory settle window for 3B AWQ kernels on Turing
        
        logger.info("[VLLM] Beginning cognitive reasoning probes (127.0.0.1:8088)...")
        vllm_log = os.path.join(LAB_DIR, "vllm_server.log")
        
        while time.time() - start_t < timeout:
            # forensic check for crashes
            if os.path.exists(vllm_log):
                try:
                    with open(vllm_log, "r") as f:
                        lines = f.readlines()[-30:]
                        if any(t in line for line in lines for t in ["Traceback", "RuntimeError", "ValueError:"]):
                            logger.error("[VLLM] Fatal engine core crash detected in logs. Aborting.")
                            return False
                except Exception:
                    pass

            try:
                async with aiohttp.ClientSession() as session:
                    # Functional ping (Reasoning Test)
                    payload = {
                        "model": "unified-base",
                        "messages": [{"role": "user", "content": "Respond with the word SUCCESS."}],
                        "max_tokens": 10,
                        "temperature": 0.0
                    }
                    # [FIX] Use chat endpoint for V1 engine compatibility
                    async with session.post("http://127.0.0.1:8088/v1/chat/completions", json=payload, timeout=10.0) as r:
                        if r.status == 200:
                            res = await r.json()
                            if "choices" in res:
                                logger.info(f"[VLLM] Engine is VOCAL and REASONING after {int(time.time() - start_t)}s.")
                                return True
            except Exception as e:
                logger.debug(f"[VLLM] Cognitive probe attempt failed: {e}")
            
            await asyncio.sleep(5)
        
        logger.error(f"[VLLM] Engine failed to reason within {timeout}s.")
        return False

    async def vram_watchdog_loop(self):
        """[SPR-21.0] Multi-Modal State Monitor: Autonomous Triage and Recovery."""
        logger.info("[WATCHDOG] Sovereignty active. Monitoring state transitions.")
        
        # [FEAT-265.6] The Blacklist Law: Only manage what we own
        BLACKLIST = ["vllm", "enginecore", "ollama", "acme_lab.py", "node.py", "archive_node.py", "pinky_node.py", "brain_node.py"]
        
        # 0. Internal Immunity
        attendant_pid = os.getpid()

        while True:
            await asyncio.sleep(10)
            
            # Gating: Respect Maintenance and Boot Windows
            if os.path.exists(MAINTENANCE_LOCK):
                continue
            if self.boot_grace_period > 0:
                self.boot_grace_period -= 1
                continue

            try:
                # 1. Physical VRAM Check [FEAT-036]
                used, total = await self._get_vram_info()
                if total > 0:
                    vram_pct = used / total
                    if vram_pct > 0.98: # Extreme threshold only
                        await self._trigger_recovery("Critical VRAM (>98%)", level=2)
                        continue

                # 2. Blacklist Audit (Physical Truth)
                # [FEAT-278.2] Cautious Reaping: Only audit known hogs
                if used > 2000:
                    try:
                        self.sync_family_ledger()
                        smi_out = subprocess.check_output(
                            ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], 
                            text=True, stderr=subprocess.DEVNULL
                        )
                        physical_pids = [int(p.strip()) for p in smi_out.strip().split("\n") if p.strip()]
                        
                        orphan_found = False
                        for p_pid in physical_pids:
                            if p_pid == attendant_pid:
                                continue

                            try:
                                proc = psutil.Process(p_pid)
                                p_name = proc.name().lower()
                                p_cmd = " ".join(proc.cmdline() or []).lower()
                            except Exception:
                                continue

                            # Is this a process we actually care about?
                            is_blacklisted = any(x in p_name or x in p_cmd for x in BLACKLIST)
                            if not is_blacklisted:
                                continue # IGNORE EVERYTHING ELSE (Xorg, Sunshine, etc.)

                            # [FEAT-220.4] Immunity Check: Is this child in the family ledger or carries session token?
                            authorized = (p_pid in self.active_pids.get('family', []) or 
                                          self._is_current_session_process(p_pid))

                            # [FEAT-265.7] Refugee Immunity: Check ancestry if not directly authorized
                            if not authorized:
                                try:
                                    for parent in proc.parents():
                                        if parent.pid in self.active_pids.get('family', []):
                                            logger.info(f"[WATCHDOG] Granting Refugee Immunity: {p_name} (PID {p_pid}) belongs to parent {parent.pid}")
                                            authorized = True
                                            self.active_pids['family'].append(p_pid)
                                            self._save_ledger()
                                            break
                                except Exception:
                                    pass                            
                            if authorized:
                                continue

                            # If not authorized by token/family, check if it owns an active engine port
                            for port in [8088, 11434, 8765]:
                                try:
                                    # Use a subshell to check port ownership without blocking
                                    res = subprocess.check_output(["sudo", "fuser", f"{port}/tcp"], text=True, stderr=subprocess.DEVNULL)
                                    if str(p_pid) in res:
                                        logger.info(f"[WATCHDOG] Sparing Port-Bound Resident: {p_name} (PID {p_pid}) on port {port}")
                                        authorized = True
                                        # ADOPT: Add to family ledger immediately
                                        self.active_pids['family'].append(p_pid)
                                        self._save_ledger()
                                        break
                                except Exception:
                                    pass

                            if not authorized:
                                logger.warning(f"[WATCHDOG] Unrecognized Blacklisted Ghost: {p_name} (PID {p_pid})")
                                orphan_found = True
                                break
                        
                        if orphan_found:
                            await self._trigger_recovery("Physical Ghost (Unrecognized Blacklist process)", level=2)
                            continue
                    except Exception as e:
                        logger.error(f"[WATCHDOG] Blacklist audit failed: {e}")

                # Scenario C: Zombie/Stuck State Check
                engine_pid = self.active_pids.get('engine_pid')
                if engine_pid and psutil.pid_exists(engine_pid):
                    proc = psutil.Process(engine_pid)
                    if proc.status() in [psutil.STATUS_ZOMBIE, psutil.STATUS_DISK_SLEEP]:
                        await self._trigger_recovery(f"Engine Process {proc.status()}", level=2)
                        continue

                # 3. Hub Liveness Probe [FEAT-035] (ERR-05)
                if current_lab_mode != "OFFLINE" and not is_hibernating:
                    try:
                        async with aiohttp.ClientSession() as session:
                            start_t = time.time()
                            async with session.get("http://127.0.0.1:8765/heartbeat", timeout=2.0) as r:
                                latency = time.time() - start_t
                                if r.status == 200:
                                    self.failure_count = 0
                                    if latency > 5.0:
                                        self.log_event(f"Degraded Heartbeat: {latency:.2f}s", "WARNING")
                                else:
                                    self.failure_count += 1
                    except Exception:
                        self.failure_count += 1

                    if self.failure_count >= 5:
                        await self._trigger_recovery("Hub Unresponsive (5 cycles)", level=2)
                        continue

                # 4. Docker Observability Watchdog [v1 Lost Gem]
                # [FEAT-180.1] Docker Cooldown: Check every 5 minutes
                now = time.time()
                if now - self._last_docker_check > 300:
                    for container in MONITOR_CONTAINERS:
                        try:
                            res = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", container],
                                                 capture_output=True, text=True, timeout=2)
                            if "true" not in res.stdout:
                                logger.error(f"[WATCHDOG] Container {container} is DOWN. Restarting...")
                                subprocess.Popen(["docker", "start", container])
                                self.log_event(f"Recovered observability container: {container}", "WARNING")
                        except Exception:
                            pass
                    self._last_docker_check = now

            except Exception as e:
                logger.error(f"[WATCHDOG] Loop Error: {e}")

    async def _trigger_recovery(self, reason, level=1):
        """Autonomous Recovery Engine with Forensic Log Capture."""
        logger.critical(f"[WATCHDOG] {reason.upper()} DETECTED. Triggering Level {level} recovery.")
        
        # 1. Forensic Capture [FEAT-151]
        self.trace_monitor.refresh_marks()
        await asyncio.sleep(2) # Allow log flush for slow PCIe/Disk
        deltas = self.trace_monitor.capture_delta()
        snippet = " | ".join(deltas[-10:]).replace('"', "'") if deltas else "No recent log context."
        
        # 2. Interleaved Logging
        self.log_event(f"[WATCHDOG] RECOVERY [{reason}]. Last Words: {snippet}", "CRITICAL")
        
        # 3. Reset Sequence
        if level == 1:
            await self.mcp_hibernate(reason=f"WD_RECOVERY_{reason}")
        else:
            await self.mcp_stop(reason=f"WD_RECOVERY_{reason}")
            await asyncio.sleep(5)
            await self.mcp_start(reason="WATCHDOG_AUTO_IGNITION")

    # --- REST Handlers ---
    async def handle_start_rest(self, r): 
        data = await r.json()
        engine = data.get("engine", "OLLAMA")
        model = data.get("model", "MEDIUM")
        disable_ear = data.get("disable_ear", True)
        op_mode = data.get("op_mode", "SERVICE_UNATTENDED")
        engine_only = data.get("engine_only", False)
        reason = data.get("reason", "REST_API_START")
        return web.json_response(await self.mcp_start(engine, model, disable_ear, op_mode, engine_only=engine_only, reason=reason))
    async def handle_stop_rest(self, r):
        return web.json_response(await self.mcp_stop())
    async def handle_hibernate_rest(self, r):
        return web.json_response(await self.mcp_hibernate())
    async def handle_quiesce_rest(self, r):
        return web.json_response(await self.mcp_quiesce())
    async def handle_ignition_rest(self, r):
        data = await r.json() if r.has_body else {}
        reason = data.get("reason", "REST_API_IGNITION")
        return web.json_response(await self.mcp_ignition(reason=reason))
    async def handle_train_rest(self, r):
        data = await r.json()
        return web.json_response(await self.mcp_train_adapter(data.get("adapter"), data.get("steps", 60)))
    async def handle_heartbeat_rest(self, r):
        return web.json_response(await self.mcp_heartbeat())
    async def handle_ping_rest(self, r):
        return web.json_response(await self.mcp_heartbeat())
    async def handle_wait_ready_rest(self, r):
        """[FEAT-265] Blocks until the Lab reports READY or crashes."""
        timeout = int(r.query.get("timeout", 300)) # Default to 300s for vLLM weights
        start_t = time.time()

        while time.time() - start_t < timeout:
            if self.ready_event.is_set():
                return web.json_response({"status": "ready"})

            # [FEAT-265.4] Crash Awareness: Return immediately if process dies
            if lab_process and lab_process.poll() is not None:
                logger.error("[API] wait_ready aborted: Lab process has terminated.")
                return web.json_response({"status": "crashed", "message": "Lab process terminated during boot."}, status=500)

            await asyncio.sleep(1.0)

        return web.json_response({"status": "timeout", "message": "Lab failed to reach READY state in time."}, status=408)

    async def handle_logs_rest(self, r):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, "r") as f:
                return web.Response(text=f.read()[-5000:])
        return web.Response(status=404)
    async def handle_mutex_rest(self, r):
        return web.json_response({"round_table_lock_exists": os.path.exists(ROUND_TABLE_LOCK)})

    async def handle_shutdown(self, app):
        """[CLEAN_RESTART] Ensures the Lab reaps its OWN session upon exit."""
        logger.warning(f"[SHUTDOWN] Service termination detected (Session: {self.session_token}). Reaping session silicon...")
        # [FEAT-119.5] Robust Synchronous Guard: Force-reap all engines and Hub
        try:
            await self.cleanup_silicon(mode="SESSION")
            logger.warning("[SHUTDOWN] Silicon reap successful.")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Silicon reap failed: {e}")
            # Final emergency: use fuser
            subprocess.run(["sudo", "fuser", "-k", "8088/tcp", "11434/tcp", "8765/tcp"], stderr=subprocess.DEVNULL)
        
        # [FEAT-277] Ensure ledger is cleared
        self.active_pids = {'hub_pid': None, 'engine_pid': None, 'engine_mode': None, 'family': []}
        self._save_ledger()

# --- Global Instance and MCP Wrappers ---
attendant = LabAttendantV4()
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
async def lab_wait_ready(timeout: int = 120):
    """[FEAT-258.1] Resilient Sentinel: Wait for Hub READY with Master liveness probe."""
    # If we are the PROXY, ensure the Master is actually up before we even try to call the internal wait
    if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
        for i in range(10): # 20s initial_probe
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://127.0.0.1:9999/heartbeat", timeout=2) as r:
                        if r.status == 200:
                            break
            except Exception:
                await asyncio.sleep(2)
        else:
            return {"status": "error", "message": "Proxy cannot reach Master Attendant after 20s. Is the service running?"}

    return await attendant.mcp_wait_ready(timeout)

async def run_bilingual():
    # [FEAT-219] Silicon Handshake: Role-Based Execution
    role = os.environ.get("LAB_ATTENDANT_ROLE")
    
    if role == "MASTER":
        # Full Master Mode: REST API + Pulse + Watchdog
        attendant.app.on_shutdown.append(attendant.handle_shutdown)
        runner = web.AppRunner(attendant.app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", ATTENDANT_PORT).start()
        logger.info(f"[BOOT] Lab Attendant V4.1 (Guardian) active on {ATTENDANT_PORT}")
        
        # [FEAT-220.1] Physical Adoption
        logger.info("[BOOT] Initiating state reconstruction...")
        await attendant.scavenge_reality()
        
        asyncio.create_task(attendant.vram_watchdog_loop())
        asyncio.create_task(attendant.pulse_loop())
        
        # [FEAT-136] Cold Hub Ignition: Proactively open the foyer for the Handshake Spark
        logger.info("[BOOT] Safe-Pilot: Igniting Hub foyer...")
        # Support STUB mode for rapid testing via environment
        engine = "STUB" if os.environ.get("LAB_TEST_STUB") == "1" else os.environ.get("LAB_MODE", "OLLAMA")
        model = os.environ.get("LAB_MODEL", "MEDIUM")
        # Note: In this context, engine_only=True means 'Just start the Hub'.
        asyncio.create_task(attendant.mcp_start(engine=engine, model=model, engine_only=True, reason="SAFE_PILOT"))

        # If in a TTY, also allow local tools, otherwise just wait
        if sys.stdin.isatty():
            await mcp.run_stdio_async()
        else:
            await asyncio.Event().wait()
    else:
        # Proxy Mode: Tool execution forwards to the Master
        os.environ["LAB_ATTENDANT_ROLE"] = "PROXY" 
        
        # [FIX] Always run the stdio transport when spawned as an MCP server.
        # The isatty check was blocking the Gemini CLI from discovering tools.
        logger.info("[BOOT] Proxy node starting MCP stdio transport...")
        await mcp.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(run_bilingual())
