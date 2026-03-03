"""
[FEAT-145] Bilingual Lab Attendant V2.

Unified orchestration core providing both a RESTful API and native MCP tools.
Hardened with the Montana Protocol and Logging Moat for stdio protection.
"""

import asyncio
import contextlib
import datetime
import json
import logging
import os
import signal
import subprocess
import sys
from typing import Any

import aiohttp
import psutil
from aiohttp import web
from mcp.server.fastmcp import FastMCP

from infra.montana import get_fingerprint, reclaim_logger

# --- Configuration (Synced with V1) ---
PORTFOLIO_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev"
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
SERVER_LOG = f"{LAB_DIR}/server.log"
ATTENDANT_LOG = f"{LAB_DIR}/attendant.log"
CHARACTERIZATION_FILE = f"{PORTFOLIO_DIR}/field_notes/data/vram_characterization.json"
MAINTENANCE_LOCK = f"{PORTFOLIO_DIR}/field_notes/data/maintenance.lock"
VLLM_START_PATH = f"{LAB_DIR}/src/start_vllm.sh"
LAB_SERVER_PATH = f"{LAB_DIR}/src/acme_lab.py"
LAB_VENV_PYTHON = f"{LAB_DIR}/.venv/bin/python3"
ATTENDANT_PORT = 9998 # Shoring: Use different port for V2 during transitory refactor

MONITOR_CONTAINERS = [
    "field_prometheus",
    "field_grafana",
    "field_node_exporter",
    "field_rapl_sim",
    "field_dcgm_exporter",
    "field_loki",
    "field_promtail",
]

# --- Global State ---
reclaim_logger("ATTENDANT")
logger = logging.getLogger("lab_attendant")

class Orchestrator:
    """Unified logic core for Lab operations.
    
    Decoupled from transport (REST/MCP) to ensure consistency across interfaces.
    """

    def __init__(self) -> None:
        """Initialize the orchestrator state and load baseline config."""
        self.lab_process: subprocess.Popen | None = None
        self.mode: str = "OFFLINE"
        self.model: str | None = None
        self.ready_event: asyncio.Event = asyncio.Event()
        self.vram_config: dict[str, Any] = {}
        self.refresh_config()

    def refresh_config(self) -> None:
        """Refresh VRAM characterization and model maps from disk."""
        if os.path.exists(CHARACTERIZATION_FILE):
            with open(CHARACTERIZATION_FILE) as f:
                self.vram_config = json.load(f)
        logger.info("[ORCH] Config refreshed.")

    async def get_vitals(self) -> dict[str, Any]:
        """Collect and return current physical and logic vitals."""
        vitals: dict[str, Any] = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "engine_running": False,
            "lab_mode": self.mode,
            "model": self.model,
            "full_lab_ready": self.ready_event.is_set(),
            "last_error": None,
            "trace_back": None,
        }

        # Engine check (Ollama)
        with contextlib.suppress(Exception):
            async with aiohttp.ClientSession() as session, \
                       session.get("http://localhost:11434/api/tags", timeout=0.5) as r:
                vitals["engine_running"] = (r.status == 200)

        # Port check (Hub)
        with contextlib.suppress(Exception):
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", 8765),
                timeout=1.0,
            )
            vitals["lab_server_running"] = True
            writer.close()
            await writer.wait_closed()

        if self.lab_process and self.lab_process.poll() is not None:
            if not vitals["lab_server_running"]:
                vitals["last_error"] = f"Process died: {self.lab_process.poll()}"
                # [FEAT-151] Trace-Back: Capture context for failed boots
                if os.path.exists(SERVER_LOG):
                    with contextlib.suppress(Exception):
                        with open(SERVER_LOG) as f:
                            vitals["trace_back"] = f.readlines()[-5:]

        return vitals

    async def cleanup_silicon(self) -> None:
        """Surgically purge all lab-related processes and clear resident ports."""
        logger.warning("[ASSASSIN] Purging silicon...")
        protected_pids = {os.getpid(), os.getppid()}

        # Port Cleanup (TCP 8765/8088)
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr.port in [8765, 8088] and conn.pid not in protected_pids:
                with contextlib.suppress(Exception):
                    if conn.pid:
                        pgid = os.getpgid(conn.pid)
                        os.killpg(pgid, signal.SIGKILL)

        # Process Cleanup (Targeted strings)
        targets = ["acme_lab.py", "archive_node.py", "vllm", "ollama"]
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            if proc.info["pid"] in protected_pids:
                continue
            cmdline = " ".join(proc.info["cmdline"] or []).lower()
            if any(t in cmdline for t in targets):
                with contextlib.suppress(Exception):
                    proc.kill()
        await asyncio.sleep(1.0)

    async def start_lab(self, engine: str = "OLLAMA", model: str = "SMALL", mode: str = "SERVICE_UNATTENDED", disable_ear: bool = True) -> dict[str, Any]:
        """Ignite the lab residents with specified engine and model tier."""
        await self.cleanup_silicon()
        self.mode = engine
        self.model = model
        self.ready_event.clear()

        # Resolve model from characterization map
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
            cmd,
            cwd=LAB_DIR,
            env=env,
            stderr=open(SERVER_LOG, "a", buffering=1),
            preexec_fn=os.setpgrp,
        )
        logger.info("[START] Lab ignited (PID: %s)", self.lab_process.pid)
        return {"status": "success", "pid": self.lab_process.pid}

    async def quiesce(self) -> dict[str, str]:
        """Set the maintenance lock and purge all silicon residents."""
        with open(MAINTENANCE_LOCK, "w") as f:
            f.write(datetime.datetime.now(datetime.timezone.utc).isoformat())
        await self.cleanup_silicon()
        self.mode = "OFFLINE"
        return {"status": "locked"}

# --- The Bilingual Wrapper ---
orch = Orchestrator()
mcp = FastMCP("Lab Attendant")

@mcp.tool()
async def ignite_lab(engine: str = "OLLAMA", model: str = "SMALL", disable_ear: bool = True) -> dict[str, Any]:
    """Ignite the Acme Lab silicon residents with specified engine and model."""
    return await orch.start_lab(engine=engine, model=model, disable_ear=disable_ear)

@mcp.tool()
async def quiesce_lab() -> dict[str, str]:
    """Perform total silicon lockdown and set the maintenance lock."""
    return await orch.quiesce()

@mcp.tool()
async def get_lab_status() -> dict[str, Any]:
    """Return the current vitals, residency state, and failure traces of the Lab."""
    return await orch.get_vitals()

# --- REST Endpoints ---
async def rest_heartbeat(_request: web.Request) -> web.Response:
    """REST wrapper for get_vitals."""
    vitals = await orch.get_vitals()
    return web.json_response(vitals)

async def rest_start(request: web.Request) -> web.Response:
    """REST wrapper for start_lab."""
    data = await request.json()
    res = await orch.start_lab(
        engine=data.get("engine", "OLLAMA"),
        model=data.get("model", "SMALL"),
        disable_ear=data.get("disable_ear", True),
    )
    return web.json_response(res)

async def rest_quiesce(_request: web.Request) -> web.Response:
    """REST wrapper for quiesce."""
    res = await orch.quiesce()
    return web.json_response(res)

async def run_bilingual_server() -> None:
    """Run both REST and MCP servers on a single event loop with stdout protection."""
    # [SHORING] Logging Moat: Ensure NO third-party library or print() uses stdout.
    sys.stdout = sys.stderr

    # 1. Start HTTP Server in background
    app = web.Application()
    app.router.add_get("/heartbeat", rest_heartbeat)
    app.router.add_post("/start", rest_start)
    app.router.add_post("/quiesce", rest_quiesce)

    runner = web.AppRunner(app)
    await runner.setup()
    # Binding to localhost only for security within the transitory refactor
    site = web.TCPSite(runner, "127.0.0.1", ATTENDANT_PORT)
    await site.start()
    logger.info("[BOOT] REST API active on %s", ATTENDANT_PORT)

    # 2. Run MCP Server (owns physical stdout)
    logger.info("[BOOT] MCP Identity: %s", get_fingerprint("MCP"))
    await mcp.run_stdio_async()

if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_bilingual_server())
