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

# [BKM-022] Atomic IO & [FEAT-151] Trace Monitoring
from infra.atomic_io import atomic_write_json, atomic_write_text
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
        self.ready_event = asyncio.Event()
        self.vram_config = {}
        self.refresh_vram_config()

    def refresh_vram_config(self):
        if os.path.exists(CHARACTERIZATION_FILE):
            try:
                with open(CHARACTERIZATION_FILE, "r") as f:
                    self.vram_config = json.load(f)
            except Exception: pass

    # --- Proxy Helper ---
    async def _proxy_request(self, method, endpoint, data=None):
        """Redirects tool calls from the Proxy process to the Master Service."""
        url = f"http://localhost:{ATTENDANT_PORT}/{endpoint}"
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

    async def mcp_start(self, engine: str = "OLLAMA", model: str = "MEDIUM", disable_ear: bool = True):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "start", {"engine": engine, "model": model, "disable_ear": disable_ear})
        
        global current_lab_mode, current_model, lab_process
        current_lab_mode = engine
        current_model = model
        
        await self.cleanup_silicon()
        self.ready_event.clear()
        self.trace_monitor.refresh_marks()
        
        env = os.environ.copy()
        env["LAB_MODE"] = engine
        if disable_ear: env["DISABLE_EAR"] = "1"
        
        if engine == "VLLM":
            # [SPR-13.0] Verified 0.17 Stable Config for Compute 7.5
            env["NCCL_P2P_DISABLE"] = "1"
            env["NCCL_SOCKET_IFNAME"] = "lo"
            env["VLLM_EXTRA_ARGS"] = "--gpu-memory-utilization 0.4 --enforce-eager --attention-backend TRITON_ATTN --enable-lora --max-loras 4"
            
            logger.info(f"[VLLM] Igniting Sovereign Node: {model}")
            subprocess.Popen(["bash", VLLM_START_PATH, model, sys.executable], env=env, cwd=LAB_DIR)
            await self._wait_for_vllm()

        # Start Hub
        cmd = [sys.executable, LAB_SERVER_PATH, "--mode", "SERVICE_UNATTENDED"]
        if disable_ear: cmd.append("--disable-ear")
        
        lab_process = subprocess.Popen(cmd, cwd=LAB_DIR, env=env, stderr=open(SERVER_LOG, "a", buffering=1), preexec_fn=os.setpgrp)
        asyncio.create_task(self.log_monitor_loop())
        return {"status": "success", "message": f"Ignited {model} via {engine}"}

    async def mcp_stop(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "stop")
        await self.cleanup_silicon()
        await self.update_status_json("OFFLINE (Manual Stop)")
        return {"status": "success", "message": "Lab stopped."}

    async def mcp_quiesce(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "quiesce")
        logger.warning("[QUIESCE] Lockdown initiated. Setting maintenance lock.")
        with open(MAINTENANCE_LOCK, "w") as f:
            f.write(datetime.datetime.now().isoformat())
        await self.cleanup_silicon()
        await self.update_status_json("MAINTENANCE MODE (Locked)")
        return {"status": "locked", "message": "Lab frozen. Watchdog passive."}

    async def mcp_ignition(self):
        if os.environ.get("LAB_ATTENDANT_ROLE") == "PROXY":
            return await self._proxy_request("POST", "ignition")
        if os.path.exists(MAINTENANCE_LOCK):
            os.remove(MAINTENANCE_LOCK)
        return {"status": "unlocked", "message": "Maintenance lock cleared."}

    async def cleanup_silicon(self):
        """[FEAT-119] Broad-Spectrum Assassin: Reclaim hardware handles by port."""
        pids_to_kill = set()
        
        # [DYNAMIC PROTECTION] Identify 'self' and 'family' to avoid suicide.
        my_pgid = os.getpgid(os.getpid())
        
        for port in [8088, 8765]:
            try:
                res = subprocess.check_output(["sudo", "fuser", f"{port}/tcp"], stderr=subprocess.STDOUT, text=True)
                for line in res.split("\n"):
                    if ":" in line:
                        pid_str = line.split(":")[1].strip()
                        if pid_str:
                            for pid in pid_str.split():
                                try:
                                    target_pgid = os.getpgid(int(pid))
                                    # Never kill our own process group.
                                    if target_pgid != my_pgid:
                                        pids_to_kill.add(target_pgid)
                                except: pass
            except Exception: pass

        if pids_to_kill:
            logger.warning(f"[ASSASSIN] Purging {len(pids_to_kill)} process groups holding ports.")
            for pgid in pids_to_kill:
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

    async def update_status_json(self, msg=None):
        vitals = await self._get_current_vitals()
        live_data = {
            "status": "ONLINE" if vitals["lab_server_running"] else "OFFLINE",
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
                        if r.status == 200: return True
            except: pass
            await asyncio.sleep(2)
        return False

    async def vram_watchdog_loop(self):
        """[FEAT-180] Resilience Ladder: Passive Monitoring."""
        while True:
            await asyncio.sleep(10)
            if os.path.exists(MAINTENANCE_LOCK): continue
            pass

    # --- REST Handlers ---
    async def handle_start_rest(self, r): 
        data = await r.json()
        return web.json_response(await self.mcp_start(data.get("engine"), data.get("model"), data.get("disable_ear", True)))
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

# --- Global Instance and MCP Wrappers ---
attendant = LabAttendantV3()
@mcp.tool()
async def lab_heartbeat(): return await attendant.mcp_heartbeat()
@mcp.tool()
async def lab_start(engine: str = "OLLAMA", model: str = "MEDIUM", disable_ear: bool = True): return await attendant.mcp_start(engine, model, disable_ear)
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
