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

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [LAB] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
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
        self.active_file = None # Tracks 'this file' for the workbench

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
                    logging.info("[LOCK] Session timeout hit. Releasing lock for background tasks.")
                    await self.manage_session_lock(active=False)

    async def afk_watcher(self):
        """Shuts down the Lab if no client connects within the timeout."""
        if not self.afk_timeout: return
        logging.info(f"[AFK] Watcher started (Timeout: {self.afk_timeout}s).")
        await asyncio.sleep(self.afk_timeout)
        if not self.connected_clients and not self.shutdown_event.is_set():
            logging.warning("[AFK] No client connected. Shutting down.")
            self.shutdown_event.set()

    async def broadcast(self, message_dict):
        """Sends a JSON message to all connected clients."""
        if not self.connected_clients: return
        if message_dict.get("type") == "status":
            message_dict["version"] = VERSION
        message = json.dumps(message_dict)
        for ws in self.connected_clients:
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
            logging.info(f"[TIC] Emitting: {tic}")
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
            try:
                return json.loads(match.group(0))
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

                    if self.shutdown_event.is_set(): return

                    if EarNode:
                        logging.info("[BUILD] Loading EarNode...")
                        self.ear = await asyncio.to_thread(EarNode, callback=None)
                        logging.info("[STT] EarNode Initialized.")

                    if self.shutdown_event.is_set(): return

                    if self.mode == "DEBUG_BRAIN":
                        await brain.call_tool("wake_up")

                    self.status = "READY"
                    logging.info("[READY] Lab Fully Operational!")
                    await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Open."})
                    asyncio.create_task(self.afk_watcher())
                    await self.shutdown_event.wait()

        except Exception as e:
            logging.error(f"[ERROR] Lab Explosion: {e}")
        finally:
            logging.info("[FINISH] LAB SHUTDOWN COMPLETE")
            os._exit(0)

    async def boot_sequence(self, mode):
        self.mode = mode
        logging.info(f"[LAB] Acme Lab Booting (Mode: {mode})...")
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
        logging.info("[LAB] Client entered the Lobby.")
        await self.manage_session_lock(active=True)
        
        status_msg = {"type": "status", "version": VERSION, "state": "ready", "message": "Lab is Open."}
        await ws.send_str(json.dumps(status_msg))

        # Initial file list sync
        try:
            files_res = await self.residents['archive'].call_tool("list_cabinet")
            await ws.send_str(json.dumps({"type": "cabinet", "files": json.loads(files_res.content[0].text)}))
        except: pass

        audio_buffer = np.zeros(0, dtype=np.int16)
        try:
            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    if self.status != "READY": continue
                    try:
                        data = json.loads(message.data)
                        if data.get("type") == "handshake":
                            logging.info(f"[HANDSHAKE] Client verified (v{data.get('version')}).")
                        elif data.get("type") == "text_input":
                            query = data.get("content", "")
                            logging.info(f"[TEXT] Rx: {query}")
                            self.last_activity = time.time()
                            await self.manage_session_lock(active=True)
                            if self.current_processing_task and not self.current_processing_task.done():
                                self.current_processing_task.cancel()
                            self.current_processing_task = asyncio.create_task(self.process_query(query, ws))
                        elif data.get("type") == "select_file":
                            self.active_file = data.get("filename")
                            logging.info(f"[WORKBENCH] Active file set to: {self.active_file}")
                    except: pass
                elif message.type == aiohttp.WSMsgType.BINARY:
                    if self.status != "READY" or not self.ear: continue
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    if len(audio_buffer) >= 32000:
                        text = self.ear.process_audio(audio_buffer[:32000])
                        if text:
                            logging.info(f"[STT] Tx: {text}")
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
        """The Workbench Router: No history limits, File-Aware."""
        logging.info(f"[LAB] Workbench Session: '{query}'")
        try:
            # 1. Permanent History (No rolling window)
            # We'll retrieve the last 20 messages for context (effectively no limit for most sessions)
            history_res = await self.residents['archive'].call_tool("get_history", arguments={"limit": 20})
            lab_history_raw = history_res.content[0].text
            
            # 2. File Context
            file_context = ""
            if self.active_file:
                try:
                    file_res = await self.residents['archive'].call_tool("read_document", arguments={"filename": self.active_file})
                    file_content = file_res.content[0].text
                    file_context = f"\n[CURRENTLY OPEN FILE: {self.active_file}]\n{file_content}\n"
                except: pass

            turn_count = 0
            MAX_TURNS = 10
            decision = None

            while turn_count < MAX_TURNS:
                turn_count += 1
                
                # Decision with enhanced context
                if not decision:
                    full_context = f"{file_context}\nRECENT HISTORY:\n{lab_history_raw}"
                    result = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": full_context, "memory": ""})
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
                    # Brain gets the full history + file context
                    augmented_query = f"{file_context}\nTASK: {instruction}"
                    brain_res = await self.monitor_task_with_tics(
                        self.residents['brain'].call_tool("deep_think", arguments={"query": augmented_query, "context": lab_history_raw}),
                        websocket
                    )
                    brain_out = brain_res.content[0].text
                    
                    # 50/50 Logic: Broadcast to dedicated Brain window
                    await websocket.send_str(json.dumps({"brain": brain_out, "brain_source": "The Brain", "channel": "insight"}))
                    
                    # Optionally suppress in Pinky window
                    # await websocket.send_str(json.dumps({"brain": "[Analysis Complete. See Insight Panel.]", "brain_source": "Pinky"}))
                    decision = None # Loop back

                elif tool == "update_whiteboard":
                    content = params.get("content", "")
                    await self.residents['brain'].call_tool("update_whiteboard", arguments={"content": content})
                    await websocket.send_str(json.dumps({"brain": content, "brain_source": "The Editor", "channel": "whiteboard"}))
                    decision = None

                else:
                    # Generic tool execution (vram, health, etc)
                    try:
                        res = await self.residents['pinky'].call_tool(tool, arguments=params)
                        out = res.content[0].text
                        await websocket.send_str(json.dumps({"brain": out, "brain_source": "System"}))
                    except: pass
                    decision = None

            # Save to permanent history
            await self.residents['archive'].call_tool("save_interaction", arguments={"user_query": query, "response": "Workbench Session Complete."})

        except Exception as e:
            logging.error(f"[ERROR] {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    args = parser.parse_args()
    lab = AcmeLab()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(lab.boot_sequence(args.mode))
    except KeyboardInterrupt:
        pass