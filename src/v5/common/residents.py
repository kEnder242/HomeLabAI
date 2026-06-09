import asyncio
import os
import logging
import sys
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, Optional

# [Task 4.1] V5 Resident Manager: Modular Node Spawner
# Objective: Decouple node lifecycle from the foyer server.

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB_DIR = os.path.dirname(SRC_DIR)
PYTHON_PATH = sys.executable

class ResidentManager:
    def __init__(self, session_token: str):
        self.residents: Dict[str, ClientSession] = {}
        self.transports = [] # [NEW] Manual transport tracking
        self.session_token = session_token
        self.booted = False
        self.booting = False
        self._boot_lock = asyncio.Lock()

    async def boot_all(self):
        """Idempotent boot of all logical nodes with timed liveness check."""
        async with self._boot_lock:
            # [Task 4.4] Liveness Probe: Verify nodes are actually responsive
            if self.booted and not self.booting:
                try:
                    if "pinky" in self.residents:
                        # MCP ping with strict timeout to detect zombies
                        await asyncio.wait_for(self.residents["pinky"].list_tools(), timeout=2.0)
                    else:
                        self.booted = False # Missing node
                except (Exception, asyncio.TimeoutError):
                    logging.warning("[RESIDENTS] Node stack stale, timed out, or defunct. Re-syncing...")
                    self.booted = False
                    # Manual close of stale transports
                    for transport in self.transports:
                        try:
                            await asyncio.wait_for(transport.__aexit__(None, None, None), timeout=1.0)
                        except Exception: pass
                    self.transports.clear()
                    self.residents.clear()

            if self.booted or self.booting:
                return
            
            self.booting = True
            try:
                logging.info("[RESIDENTS] Booting node stack...")
                n_dir = os.path.join(SRC_DIR, "nodes")
                nodes = [
                    ("pinky", os.path.join(n_dir, "pinky_node.py")),
                    ("archive", os.path.join(n_dir, "archive_node.py")),
                    ("thought", os.path.join(n_dir, "thought_node.py")),
                    ("brain", os.path.join(n_dir, "brain_node.py")),
                    ("lab", os.path.join(n_dir, "lab_node.py")),
                ]

                # Launch all node boots concurrently
                boot_tasks = []
                for name, path in nodes:
                    boot_tasks.append(self._boot_node(name, path))
                
                await asyncio.gather(*boot_tasks)
                self.booted = True
                logging.info("[RESIDENTS] All nodes fully synchronized.")
            finally:
                self.booting = False

    async def _boot_node(self, name, path):
        try:
            logging.info(f"[RESIDENTS] Syncing {name.upper()}...")
            # Settle window (legacy requirement)
            await asyncio.sleep(1.0)
            
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{SRC_DIR}"
            env["LAB_IMMUNITY_TOKEN"] = self.session_token
            node_args = [path, "--role", name.upper(), "--session", self.session_token]
            
            params = StdioServerParameters(command=PYTHON_PATH, args=node_args, env=env)
            
            # [Task 4.1] Manual context management to avoid anyio task mismatch
            transport_cm = stdio_client(params)
            read_stream, write_stream = await transport_cm.__aenter__()
            self.transports.append(transport_cm)
            
            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()
            
            self.residents[name] = session
            logging.info(f"[RESIDENTS] {name.upper()} Node active.")
        except Exception as e:
            logging.error(f"[RESIDENTS] Failed to sync {name.upper()}: {e}")

    async def shutdown(self):
        """Graceful release of all node contexts with manual cleanup."""
        async with self._boot_lock:
            logging.info("[RESIDENTS] Releasing node stack...")
            
            # 1. Close Sessions
            for name in list(self.residents.keys()):
                session = self.residents.pop(name)
                try:
                    await asyncio.wait_for(session.__aexit__(None, None, None), timeout=1.0)
                except Exception: pass
            
            # 2. Close Transports
            for transport in self.transports:
                try:
                    await asyncio.wait_for(transport.__aexit__(None, None, None), timeout=1.0)
                except Exception: pass
            
            self.transports.clear()
            self.residents.clear()
            self.booted = False
            self.booting = False
            logging.info("[RESIDENTS] Node stack released.")
        self.booting = False
        self._boot_lock = asyncio.Lock()

    def get_node(self, name: str) -> Optional[ClientSession]:
        return self.residents.get(name)
