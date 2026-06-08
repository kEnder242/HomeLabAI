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
        self.session_token = session_token
        self.stack = AsyncExitStack()
        self.booted = False
        self.booting = False
        self._boot_lock = asyncio.Lock()

    async def boot_all(self):
        """Idempotent boot of all logical nodes."""
        async with self._boot_lock:
            if self.booted:
                return
            self.booting = True
        
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
        
        try:
            await asyncio.gather(*boot_tasks)
            self.booted = True
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
            cl_stack = await self.stack.enter_async_context(stdio_client(params))
            session = await self.stack.enter_async_context(ClientSession(cl_stack[0], cl_stack[1]))
            await session.initialize()
            
            self.residents[name] = session
            logging.info(f"[RESIDENTS] {name.upper()} Node active.")
        except Exception as e:
            logging.error(f"[RESIDENTS] Failed to sync {name.upper()}: {e}")

    async def shutdown(self):
        """Graceful release of all node contexts."""
        logging.info("[RESIDENTS] Releasing node stack...")
        await self.stack.aclose()
        self.residents.clear()
        self.booted = False
        self.booting = False
        self._boot_lock = asyncio.Lock()

    def get_node(self, name: str) -> Optional[ClientSession]:
        return self.residents.get(name)
