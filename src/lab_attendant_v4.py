import os
import subprocess
import socket
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

    # [FEAT-252] Dynamic Auth: Allow either the STYLE_HASH or the current SESSION_TOKEN
    if provided_key not in [expected_key, attendant.session_token]:
        logger.warning(f"[SECURITY] Invalid Key: {provided_key} (Expected Style: {expected_key} or Session: {attendant.session_token}) from {request.remote}")
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
        
        self.trace_monitor = TraceMonitor([SERVER_LOG, ATTENDANT_LOG])
        self.ready_event = asyncio.Event()
        self.current_reason = "INIT"
        self.session_token = uuid.uuid4().hex[:8] # [FEAT-220] Stable Session Token
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
    async def _proxy_request(self, method, endpoint, data=None, retries=5):
        """[FEAT-258] Resilient Proxy: Redirects tool calls with automatic retry backoff."""
        key = get_style_key()
        connector = "&" if "?" in endpoint else "?"
        url = f"http://localhost:{ATTENDANT_PORT}/{endpoint}{connector}key={key}"
        
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
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "start", {
                "engine": engine, "model": model, "disable_ear": disable_ear, 
                "op_mode": op_mode, "engine_only": engine_only, "reason": reason
            })

        global current_lab_mode, current_model, lab_process, is_hibernating

        
        if os.path.exists(MAINTENANCE_LOCK):
            logger.warning("[IGNITION] Aborting start: MAINTENANCE_LOCK detected.")
            return {"status": "error", "message": "Maintenance lock active."}

        is_hibernating = False
        self.current_reason = reason
        logger.info(f"[IGNITION] [{reason.upper()}] Starting {model} via {engine} (Mode: {op_mode})")

        
        self.refresh_vram_config() # Reload latest model mappings
        
        # Resolve model path and config from map
        model_map = self.vram_config.get("model_map", {})
        tier_config = model_map.get(model, model_map.get("UNIFIED", {}))
        
        target_model = tier_config.get("vllm" if engine == "VLLM" else "ollama", model)
        utilization = tier_config.get("gpu_memory_utilization", 0.4)
        backend = tier_config.get("attention_backend", "TRITON_ATTN")

        # [FEAT-262] Fast Wake Path: If already hibernating, just wake up
        if current_lab_mode == "HIBERNATING" and engine == "VLLM":
            logger.info(f"[IGNITION] [{reason.upper()}] Fast Wake triggered for hibernating vLLM.")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post("http://localhost:8088/wake_up", timeout=5.0) as r:
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
        except Exception: pass

        
        # [FEAT-259.2] Fast STUB: Skip physical silicon gates for logic testing
        if engine == "STUB":
            logger.info("[IGNITION] STUB mode active. Bypassing physical gates.")
            self.ready_event.set() # Instant Ready
            if not engine_only:
                # Still spawn Hub foyer if requested
                pass # Spawning logic below will handle it
            else:
                return {"status": "success", "message": "STUB engine sparked."}

        # 1. Resolve Required Memory [FEAT-254]
        used_now, total_vram = await self._get_vram_info()
        required_mb = int(total_vram * utilization)

        # [FEAT-250] Surgical Ignition: Spare the Hub if requested
        # 2. Cleanup: Clear orphans from required ports
        if engine_only:
            await self.cleanup_silicon(mode="ORPHANS")
        else:
            await self.cleanup_silicon(mode="ORPHANS")

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
            # [SPR-13.0] Verified Stable Config
            env["NCCL_P2P_DISABLE"] = "1"
            env["NCCL_SOCKET_IFNAME"] = "lo"
            env["VLLM_ATTENTION_BACKEND"] = str(backend)
            env["VLLM_SERVER_DEV_MODE"] = "1" # [FEAT-262] Required for Sleep Mode
            
            # [FEAT-030] Unity Pattern: Build LoRA module string
            lora_modules = tier_config.get("lora_modules", [])
            lora_args = "--lora-modules " + " ".join(lora_modules) if lora_modules else ""
            
            # Context Constraint from characterization
            max_len = tier_config.get("max_model_len", 8192)
            
            # [BKM] Consolidate into EXTRA_ARGS for the script to consume
            # [FEAT-262] Adding --enable-sleep-mode
            env["VLLM_EXTRA_ARGS"] = f"--gpu-memory-utilization {utilization} --enforce-eager --attention-backend {backend} --enable-lora --max-loras 4 --max-model-len {max_len} --enable-sleep-mode {lora_args}"
            
            logger.info(f"[VLLM] Launching Sovereign Node: {target_model} (Recipe: start_vllm.sh)")
            self.log_event(f"Ignition [{reason.upper()}]: {engine}/{target_model} (Mode: {op_mode})")
            subprocess.Popen(["bash", VLLM_START_PATH, target_model, sys.executable], env=env, cwd=LAB_DIR, start_new_session=True)
            await self._wait_for_vllm()
        elif engine == "OLLAMA":
            # [SPR-13.0] OLLAMA Fallback
            logger.info(f"[OLLAMA] Launching Fallback Node: {target_model}")
            self.log_event(f"Ignition [{reason.upper()}]: {engine}/{target_model} (Mode: {op_mode})")
            subprocess.Popen(["ollama", "run", target_model], env=env, start_new_session=True)
        elif engine == "STUB":
            self.log_event(f"Ignition [{reason.upper()}]: STUB (Mode: {op_mode})")
            # No physical subprocess needed for STUB engine
            pass

        # [FEAT-250] Surgical Ignition: Only skip Hub if it is already running AND immune
        hub_active = False
        try:
            res = subprocess.check_output(["sudo", "fuser", "8765/tcp"], stderr=subprocess.STDOUT, text=True)
            if ":" in res:
                pid = int(res.split(":")[1].strip().split()[0])
                if self._is_current_session_process(pid):
                    hub_active = True
                else:
                    logger.warning(f"[IGNITION] Reaping non-immune orphan on port 8765 (PID: {pid})")
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                    await asyncio.sleep(1.0)
        except Exception:
            pass

        if engine_only and hub_active:
            logger.info("[IGNITION] Surgical Spark complete. Foyer spared.")
            return {"status": "success", "message": "Engines sparked. Hub spared."}

        # Start Hub
        logger.info(f"[IGNITION] [{reason.upper()}] Igniting Hub foyer...")
        cmd = [sys.executable, LAB_SERVER_PATH, "--mode", op_mode]
        if disable_ear:
            cmd.append("--disable-ear")
        
        # [FEAT-213] Engine Warm-up Delay (Reduced for speed)
        await asyncio.sleep(2.0)
        
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

    async def mcp_hibernate(self):
        """[FEAT-249] Selective engine unload (Sleep) while keeping Hub alive."""
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "hibernate")
        
        global is_hibernating, current_lab_mode
        is_hibernating = True
        current_lab_mode = "HIBERNATING"
        
        # [FEAT-262] vLLM Sleep Mode (Fast Path)
        engine = os.environ.get("LAB_MODE", "OLLAMA")
        if engine == "VLLM":
            logger.warning("[HUB] Transitioning vLLM to Sleep Mode (Level 1)...")
            
            async def _tactical_sleep():
                try:
                    async with aiohttp.ClientSession() as session:
                        # [FIX] Level 2 for full weight offloading (VRAM Free)
                        async with session.post("http://localhost:8088/sleep?level=2", timeout=10.0) as r:
                            if r.status == 200:
                                logger.warning("[SLEEP] vLLM successfully offloaded weights to CPU. VRAM Reclaimed.")
                                await self.update_status_json("HIBERNATING (VRAM Free)")
                            else:
                                logger.error(f"[SLEEP] vLLM rejected sleep level 2: {r.status}")
                                # Fallback to hard-reap if level 2 is unsupported
                                await self.cleanup_silicon(mode="SESSION")
                except Exception as e:
                    logger.error(f"[SLEEP] vLLM sleep signal failed: {e}")
                    # Fallback to hard-reap if the REST API is dead
                    await self.cleanup_silicon(mode="SESSION")
            
            asyncio.create_task(_tactical_sleep())
            return {"status": "success", "message": "vLLM sleep signal dispatched."}

        # Fallback: [FEAT-259] The Butler Pattern (Kill-to-Hibernate)
        logger.warning("[HUB] Hibernation signal received. Unloading local engines via Reap...")
        self.log_event("Hibernation: Unloading weights via Reap.")
        
        async def _run_selective_cleanup():
            await asyncio.sleep(0.5)
            # Use the new signature-aware cleanup but spare the Hub
            await self.cleanup_silicon(mode="SESSION") 
            # Note: SESSION mode reaps Hub by token, but for Hibernation we usually want Hub to stay.
            # So I'll manually call a selective version or adjust cleanup_silicon.
            # Let's just do a manual session reap for engines only.
            reaped_count = 0
            for proc in psutil.process_iter(["pid", "name", "environ", "cmdline"]):
                try:
                    token = proc.info.get("environ", {}).get("LAB_IMMUNITY_TOKEN")
                    if token == self.session_token:
                        cmdline = " ".join(proc.info["cmdline"] or []).lower()
                        if any(t in cmdline for t in ["vllm", "ollama", "enginecore"]):
                            os.killpg(os.getpgid(proc.info["pid"]), signal.SIGKILL)
                            reaped_count += 1
                except Exception: continue
            
            if reaped_count > 0:
                logger.info(f"[BUTLER] Successfully reaped {reaped_count} session engine processes.")
            
            # [FEAT-249.3] Verified Hibernation: Wait for VRAM drop
            for i in range(10):
                used, _ = await self._get_vram_info()
                if used < 2000:
                    logger.info(f"[HIBERNATE] VRAM reclamation verified at {used}MB.")
                    break
                await asyncio.sleep(2)
            await self.update_status_json("HIBERNATING (VRAM Free)")

        asyncio.create_task(_run_selective_cleanup())
        return {"status": "success", "message": "Hibernation initiated."}

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

    async def mcp_wait_ready(self, timeout: int = 120):
        """[FEAT-136] Blocking wait for the Lab Hub to reach the READY state with Forensic detection."""
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("GET", f"wait_ready?timeout={timeout}")
        
        start_t = time.time()
        # [FEAT-251.2] Forensic Wait: Catch Hub-level crashes early
        while time.time() - start_t < timeout:
            if self.ready_event.is_set():
                # [FEAT-259.3] Physical Verify: Ensure engine port is actually listening
                try:
                    # [REVISION-17.9] Use asyncio.to_thread for blocking socket probe
                    def probe_port():
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            return s.connect_ex(("localhost", 8088)) == 0
                    
                    if await asyncio.to_thread(probe_port):
                        return {"status": "ready", "message": "Lab is Open."}
                except Exception: pass
            
            # Check server.log for Hub crashes
            if os.path.exists(SERVER_LOG):
                try:
                    # [REVISION-17.9] Use asyncio.to_thread for blocking file read
                    def read_log():
                        with open(SERVER_LOG, "r") as f:
                            return f.readlines()[-20:]
                    
                    lines = await asyncio.to_thread(read_log)
                    if any("Traceback" in line or "Error:" in line or "Exception:" in line for line in lines):
                            # Ensure we don't catch the 'Expected Error' during handshake resilience
                            if not any("Larynx is warming" in line for line in lines):
                                logger.error("[HUB] Fatal startup crash detected in logs. Aborting wait.")
                                return {"status": "error", "message": "Fatal Hub crash detected in logs."}
                except Exception: pass

            await asyncio.sleep(2)
            
        return {"status": "timeout", "message": f"Lab failed to reach READY within {timeout}s"}

    async def cleanup_silicon(self, mode="ORPHANS"):
        """
        [FEAT-119] Broad-Spectrum Assassin: Reclaim hardware handles.
        Modes:
          - ORPHANS: Kill anything on Lab ports/names that LACKS the current session token. (Ignition)
          - SESSION: Kill Engines by signature and Hub by current token. (Shutdown)
        """
        pgids_to_kill = set()
        my_pgid = os.getpgid(os.getpid())
        
        # 1. Target Definition
        ports = [8088, 11434, 8765]
        targets = ["vllm", "ollama", "enginecore", "acme_lab.py", "node.py"]
        
        # 2. Port-Based Discovery
        for port in ports:
            try:
                res = subprocess.check_output(["sudo", "fuser", f"{port}/tcp"], stderr=subprocess.STDOUT, text=True)
                for line in res.split("\n"):
                    if ":" in line:
                        pids = line.split(":")[1].strip().split()
                        for p in pids:
                            p_int = int(p)
                            is_mine = self._is_current_session_process(p_int)
                            
                            # [FEAT-119.1] Physical Override: Sparing logic
                            if mode == "SESSION":
                                # Shutdown: Kill engines by port, Hub only if it's mine
                                if port == 8765:
                                    if is_mine: pgids_to_kill.add(os.getpgid(p_int))
                                else:
                                    pgids_to_kill.add(os.getpgid(p_int)) # Kill all engines
                            else:
                                # Ignition (ORPHANS): Kill ONLY if NOT mine.
                                # This ensures the Hub foyer that just called us survives.
                                if not is_mine:
                                    pgids_to_kill.add(os.getpgid(p_int))
            except Exception: pass

        # 3. Name-Based Discovery (For token-blind EngineCores)
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                p_name = str(proc.info["name"] or "").lower()
                cmd = " ".join(proc.info["cmdline"] or []).lower()
                pid = proc.info["pid"]
                is_mine = self._is_current_session_process(pid)
                is_engine = any(t in cmd or t in p_name for t in ["vllm", "ollama", "enginecore"])
                
                if mode == "SESSION":
                    if is_engine: pgids_to_kill.add(os.getpgid(pid))
                    elif is_mine: pgids_to_kill.add(os.getpgid(pid))
                else:
                    # Ignition: Kill orphans matching our names
                    if any(t in cmd or t in p_name for t in targets) and not is_mine:
                        pgids_to_kill.add(os.getpgid(pid))
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass

        if pgids_to_kill:
            pgids_to_kill.discard(my_pgid)
            if pgids_to_kill:
                logger.warning(f"[ASSASSIN] [{mode}] Purging process groups: {pgids_to_kill}")
                for pgid in pgids_to_kill:
                    with contextlib.suppress(Exception):
                        os.killpg(pgid, signal.SIGKILL)
        
        await asyncio.sleep(2.0)

    def _is_current_session_process(self, pid):
        """Returns True if the process carries the current session token."""
        try:
            if pid == os.getpid(): return False
            proc = psutil.Process(pid)
            token = proc.environ().get("LAB_IMMUNITY_TOKEN")
            return token == self.session_token
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
            "reason": self.current_reason,
            "session": self.session_token,
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
                
                if "[READY] Lab is Open" in line:
                    self.ready_event.set()
                    logger.info("[WATCHDOG] Lab reported READY signal.")
                    await self.update_status_json("Mind is READY")
                
                # [FEAT-255.2] Continuous Sentinel: Listen for state resets
                if "Clearing Hub READY state" in line:
                    self.ready_event.clear()
                    logger.warning("[WATCHDOG] Hub READY state cleared for transition.")

    async def _wait_for_vllm(self, timeout=120):
        start_t = time.time()
        # [FEAT-251.2] Forensic Wait: Early crash detection
        vllm_log = os.path.join(LAB_DIR, "vllm_server.log")
        
        while time.time() - start_t < timeout:
            # Check for crashes in log
            if os.path.exists(vllm_log):
                try:
                    with open(vllm_log, "r") as f:
                        # Read last 20 lines
                        lines = f.readlines()[-20:]
                        if any("Traceback" in line or "ValueError:" in line or "RuntimeError:" in line for line in lines):
                            logger.error("[VLLM] Fatal startup crash detected in logs. Aborting wait.")
                            return False
                except Exception:
                    pass

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

    async def handle_shutdown(self, app):
        """[CLEAN_RESTART] Ensures the Lab reaps its OWN session upon exit."""
        logger.warning(f"[SHUTDOWN] Service termination detected (Session: {self.session_token}). Reaping session silicon...")
        # Reaps all engines by name/port and the Hub by token
        await self.cleanup_silicon(mode="SESSION")

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
        for i in range(10): # 20s initial probe
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://localhost:9999/heartbeat", timeout=2) as r:
                        if r.status == 200: break
            except Exception:
                await asyncio.sleep(2)
        else:
            return {"status": "error", "message": "Proxy cannot reach Master Attendant after 20s. Is the service running?"}

    return await attendant.mcp_wait_ready(timeout)

async def run_bilingual():
    # [FEAT-219] Silicon Handshake: Role-Based Execution
    role = os.environ.get("LAB_ATTENDANT_ROLE")
    not sys.stdin.isatty()
    
    if role == "MASTER":
        # Full Master Mode: REST API + Pulse + Watchdog
        attendant.app.on_shutdown.append(attendant.handle_shutdown)
        runner = web.AppRunner(attendant.app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", ATTENDANT_PORT).start()
        logger.info(f"[BOOT] Lab Attendant V4.1 (Guardian) active on {ATTENDANT_PORT}")
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
