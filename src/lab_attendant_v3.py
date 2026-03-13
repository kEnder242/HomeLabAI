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
import pynvml

# [BKM-022] Atomic IO & [FEAT-151] Trace Monitoring
from infra.atomic_io import atomic_write_json
from debug.trace_monitor import TraceMonitor
from infra.forensic_ledger import ForensicLedger
from infra.status_model import StatusModel

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
ROUND_TABLE_LOCK = f"{LAB_DIR}/round_table.lock"
MAINTENANCE_LOCK = f"{PORTFOLIO_DIR}/field_notes/data/maintenance.lock"
PAGER_ACTIVITY_FILE = f"{PORTFOLIO_DIR}/field_notes/data/pager_activity.json"
VLLM_START_PATH = f"{LAB_DIR}/src/start_vllm.sh"
LAB_SERVER_PATH = f"{LAB_DIR}/src/acme_lab.py"
LAB_VENV_PYTHON = f"{LAB_DIR}/.venv/bin/python3"
ATTENDANT_PORT = 9999

# --- Global State ---
lab_process = None
current_lab_mode = "OFFLINE"
current_model = None
requested_model_tier = "UNIFIED"
_BOOT_HASH = uuid.uuid4().hex[:4].upper()

# [BKM-002] Montana Protocol: Aggressive Logger Authority
from infra.montana import reclaim_logger
reclaim_logger(role="ATTENDANT")
logger = logging.getLogger("lab_attendant_v3")

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
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

class LabAttendantV3:
    def __init__(self):
        self.app = web.Application(middlewares=[cors_middleware])
        # [SERVICE] Control & Monitoring Endpoints
        self.app.router.add_post("/start", self.handle_start_rest)
        self.app.router.add_post("/stop", self.handle_stop_rest)
        self.app.router.add_post("/quiesce", self.handle_quiesce_rest)
        self.app.router.add_post("/ignition", self.handle_ignition_rest)
        self.app.router.add_post("/hard_reset", self.handle_stop_rest)
        
        self.app.router.add_get("/heartbeat", self.handle_heartbeat_rest)
        self.app.router.add_get("/ping", self.handle_ping_rest)
        self.app.router.add_get("/wait_ready", self.handle_wait_ready_rest)
        self.app.router.add_get("/logs", self.handle_logs_rest)
        self.app.router.add_get("/mutex", self.handle_mutex_rest)
        
        self.trace_monitor = TraceMonitor([SERVER_LOG, ATTENDANT_LOG])
        self.forensic = ForensicLedger()
        self.status_model = StatusModel()
        self.ready_event = asyncio.Event()
        self.vram_config = {}
        self.refresh_vram_config()

    def refresh_vram_config(self):
        if os.path.exists(CHARACTERIZATION_FILE):
            try:
                with open(CHARACTERIZATION_FILE, "r") as f:
                    self.vram_config = json.load(f)
                logger.info("[VRAM] Config refreshed from disk.")
            except Exception: pass

    # --- Proxy Helper ---
    async def _proxy_request(self, method, endpoint, data=None):
        url = f"http://localhost:{ATTENDANT_PORT}/{endpoint}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(method, url, json=data) as r:
                    return await r.json()
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def mcp_start(self, engine: str = "OLLAMA", model: str = "MEDIUM", disable_ear: bool = True, is_autonomous: bool = False, op_mode: str = "SERVICE_UNATTENDED"):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "start", {"engine": engine, "model": model, "disable_ear": disable_ear, "op_mode": op_mode})
        
        global current_lab_mode, current_model, lab_process, requested_model_tier
        if not is_autonomous:
            requested_model_tier = model
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
        self.forensic.refresh_marks()
        
        self.status_model.update_logical(mode="IGNITION", task=f"Starting {model}", readiness="BOOTING")
        
        env = os.environ.copy()
        env["LAB_MODE"] = engine
        if disable_ear: env["DISABLE_EAR"] = "1"
        
        if engine == "VLLM":
            # [SPR-13.0] Verified Stable Config from characterization.json
            env["NCCL_P2P_DISABLE"] = "1"
            env["NCCL_SOCKET_IFNAME"] = "lo"
            env["VLLM_ATTENTION_BACKEND"] = backend
            # VLLM_EXTRA_ARGS must include the backend flag as the env var is ignored in 0.17
            env["VLLM_EXTRA_ARGS"] = f"--gpu-memory-utilization {utilization} --enforce-eager --attention-backend {backend} --enable-lora --max-loras 4"
            
            logger.info(f"[VLLM] Igniting Sovereign Node: {target_model} (Util: {utilization}, Backend: {backend})")
            logger.info(f"[DEBUG] Env Backend: {env.get('VLLM_ATTENTION_BACKEND')}, Use_V1: {env.get('VLLM_USE_V1')}")
            subprocess.Popen(["bash", VLLM_START_PATH, target_model, sys.executable], env=env, cwd=LAB_DIR)
            await self._wait_for_vllm()

        # Start Hub
        cmd = [sys.executable, LAB_SERVER_PATH, "--mode", op_mode]
        if disable_ear: cmd.append("--disable-ear")
        
        logger.info(f"[BOOT] Executing: {' '.join(cmd)}")
        lab_process = subprocess.Popen(cmd, cwd=LAB_DIR, env=env, stderr=open(SERVER_LOG, "a", buffering=1), preexec_fn=os.setpgrp)
        self.forensic.record_event("INFO", f"Lab Ignition: {model} via {engine}", {"tier": model, "engine": engine, "op_mode": op_mode})
        asyncio.create_task(self.log_monitor_loop())
        return {"status": "success", "message": f"Ignited {model} via {engine}"}

    async def mcp_stop(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "stop")
        self.forensic.record_event("WARNING", "Manual Lab Stop Initiated", {"user": "gemini-cli"})
        await self.cleanup_silicon()
        self.status_model.update_logical(mode="OFFLINE", task="None", readiness="OFFLINE")
        return {"status": "success", "message": "Lab stopped."}

    async def mcp_quiesce(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "quiesce")
        logger.warning("[QUIESCE] Lockdown initiated. Setting maintenance lock.")
        with open(MAINTENANCE_LOCK, "w") as f:
            f.write(datetime.datetime.now().isoformat())
        await self.cleanup_silicon()
        self.status_model.update_logical(mode="MAINTENANCE", task="Lockdown", readiness="OFFLINE")
        return {"status": "locked", "message": "Lab frozen. Watchdog passive."}

    async def mcp_ignition(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "ignition")
        if os.path.exists(MAINTENANCE_LOCK):
            os.remove(MAINTENANCE_LOCK)
        return {"status": "unlocked", "message": "Maintenance lock cleared."}

    async def cleanup_silicon(self):
        """[FEAT-119] Broad-Spectrum Assassin: Reclaim hardware handles by PGID."""
        pgids_to_kill = set()
        
        # Identify 'self' to avoid suicide
        my_pgid = os.getpgid(os.getpid())
        
        # 1. Port-Based Discovery (Master Residents)
        for port in [8088, 8765]:
            try:
                res = subprocess.check_output(["sudo", "fuser", f"{port}/tcp"], stderr=subprocess.STDOUT, text=True)
                for line in res.split("\n"):
                    if ":" in line:
                        pid_str = line.split(":")[1].strip()
                        for pid in pid_str.split():
                            try:
                                t_pgid = os.getpgid(int(pid))
                                if t_pgid != my_pgid:
                                    pgids_to_kill.add(t_pgid)
                            except: pass
            except Exception: pass

        # 2. Name-Based Discovery (Orphaned Residents)
        targets = ["acme_lab.py", "archive_node.py", "pinky_node.py", "brain_node.py", "vllm", "ollama", "enginecore", "python"]
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["pid"] == os.getpid(): continue
                cmdline = " ".join(proc.info["cmdline"] or []).lower()
                if any(t in cmdline for t in targets):
                    t_pgid = os.getpgid(proc.info["pid"])
                    if t_pgid != my_pgid:
                        pgids_to_kill.add(t_pgid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError): pass

        if pgids_to_kill:
            logger.warning(f"[ASSASSIN] Purging {len(pgids_to_kill)} process groups to clear zombies.")
            for pgid in pgids_to_kill:
                with contextlib.suppress(Exception):
                    os.killpg(pgid, signal.SIGKILL)
        
        await asyncio.sleep(2.0)

    async def _get_current_vitals(self):
        vitals = {"attendant_pid": os.getpid(), "lab_server_running": False, "engine_running": False, "lab_mode": current_lab_mode, "model": current_model, "full_lab_ready": self.ready_event.is_set(), "boot_hash": _BOOT_HASH}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8765/heartbeat", timeout=0.2) as r:
                    if r.status == 200: vitals["lab_server_running"] = True
                port = 8088 if current_lab_mode == "VLLM" else 11434
                async with session.get(f"http://localhost:{port}/v1/models" if port == 8088 else f"http://localhost:{port}/api/tags", timeout=0.2) as r:
                    if r.status == 200: vitals["engine_running"] = True
        except: pass
        return vitals

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
                    self.status_model.update_logical(mode="READY", task="Idle", readiness="READY")
                    return

    async def _wait_for_vllm(self, timeout=120):
        start_t = time.time()
        while time.time() - start_t < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:8088/v1/models", timeout=1.0) as r:
                        if r.status == 200: return True
            except: pass
            await asyncio.sleep(2)
        return False

    async def vram_watchdog_loop(self):
        """[FEAT-180] Resilience Ladder: Auto-Restart & Tiered Downshift."""
        global lab_process, current_lab_mode, current_model, requested_model_tier
        
        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as e:
            logger.error(f"[WATCHDOG] Failed to initialize NVML: {e}")
            return

        while True:
            await asyncio.sleep(10)
            if os.path.exists(MAINTENANCE_LOCK): continue
            self.refresh_vram_config()
            
            # 1. VRAM Monitoring
            try:
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                used_mib = info.used / 1024 / 1024
                downshift_threshold = self.vram_config.get("safe_tiers", {}).get("downshift", 9500)
                critical_threshold = self.vram_config.get("safe_tiers", {}).get("critical", 11000)
                
                vitals = await self._get_current_vitals()
                logger.info(f"[WATCHDOG] Heartbeat | VRAM: {used_mib:.0f}MiB / {downshift_threshold}MiB | Lab: {'Active' if lab_process else 'None'} | Tier: {requested_model_tier}")
                
                self.status_model.update_physical(
                    vram_used_mib=int(used_mib),
                    engine_active=vitals["engine_running"],
                    lab_active=vitals["lab_server_running"]
                )

                if used_mib > critical_threshold:
                    logger.error(f"[WATCHDOG] VRAM Critical ({used_mib:.0f}MiB). Emergency Stop.")
                    self.forensic.record_event("CRITICAL", f"VRAM Critical: {used_mib:.0f}MiB", {"threshold": critical_threshold})
                    await self.mcp_stop()
                elif used_mib > downshift_threshold and requested_model_tier == "UNIFIED":
                    model_map = self.vram_config.get("model_map", {})
                    large_model = model_map.get("LARGE", {}).get("vllm" if current_lab_mode == "VLLM" else "ollama")
                    if current_model != large_model:
                        logger.warning(f"[WATCHDOG] VRAM Pressure ({used_mib:.0f}MiB). Downshifting to LARGE tier.")
                        self.forensic.record_event("WARNING", f"VRAM Pressure: {used_mib:.0f}MiB. Downshifting.", {"threshold": downshift_threshold})
                        await self.mcp_start(engine=current_lab_mode, model="LARGE", is_autonomous=True)
            except Exception as e:
                logger.error(f"[WATCHDOG] Monitor error: {e}")

            # 2. Auto-Restart Check
            if lab_process is not None:
                poll = lab_process.poll()
                if poll is not None:
                    logger.warning(f"[WATCHDOG] Lab process died with code {poll}. Restarting...")
                    self.forensic.record_event("ERROR", f"Lab Process Died (Code: {poll}). Restarting.", {"code": poll})
                    await self.mcp_start(engine=current_lab_mode, model=requested_model_tier, is_autonomous=True)
                    continue

    # --- REST Handlers ---
    async def handle_start_rest(self, r): 
        data = await r.json()
        logger.info(f"[REST] Received /start: {data}")
        return web.json_response(await self.mcp_start(data.get("engine"), data.get("model"), data.get("disable_ear", True), op_mode=data.get("op_mode", "SERVICE_UNATTENDED")))
    async def handle_stop_rest(self, r): return web.json_response(await self.mcp_stop())
    async def handle_quiesce_rest(self, r): return web.json_response(await self.mcp_quiesce())
    async def handle_ignition_rest(self, r): return web.json_response(await self.mcp_ignition())
    async def handle_heartbeat_rest(self, r): return web.json_response(await self.mcp_heartbeat())
    async def handle_ping_rest(self, r): return web.json_response(await self.mcp_heartbeat())
    async def handle_wait_ready_rest(self, r):
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=int(r.query.get("timeout", 60)))
            return web.json_response({"status": "ready"})
        except: return web.json_response({"status": "timeout"}, status=408)
    async def handle_logs_rest(self, r):
        if os.path.exists(SERVER_LOG):
            with open(SERVER_LOG, "r") as f: return web.Response(text=f.read()[-5000:])
        return web.Response(status=404)
    async def handle_mutex_rest(self, r):
        return web.json_response({"round_table_lock_exists": os.path.exists(ROUND_TABLE_LOCK)})

    async def mcp_heartbeat(self):
        return await self._get_current_vitals()

# --- Global Instance and MCP Wrappers ---
attendant = LabAttendantV3()
@mcp.tool()
async def lab_heartbeat(): return await attendant.mcp_heartbeat()
@mcp.tool()
async def lab_start(engine: str = "OLLAMA", model: str = "MEDIUM", disable_ear: bool = True, op_mode: str = "SERVICE_UNATTENDED"): return await attendant.mcp_start(engine, model, disable_ear, op_mode=op_mode)
@mcp.tool()
async def lab_stop(): return await attendant.mcp_stop()
@mcp.tool()
async def lab_quiesce(): return await attendant.mcp_quiesce()
@mcp.tool()
async def lab_ignition(): return await attendant.mcp_ignition()

async def run_bilingual():
    # If Proxing, skip background loops and REST
    if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
        await mcp.run_stdio_async()
        return

    runner = web.AppRunner(attendant.app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", ATTENDANT_PORT).start()
    logger.info(f"[BOOT] Lab Attendant V3 (Master) active on {ATTENDANT_PORT}")
    asyncio.create_task(attendant.vram_watchdog_loop())
    
    if sys.stdin.isatty(): await mcp.run_stdio_async()
    else: await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(run_bilingual())
