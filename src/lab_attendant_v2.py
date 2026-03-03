import os
import subprocess
import json
import asyncio
import datetime
import logging
import psutil
import aiohttp
from aiohttp import web
from mcp.server.fastmcp import FastMCP
from infra.montana import reclaim_logger, get_fingerprint

# --- Configuration (Synced with V1) ---
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
SERVER_LOG = f"{LAB_DIR}/server.log"
ATTENDANT_LOG = f"{LAB_DIR}/attendant.log"
SERVER_PID_FILE = f"{LAB_DIR}/server.pid"
STATUS_JSON = f"{PORTFOLIO_DIR}/field_notes/data/status.json"
CHARACTERIZATION_FILE = f"{PORTFOLIO_DIR}/field_notes/data/vram_characterization.json"
INFRASTRUCTURE_FILE = f"{LAB_DIR}/config/infrastructure.json"
MAINTENANCE_LOCK = f"{PORTFOLIO_DIR}/field_notes/data/maintenance.lock"
VLLM_START_PATH = f"{LAB_DIR}/src/start_vllm.sh"
LAB_SERVER_PATH = f"{LAB_DIR}/src/acme_lab.py"
LAB_VENV_PYTHON = f"{LAB_DIR}/.venv/bin/python3"
ATTENDANT_PORT = 9999

MONITOR_CONTAINERS = [
    "field_prometheus", "field_grafana", "field_node_exporter", 
    "field_rapl_sim", "field_dcgm_exporter", "field_loki", "field_promtail"
]

# --- Global State ---
reclaim_logger("ATTENDANT")
logger = logging.getLogger("lab_attendant")

class Orchestrator:
    """
    Unified logic core for Lab operations. 
    Decoupled from transport (REST/MCP).
    """
    def __init__(self):
        self.lab_process = None
        self.mode = "OFFLINE"
        self.model = None
        self.ready_event = asyncio.Event()
        self.vram_config = {}
        self.refresh_config()

    def refresh_config(self):
        if os.path.exists(CHARACTERIZATION_FILE):
            with open(CHARACTERIZATION_FILE, "r") as f:
                self.vram_config = json.load(f)
        logger.info("[ORCH] Config refreshed.")

    async def get_vitals(self):
        vitals = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "engine_running": False,
            "lab_mode": self.mode,
            "model": self.model,
            "full_lab_ready": self.ready_event.is_set(),
            "last_error": None,
        }
        
        # Engine check (Ollama)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags", timeout=0.5) as r:
                    vitals["engine_running"] = (r.status == 200)
        except Exception:
            pass

        # Port check (Hub)
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', 8765), timeout=1.0)
            vitals["lab_server_running"] = True
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

        if self.lab_process and self.lab_process.poll() is not None:
            if not vitals["lab_server_running"]:
                vitals["last_error"] = f"Process died: {self.lab_process.poll()}"
        
        return vitals

    async def cleanup_silicon(self):
        import signal
        logger.warning("[ASSASSIN] Purging silicon...")
        protected_pids = {os.getpid(), os.getppid()}
        
        # Port Cleanup
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr.port in [8765, 8088] and conn.pid not in protected_pids:
                try:
                    pgid = os.getpgid(conn.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass

        # Process Cleanup
        targets = ["acme_lab.py", "archive_node.py", "vllm", "ollama"]
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            if proc.info["pid"] in protected_pids:
                continue
            cmdline = " ".join(proc.info["cmdline"] or []).lower()
            if any(t in cmdline for t in targets):
                try:
                    proc.kill()
                except Exception:
                    pass
        await asyncio.sleep(1.0)

    async def start_lab(self, engine="OLLAMA", model="SMALL", mode="SERVICE_UNATTENDED", disable_ear=True):
        await self.cleanup_silicon()
        self.mode = engine
        self.model = model
        self.ready_event.clear()

        # Resolve model from map
        model_map = self.vram_config.get("model_map", {})
        actual_model = model_map.get(model, {}).get(engine.lower(), model)
        
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
        
        if engine == "VLLM":
            # [FEAT-137] Stable Turing Config
            env["VLLM_ATTENTION_BACKEND"] = "XFORMERS"
            env["NCCL_P2P_DISABLE"] = "1"
            env["NCCL_SOCKET_IFNAME"] = "lo"
            
            subprocess.Popen(["bash", VLLM_START_PATH, actual_model, LAB_VENV_PYTHON], env=env, cwd=LAB_DIR)
            await asyncio.sleep(5.0)

        cmd = [LAB_VENV_PYTHON, LAB_SERVER_PATH, "--mode", mode]
        if disable_ear:
            cmd.append("--disable-ear")

        self.lab_process = subprocess.Popen(
            cmd, cwd=LAB_DIR, env=env,
            stderr=open(SERVER_LOG, "a", buffering=1),
            preexec_fn=os.setpgrp
        )
        logger.info(f"[START] Lab ignited (PID: {self.lab_process.pid})")
        return {"status": "success", "pid": self.lab_process.pid}

    async def quiesce(self):
        with open(MAINTENANCE_LOCK, "w") as f:
            f.write(datetime.datetime.now().isoformat())
        await self.cleanup_silicon()
        self.mode = "OFFLINE"
        return {"status": "locked"}

# --- The Bilingual Wrapper ---
orch = Orchestrator()
mcp = FastMCP("Lab Attendant")

@mcp.tool()
async def ignite_lab(engine: str = "OLLAMA", model: str = "SMALL", disable_ear: bool = True):
    """Ignites the Acme Lab silicon residents."""
    return await orch.start_lab(engine=engine, model=model, disable_ear=disable_ear)

@mcp.tool()
async def quiesce_lab():
    """Performs total silicon lockdown and sets maintenance lock."""
    return await orch.quiesce()

@mcp.tool()
async def get_lab_status():
    """Returns the current vitals and residency state of the Lab."""
    return await orch.get_vitals()

# --- REST Endpoints ---
async def rest_heartbeat(request):
    vitals = await orch.get_vitals()
    return web.json_response(vitals)

async def rest_start(request):
    data = await request.json()
    res = await orch.start_lab(
        engine=data.get("engine", "OLLAMA"),
        model=data.get("model", "SMALL"),
        disable_ear=data.get("disable_ear", True)
    )
    return web.json_response(res)

async def rest_quiesce(request):
    res = await orch.quiesce()
    return web.json_response(res)

async def run_bilingual_server():
    # 1. Start HTTP Server in background
    app = web.Application()
    app.router.add_get("/heartbeat", rest_heartbeat)
    app.router.add_post("/start", rest_start)
    app.router.add_post("/quiesce", rest_quiesce)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", ATTENDANT_PORT)
    await site.start()
    logger.info(f"[BOOT] REST API active on {ATTENDANT_PORT}")

    # 2. Run MCP Server (owns stdin/stdout)
    # Note: FastMCP.run() is blocking, so we run it last.
    logger.info(f"[BOOT] MCP Identity: {get_fingerprint('MCP')}")
    mcp.run()

if __name__ == "__main__":
    asyncio.run(run_bilingual_server())
