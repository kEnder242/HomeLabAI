import asyncio
import aiohttp
from aiohttp import web
import json
import logging
import argparse
import sys
import numpy as np
import random
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import os

# Equipment
if os.environ.get("DISABLE_EAR") == "1":
    logging.info("[CONFIG] EarNode disabled via env var.")
    EarNode = None
else:
    try:
        from equipment.ear_node import EarNode
    except ImportError:
        logging.warning("[STT] EarNode dependencies missing. Voice input will be unavailable.")
        EarNode = None

# Configuration
PORT = 8765
PYTHON_PATH = sys.executable
VERSION = "3.4.0"

# FORCE UNBUFFERED LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [LAB] %(levelname)s - %(message)s',
    stream=sys.stdout # Hits the redirected server.log immediately
)

class AcmeLab:
    NERVOUS_TICS = [
        "Thinking... Narf!",
        "Consulting the Big Guy...",
        "One moment, the Brain is loading...",
        "Processing... Poit!",
        "Just a second... Zort!",
        "Checking the archives...",
        "Egad, this is heavy math...",
        "Stand by..."
    ]

    def __init__(self, afk_timeout=None):
        self.residents = {}
        self.ear = None
        self.mode = "SERVICE_UNATTENDED"
        self.status = "BOOTING"
        self.connected_clients = set()
        self.shutdown_event = asyncio.Event()
        self.current_processing_task = None
        self.afk_timeout = afk_timeout
        self.lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../Portfolio_Dev/field_notes/data/round_table.lock")
        self.last_activity = 0.0
        self.active_file = None

    async def manage_session_lock(self, active=True):
        """Creates or removes the round_table.lock to prioritize Intercom."""
        try:
            if active:
                os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
                with open(self.lock_path, "w") as f:
                    f.write(str(os.getpid()))
                self.last_activity = time.time()
                logging.info(f"[LOCK] Intercom Active. Round Table Lock created.")
            else:
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
                    logging.info(f"[LOCK] Intercom Idle. Round Table Lock removed.")
        except Exception as e:
            logging.error(f"[LOCK] Error managing lock: {e}")

    async def session_monitor(self):
        """Monitors client activity and releases lock after 5 minutes of silence."""
        while not self.shutdown_event.is_set():
            await asyncio.sleep(30)
            if self.connected_clients and os.path.exists(self.lock_path):
                if time.time() - self.last_activity > 300:
                    await self.manage_session_lock(active=False)

    async def broadcast(self, message_dict):
        """Sends a JSON message to all connected clients."""
        if not self.connected_clients: return
        if message_dict.get("type") == "status":
            message_dict["version"] = VERSION
        message = json.dumps(message_dict)
        for ws in list(self.connected_clients):
            try:
                await ws.send_str(message)
            except Exception: pass

    async def monitor_task_with_tics(self, coro, websocket, delay=2.0):
        """Wraps a coroutine and emits nervous tics during long tasks."""
        task = asyncio.create_task(coro)
        while not task.done():
            done, pending = await asyncio.wait([task], timeout=delay)
            if task in done:
                return task.result()
            tic = random.choice(self.NERVOUS_TICS)
            try:
                await websocket.send_str(json.dumps({"brain": tic, "brain_source": "Pinky (Reflex)"}))
            except: pass
            delay = min(delay * 1.5, 5.0) 
        return task.result()

    def extract_json(self, text):
        """Robustly extracts JSON from LLM responses."""
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(0))
            except: pass
        return None

    async def load_residents_and_equipment(self):
        """Connects MCP nodes sequentially with live progress reporting."""
        logging.info(f"[BUILD] Loading Residents (v{VERSION})...")
        
        archive_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
        pinky_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/pinky_node.py"])
        brain_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

        try:
            # 1. Archive Node
            self.status = "BOOTING (Archive)"
            await self.broadcast({"type": "status", "state": "lobby", "message": "Connecting to Archive Node..."})
            async with stdio_client(archive_params) as (ar, aw):
                async with ClientSession(ar, aw) as archive:
                    await archive.initialize()
                    self.residents['archive'] = archive
                    logging.info("[LAB] Archive Connected.")

                    # 2. Pinky Node
                    self.status = "BOOTING (Pinky)"
                    await self.broadcast({"type": "status", "state": "lobby", "message": "Connecting to Pinky (Gateway)..."})
                    async with stdio_client(pinky_params) as (pr, pw):
                        async with ClientSession(pr, pw) as pinky:
                            await pinky.initialize()
                            self.residents['pinky'] = pinky
                            logging.info("[LAB] Pinky Connected.")

                            # 3. Brain Node
                            self.status = "BOOTING (Brain)"
                            await self.broadcast({"type": "status", "state": "lobby", "message": "Connecting to Brain (Architect)..."})
                            async with stdio_client(brain_params) as (br, bw):
                                async with ClientSession(br, bw) as brain:
                                    await brain.initialize()
                                    self.residents['brain'] = brain
                                    logging.info("[LAB] Brain Connected.")

                                    if self.shutdown_event.is_set(): return

                                    # 4. Async EarNode Load (Don't block the Lobby)
                                    if EarNode:
                                        self.status = "LOBBY (Ear Loading)"
                                        logging.info("[BUILD] Starting EarNode background load...")
                                        asyncio.create_task(self.background_load_ear())
                                    else:
                                        logging.info("[STT] EarNode disabled via environment.")

                                    self.status = "READY"
                                    logging.info("[READY] Lab is Open (Lobby Active).")
                                    await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Open."})
                                    
                                    # Main Server Heartbeat loop
                                    await self.shutdown_event.wait()
                                    logging.info("[STOP] Shutdown signal received.")

        except Exception as e:
            import traceback
            logging.error(f"[FATAL] Lab Startup Error: {e}")
            logging.error(traceback.format_exc())
        finally:
            logging.info("[FINISH] LAB SHUTDOWN COMPLETE")
            os._exit(0)

    async def background_load_ear(self):
        """Loads the heavy EarNode in a thread to keep the main loop responsive."""
        try:
            self.ear = await asyncio.to_thread(EarNode, callback=None)
            logging.info("[STT] EarNode Ready.")
            await self.broadcast({"type": "status", "state": "ready", "message": "EarNode Online (STT Active)."})
        except Exception as e:
            logging.error(f"[STT] EarNode Load Failed: {e}")

    async def boot_sequence(self, mode):
        self.mode = mode
        logging.info(f"[BOOT] Acme Lab Booting (Mode: {mode})...")
        asyncio.create_task(self.session_monitor())
        app = web.Application()
        app.add_routes([web.get('/', self.client_handler)])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        await self.load_residents_and_equipment()

    async def client_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connected_clients.add(ws)
        await self.manage_session_lock(active=True)
        
        status_msg = {"type": "status", "version": VERSION, "state": "ready" if self.status == "READY" else "lobby", "message": "Lab is Open."}
        await ws.send_str(json.dumps(status_msg))

        audio_buffer = np.zeros(0, dtype=np.int16)
        try:
            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(message.data)
                        if data.get("type") == "handshake":
                            logging.info(f"[HANDSHAKE] Client verified (v{data.get('version')}).")
                            if 'archive' in self.residents:
                                files_res = await self.residents['archive'].call_tool("list_cabinet")
                                await ws.send_str(json.dumps({"type": "cabinet", "files": json.loads(files_res.content[0].text)}))
                        elif data.get("type") == "text_input":
                            if self.status != "READY":
                                await ws.send_str(json.dumps({"brain": "Narf! Still in the Lobby...", "brain_source": "Pinky"}))
                                continue
                            self.current_processing_task = asyncio.create_task(self.process_query(data.get("content", ""), ws))
                    except Exception: pass
        finally:
            if ws in self.connected_clients: self.connected_clients.remove(ws)
            if not self.connected_clients:
                await self.manage_session_lock(active=False)
                # ONE-SHOT SHUTDOWN: Non-service modes exit on disconnect
                if self.mode != "SERVICE_UNATTENDED":
                    logging.info(f"[SHUTDOWN] Debug mode '{self.mode}' exiting after disconnect.")
                    self.shutdown_event.set()
        return ws

    async def process_query(self, query, websocket):
        """Simplified router for stabilization."""
        try:
            result = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": "", "memory": ""})
            decision = self.extract_json(result.content[0].text)
            if decision and decision.get("tool") == "reply_to_user":
                await websocket.send_str(json.dumps({"brain": decision["parameters"].get("text", "Narf!"), "brain_source": "Pinky"}))
        except Exception as e:
            logging.error(f"[QUERY_ERR] {e}")

if __name__ == "__main__":
    # DEFINITIVE BOOT MARKER
    print(f"--- [RESTART_MARKER] BOOT_ID: {time.time():.4f} ---", flush=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    args = parser.parse_args()
    lab = AcmeLab()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(lab.boot_sequence(args.mode))
    except KeyboardInterrupt: pass