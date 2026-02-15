import asyncio
import json
import logging
import os
import random
import sys
import time
from typing import Dict, Set

import aiohttp
import numpy as np
from aiohttp import web
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# Configuration
PORT = 8765
PYTHON_PATH = sys.executable
VERSION = "3.6.4"
BRAIN_HEARTBEAT_URL = "http://localhost:11434/api/tags"
ATTENDANT_PORT = 9999
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
STATUS_JSON = os.path.join(WORKSPACE_DIR, "field_notes/data/status.json")
ROUND_TABLE_LOCK = os.path.expanduser("~/Dev_Lab/HomeLabAI/round_table.lock")

# --- THE MONTANA PROTOCOL ---
def reclaim_logger():
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    fmt = logging.Formatter('%(asctime)s - [LAB] %(levelname)s - %(message)s')
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    root.setLevel(logging.INFO)
    logging.getLogger("nemo").setLevel(logging.ERROR)
    logging.getLogger("chromadb").setLevel(logging.ERROR)

class AcmeLab:
    def __init__(self, mode="SERVICE_UNATTENDED", afk_timeout=300):
        self.mode = mode
        self.afk_timeout = afk_timeout
        self.status = "INIT"
        self.connected_clients: Set[web.WebSocketResponse] = set()
        self.residents: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.shutdown_event = asyncio.Event()
        self.last_activity = time.time()
        self.last_save_event = 0.0
        self.reflex_ttl = 1.0
        self.banter_backoff = 0
        self.brain_online = False
        self.ear = None
        reclaim_logger()

    def load_ear(self):
        """Lazy load real EarNode logic."""
        try:
            sys.path.append(os.path.join(os.getcwd(), "src/equipment"))
            from ear_node import EarNode
            self.ear = EarNode()
            logging.info("[BOOT] EarNode initialized (NeMo).")
        except Exception as e:
            logging.error(f"[BOOT] Failed to load EarNode: {e}")

    async def broadcast(self, message_dict):
        if message_dict.get("type") == "status":
            message_dict["version"] = VERSION
        message = json.dumps(message_dict)
        for ws in list(self.connected_clients):
            try:
                await ws.send_str(message)
            except Exception:
                pass

    async def check_brain_health(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(BRAIN_HEARTBEAT_URL, timeout=2) as resp:
                    self.brain_online = (resp.status == 200)
        except Exception:
            self.brain_online = False
        return self.brain_online

    async def trigger_cooldown(self):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:{ATTENDANT_PORT}/refresh"
                await session.post(url, timeout=2)
        except Exception as e:
            logging.error(f"[HYGIENE] Cooldown failed: {e}")

    async def reflex_loop(self):
        tics = ["Narf!", "Poit!", "Zort!", "Egad!", "Trotro!"]
        while not self.shutdown_event.is_set():
            await asyncio.sleep(30)
            if "DEBUG" not in self.mode and self.afk_timeout and self.last_activity > 0:
                idle_time = time.time() - self.last_activity
                if idle_time > self.afk_timeout:
                    logging.info(f"[AFK] Idle {idle_time:.1f}s. Cooldown.")
                    await self.trigger_cooldown()
                    self.last_activity = 0.0
            if self.connected_clients and self.status == "READY":
                if (time.time() - self.last_activity > 60):
                    self.reflex_ttl -= 0.5
                else:
                    self.reflex_ttl = 1.0
                    self.banter_backoff = max(0, self.banter_backoff - 1)
                if self.reflex_ttl <= 0:
                    tic = random.choice(tics)
                    await self.broadcast({"brain": tic, "brain_source": "Pinky"})
                    self.banter_backoff += 1
                    self.reflex_ttl = 1.0 + (self.banter_backoff * 0.5)
            await self.check_brain_health()

    async def manage_session_lock(self, active: bool):
        try:
            if active:
                with open(ROUND_TABLE_LOCK, 'w') as f:
                    f.write(str(os.getpid()))
            else:
                if os.path.exists(ROUND_TABLE_LOCK):
                    os.remove(ROUND_TABLE_LOCK)
        except Exception:
            pass

    async def client_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connected_clients.add(ws)
        await self.manage_session_lock(active=True)
        audio_buffer = np.zeros(0, dtype=np.int16)
        try:
            await ws.send_str(json.dumps({
                "type": "status", "version": VERSION,
                "state": "ready" if self.status == "READY" else "lobby",
                "message": "Lab foyer is open."
            }))
            async def ear_poller():
                while not ws.closed:
                    if self.ear:
                        query = self.ear.check_turn_end()
                        if query:
                            await self.broadcast({"type": "final", "text": query})
                            await self.process_query(query, ws)
                    await asyncio.sleep(0.1)
            asyncio.create_task(ear_poller())
            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(message.data)
                    m_type = data.get("type")
                    if m_type == "handshake":
                        if 'archive' in self.residents:
                            try:
                                res = await self.residents['archive'].call_tool("list_cabinet")
                                if res.content and hasattr(res.content[0], 'text'):
                                    files = json.loads(res.content[0].text)
                                    await ws.send_str(json.dumps({"type": "cabinet", "files": files}))
                            except Exception as e:
                                logging.error(f"[HANDSHAKE] Failed: {e}")
                    elif m_type == "text_input":
                        query = data.get("content", "")
                        self.last_activity = time.time()
                        await self.process_query(query, ws)
                    elif m_type == "read_file":
                        fn = data.get("filename")
                        if 'archive' in self.residents:
                            res = await self.residents['archive'].call_tool("read_document", arguments={"filename": fn})
                            await ws.send_str(json.dumps({"type": "file_content", "filename": fn, "content": res.content[0].text}))
                elif message.type == aiohttp.WSMsgType.BINARY and self.ear:
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    if np.abs(chunk).max() > 500 and random.random() < 0.05:
                        logging.info("[AUDIO] Signal detected.")
                    if len(audio_buffer) >= 24000:
                        text = self.ear.process_audio(audio_buffer[:24000])
                        if text:
                            logging.info(f"[STT] Transcribed: {text}")
                            await self.broadcast({"text": text, "type": "transcription"})
                        audio_buffer = audio_buffer[16000:]
        finally:
            self.connected_clients.remove(ws)
            if not self.connected_clients:
                await self.manage_session_lock(active=False)
                if "DEBUG" in self.mode:
                    self.shutdown_event.set()
        return ws

    async def process_query(self, query, websocket):
        logging.info(f"[QUERY] Processing: {query}")
        async def handle_out(txt, source):
            if '"status": "shutdown"' in txt:
                logging.info("[LIFECYCLE] Shutdown signal intercepted.")
                await websocket.send_str(json.dumps({"brain": "Goodnight. Closing the Lab...", "brain_source": "System"}))
                self.shutdown_event.set()
                return True
            await websocket.send_str(json.dumps({"brain": txt, "brain_source": source}))
            return True
        if self.mode == "DEBUG_PINKY":
            if 'pinky' in self.residents:
                res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": ""})
                return await handle_out(res.content[0].text, "Pinky")
        if 'pinky' in self.residents:
            try:
                res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": ""})
                pinky_out = res.content[0].text
                if "ask_brain" in pinky_out or "Brain" in query:
                    if 'brain' in self.residents and self.brain_online:
                        b_res = await self.residents['brain'].call_tool("deep_think", arguments={"task": query})
                        return await handle_out(b_res.content[0].text, "Brain")
                if "close_lab" in pinky_out or "close the lab" in query.lower():
                    if 'architect' in self.residents:
                        a_res = await self.residents['architect'].call_tool("close_lab")
                        return await handle_out(a_res.content[0].text, "Architect")
                return await handle_out(pinky_out, "Pinky")
            except Exception as e:
                logging.error(f"[TRIAGE] Pinky failed: {e}")
        await websocket.send_str(json.dumps({"brain": f"Hearing: {query}", "brain_source": "Pinky (Fallback)"}))
        return False

    async def boot_residents(self):
        nodes = [
            ("archive", "src/nodes/archive_node.py"),
            ("brain", "src/nodes/brain_node.py"),
            ("pinky", "src/nodes/pinky_node.py"),
            ("architect", "src/nodes/architect_node.py")
        ]
        for name, path in nodes:
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{os.getcwd()}/src"
                params = StdioServerParameters(command=PYTHON_PATH, args=[path], env=env)
                cl_stack = await self.exit_stack.enter_async_context(stdio_client(params))
                session = await self.exit_stack.enter_async_context(ClientSession(cl_stack[0], cl_stack[1]))
                await session.initialize()
                self.residents[name] = session
                logging.info(f"[BOOT] {name.upper()} online.")
            except Exception as e:
                logging.error(f"[BOOT] Failed to load {name}: {e}")
        self.status = "READY"
        logging.info("[READY] Lab is Open.")

    async def run(self, disable_ear=True):
        if not disable_ear:
            self.load_ear()
        app = web.Application()
        app.router.add_get("/", self.client_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        try:
            await site.start()
            logging.info(f"[BOOT] Server on {PORT}")
            asyncio.create_task(self.boot_residents())
            asyncio.create_task(self.reflex_loop())
            await self.shutdown_event.wait()
        finally:
            logging.info("[SHUTDOWN] Closing residents...")
            # Use try/except to avoid exit_stack errors from TaskGroups
            try:
                await self.exit_stack.aclose()
            except Exception: pass
            await runner.cleanup()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    parser.add_argument("--afk-timeout", type=int, default=300)
    parser.add_argument("--disable-ear", action="store_true", default=False)
    args = parser.parse_args()
    lab = AcmeLab(mode=args.mode, afk_timeout=args.afk_timeout)
    asyncio.run(lab.run(disable_ear=args.disable_ear))
