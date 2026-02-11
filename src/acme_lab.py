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
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../server.log")

# Hardened Code-Level Logging
class FlushHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [LAB] %(levelname)s - %(message)s',
    handlers=[FlushHandler(LOG_FILE, mode='a')]
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
            except: pass

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
        """Connects MCP nodes and loads ML models."""
        logging.info(f"[BUILD] Loading Residents & Equipment (v{VERSION})...")
        archive_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
        pinky_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/pinky_node.py"])
        brain_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

        try:
            async with stdio_client(archive_params) as (ar, aw), \
                       stdio_client(pinky_params) as (pr, pw), \
                       stdio_client(brain_params) as (br, bw):
                
                async with ClientSession(ar, aw) as archive, \
                           ClientSession(pr, pw) as pinky, \
                           ClientSession(br, bw) as brain:
                    
                    await archive.initialize()
                    await pinky.initialize()
                    await brain.initialize()
                    
                    self.residents['archive'] = archive
                    self.residents['pinky'] = pinky
                    self.residents['brain'] = brain
                    logging.info("[LAB] Residents Connected.")

                    if EarNode:
                        logging.info("[BUILD] Initializing EarNode...")
                        self.ear = await asyncio.to_thread(EarNode, callback=None)
                        logging.info("[STT] EarNode Initialized.")

                    self.status = "READY"
                    logging.info("[READY] Lab Fully Operational!")
                    await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Open."})
                    await self.shutdown_event.wait()

        except Exception as e:
            logging.error(f"[FATAL] Lab Startup Error: {e}")
        finally:
            os._exit(0)

    async def boot_sequence(self, mode):
        self.mode = mode
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
        
        status_msg = {"type": "status", "version": VERSION, "state": "ready" if self.status == "READY" else "waiting", "message": "Lab is Open."}
        await ws.send_str(json.dumps(status_msg))

        audio_buffer = np.zeros(0, dtype=np.int16)
        try:
            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(message.data)
                        # --- LOBBY ACCESS: Handshake and File browsing are allowed during boot ---
                        if data.get("type") == "handshake":
                            logging.info(f"[HANDSHAKE] Client verified (v{data.get('version')}).")
                            try:
                                # Archive node usually boots fast; try to sync cabinet immediately
                                if 'archive' in self.residents:
                                    files_res = await self.residents['archive'].call_tool("list_cabinet")
                                    await ws.send_str(json.dumps({"type": "cabinet", "files": json.loads(files_res.content[0].text)}))
                            except: pass
                        elif data.get("type") == "select_file":
                            self.active_file = data.get("filename")
                        elif data.get("type") == "read_file":
                            filename = data.get("filename")
                            if 'archive' in self.residents:
                                res = await self.residents['archive'].call_tool("read_document", arguments={"filename": filename})
                                await ws.send_str(json.dumps({"type": "file_content", "filename": filename, "content": res.content[0].text}))
                        
                        # --- READINESS GATE: Drop complex queries if model isn't ready ---
                        elif data.get("type") == "text_input":
                            if self.status != "READY":
                                await ws.send_str(json.dumps({"brain": "Narf! I'm still in the Lobby. Give me a moment to wake the Big Guy...", "brain_source": "Pinky"}))
                                continue
                            
                            query = data.get("content", "")
                            self.last_activity = time.time()
                            if self.current_processing_task and not self.current_processing_task.done():
                                self.current_processing_task.cancel()
                            self.current_processing_task = asyncio.create_task(self.process_query(query, ws))
                    except Exception as e:
                        logging.error(f"[LOBBY_ERR] {e}")
                elif message.type == aiohttp.WSMsgType.BINARY:
                    if self.status != "READY" or not self.ear: continue
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    if len(audio_buffer) >= 32000:
                        text = self.ear.process_audio(audio_buffer[:32000])
                        if text:
                            if self.current_processing_task and not self.current_processing_task.done():
                                self.current_processing_task.cancel()
                            await ws.send_str(json.dumps({"text": text}))
                        audio_buffer = audio_buffer[32000-8000:] 
                    query = self.ear.check_turn_end()
                    if query:
                        await ws.send_str(json.dumps({"type": "final", "text": query}))
                        self.current_processing_task = asyncio.create_task(self.process_query(query, ws))
        finally:
            if ws in self.connected_clients: self.connected_clients.remove(ws)
            if not self.connected_clients: await self.manage_session_lock(active=False)
        return ws

    async def process_query(self, query, websocket):
        """Standard v3.4.0 Workbench Router."""
        try:
            lab_history = [f"User: {query}"]
            turn_count = 0
            MAX_TURNS = 10
            decision = None

            while turn_count < MAX_TURNS:
                turn_count += 1
                lab_context = "\n".join(lab_history[-6:])
                
                if not decision:
                    result = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": lab_context, "memory": ""})
                    decision = self.extract_json(result.content[0].text)
                
                if not decision: break
                tool = decision.get("tool")
                params = decision.get("parameters", {})
                await self.broadcast({"type": "debug", "event": "PINKY_DECISION", "data": decision})

                if tool == "reply_to_user":
                    text = params.get("text", "Narf!")
                    await websocket.send_str(json.dumps({"brain": text, "brain_source": "Pinky"}))
                    break
                elif tool in ["delegate_to_brain", "start_draft", "refine_draft"]:
                    instruction = params.get("instruction", query)
                    brain_res = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": instruction, "context": lab_context}), websocket)
                    brain_out = brain_res.content[0].text
                    await websocket.send_str(json.dumps({"brain": brain_out, "brain_source": "Brain", "channel": "insight"}))
                    lab_history.append(f"Brain: {brain_out}")
                    decision = None
                else:
                    res = await self.residents['pinky'].call_tool(tool, arguments=params)
                    out = res.content[0].text
                    await websocket.send_str(json.dumps({"brain": out, "brain_source": "System"}))
                    lab_history.append(f"System: {out}")
                    decision = None

            await self.residents['archive'].call_tool("save_interaction", arguments={"user_query": query, "response": "\n".join(lab_history)})
        except Exception as e:
            logging.error(f"[ERROR] {e}")

if __name__ == "__main__":
    import time
    # DEFINITIVE RESTART MARKER - Now hits both stdout and the hardened log file
    msg = f"--- [RESTART_MARKER] BOOT_ID: {time.time():.4f} ---"
    print(msg, flush=True)
    logging.info(msg)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    args = parser.parse_args()
    lab = AcmeLab()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(lab.boot_sequence(args.mode))
    except KeyboardInterrupt:
        pass