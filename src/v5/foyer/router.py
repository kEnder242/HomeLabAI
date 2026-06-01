import asyncio
import json
import logging
import os
import time
import uuid
import random
import aiohttp
from aiohttp import web
import aiohttp_cors
import sys

# Add src to path for logic and equipment imports
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if LAB_DIR not in sys.path:
    sys.path.append(LAB_DIR)

from v5.common.types import IntentEvent, LabStatus
from v5.common.residents import ResidentManager
from logic.cognitive_hub import CognitiveHub
from equipment.sensory_manager import SensoryManager

# [Task 4.2] V5 Foyer: The Always-Online Router (Full Feature)
# Objective: Host the Cognitive Hub and provide 100% foyer uptime.

PORT = 8765
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [FOYER] - %(levelname)s - %(message)s')

class FoyerRouter:
    def __init__(self):
        self.connected_clients = set()
        self.session_token = uuid.uuid4().hex[:8]
        self.residents = ResidentManager(self.session_token)
        self.sensory = SensoryManager(self.broadcast)
        self.cognitive = CognitiveHub(
            self.residents.residents, 
            self.broadcast, 
            self.sensory, 
            get_vram_status=self.get_vram_status,
            trigger_morning_briefing=self.trigger_morning_briefing
        )
        self.status = LabStatus()
        self.app = web.Application()
        self.setup_routes()

    async def trigger_morning_briefing(self):
        logging.info("[FOYER] Triggering Morning Briefing...")
        # Future: Logic for morning synthesis
        pass
        
    def get_vram_status(self, force=False):
        return self.status.vocal

    def setup_routes(self):
        self.app.add_routes([
            web.get('/', self.handle_websocket),
            web.get('/hub', self.handle_websocket),
            web.post('/inject', self.handle_rest_inject),
            web.get('/health', self.handle_health),
            web.get('/status', self.handle_status),
            web.post('/wake', self.handle_wake),
            web.post('/stop', self.handle_stop)
        ])
        
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def handle_health(self, request):
        return web.json_response({"status": "ONLINE", "version": "5.0.0-foyer"})

    async def handle_status(self, request):
        return web.json_response(self.status.to_dict())

    async def handle_wake(self, request):
        """[FEAT-318.12] Wake signal to ignition."""
        # Future: IPC to Ignition Manager
        return web.json_response({"status": "WAKING"})

    async def handle_stop(self, request):
        """Graceful logical stop."""
        await self.residents.shutdown()
        return web.json_response({"status": "STOPPED"})

    async def handle_rest_inject(self, request):
        data = await request.json()
        query = data.get("query")
        if query:
            event = await self.enqueue_intent(query, source="REST")
            return web.json_response({"status": "QUEUED", "id": event.id})
        return web.json_response({"status": "ERROR", "message": "No query provided"}, status=400)

    async def handle_websocket(self, ws_request):
        ws = web.WebSocketResponse(heartbeat=30.0)
        await ws.prepare(ws_request)
        
        socket_id = str(uuid.uuid4())[:8]
        self.connected_clients.add(ws)
        logging.info(f"Client connected: {socket_id}")
        
        await ws.send_str(json.dumps(self.status.to_dict()))
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    m_type = data.get("type")
                    
                    if m_type == "handshake":
                        await ws.send_str(json.dumps({
                            "type": "status", 
                            "state": "connected", 
                            "socket_id": socket_id,
                            "version": "5.0.0-foyer"
                        }))
                    elif m_type == "text_input":
                        query = data.get("content")
                        # [Task 2.1] Integrated Reasoning
                        asyncio.create_task(self.cognitive.process_query(query))
                    elif m_type == "workspace_save":
                        fn = data.get("filename")
                        content = data.get("content")
                        # Delegate to cognitive hub for 'Vibe Check'
                        asyncio.create_task(self.cognitive.handle_workspace_save(fn, content, self.broadcast))
                    elif m_type == "read_file":
                        fn = data.get("filename")
                        archive = self.residents.get_node("archive")
                        if archive:
                            res = await archive.call_tool("read_document", {"filename": fn})
                            await ws.send_str(json.dumps({
                                "type": "file_content",
                                "filename": fn,
                                "content": res.content[0].text,
                                "brain_source": "System"
                            }))
                    elif m_type == "mic_state":
                        active = data.get("active", False)
                        self.status.mic_active = active
                        logging.info(f"[SENSORY] Mic state changed: {active}")
                        
        finally:
            if ws in self.connected_clients:
                self.connected_clients.remove(ws)
            logging.info(f"Client disconnected: {socket_id}")
            
        return ws

    async def enqueue_intent(self, query, source):
        event = IntentEvent(query=query, source=source)
        try:
            with open(QUEUE_FILE, "a") as f:
                f.write(event.to_json() + "\n")
            return event
        except Exception as e:
            logging.error(f"Failed to enqueue: {e}")
            raise

    async def broadcast(self, message_dict):
        """[FEAT-221] Safe broadcast with schema enforcement and forensic integrity."""
        m_type = message_dict.get("type", "chat")
        m_content = message_dict.get("brain") or message_dict.get("message")
        if not m_content:
            if m_type == "status": return
            m_content = "EMPTY_CONTENT"
        m_source = message_dict.get("brain_source", "System")

        # [Task 8.4] Forensic Integrity
        try:
            from infra.forensic_ledger import ledger
            if m_type in ["chat", "crosstalk"]:
                ledger.record_thought(m_source, m_content, role=m_type.upper())
        except Exception as e:
            logging.error(f"[LEDGER] Failed to record thought: {e}")

        # Schema Enrichment
        message_dict["type"] = m_type
        message_dict["brain"] = m_content
        message_dict["brain_source"] = m_source
        message_dict["hub_pid"] = os.getpid()
        if "msg_id" not in message_dict:
            message_dict["msg_id"] = uuid.uuid4().hex[:12]

        logging.info(f"[BROADCAST] [{m_type.upper()}] ({m_source}): {m_content[:60]}...")

        # Broadcast to sockets
        msg_str = json.dumps(message_dict)
        for ws in list(self.connected_clients):
            try:
                if not ws.closed:
                    await ws.send_str(msg_str)
                else:
                    self.connected_clients.remove(ws)
            except Exception:
                if ws in self.connected_clients:
                    self.connected_clients.remove(ws)

    async def status_watcher(self):
        """Polls status.json for hardware state updates."""
        last_mtime = 0
        while True:
            try:
                if os.path.exists(STATUS_JSON):
                    mtime = os.path.getmtime(STATUS_JSON)
                    if mtime > last_mtime:
                        with open(STATUS_JSON, "r") as f:
                            data = json.load(f)
                            self.status.state = data.get("state", "UNKNOWN")
                            self.status.vocal = data.get("vocal", False)
                            self.status.engine_up = data.get("engine_up", False)
                        last_mtime = mtime
            except Exception as e:
                logging.error(f"Status watcher error: {e}")
            await asyncio.sleep(1)

    async def reflex_loop(self):
        """[FEAT-365] Characterful reflexes (tics)."""
        tics = ["Narf!", "Poit!", "Zort!", "Checking circuits...", "Egad!", "Trotro!"]
        while True:
            # Only tic if operational and not typing
            if self.status.state == "OPERATIONAL" and self.connected_clients:
                if random.random() < 0.1: # 10% chance
                    await self.broadcast({"type": "crosstalk", "brain": random.choice(tics), "brain_source": "Pinky"})
            await asyncio.sleep(30)

    async def ear_poller_loop(self):
        """[FEAT-259.1] Global Sensory Sentinel."""
        logging.info("[SENSORY] Global Ear Poller active.")
        while True:
            try:
                query = self.sensory.check_turn_end()
                if query:
                    logging.info(f"[SENSORY] Turn end detected: {query}")
                    asyncio.create_task(self.cognitive.process_query(f"[ME] {query}"))
            except Exception as e:
                logging.error(f"[SENSORY] Poller failure: {e}")
            await asyncio.sleep(0.1)

    async def start_services(self):
        """[FEAT-145] Sensory Boot."""
        logging.info("[FOYER] Starting background services...")
        await self.sensory.load()

    async def scheduled_tasks_loop(self):
        """[FEAT-266] Periodic Maintenance (Nibbler)."""
        last_nibble = 0
        while True:
            if time.time() - last_nibble > 600:
                logging.info("[ALARM] Triggering periodic Nibbler pass...")
                # Future: Spawn nibbler subprocess
                last_nibble = time.time()
            await asyncio.sleep(60)

    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start_services())
        loop.create_task(self.status_watcher())
        loop.create_task(self.reflex_loop())
        loop.create_task(self.ear_poller_loop())
        loop.create_task(self.scheduled_tasks_loop())
        web.run_app(self.app, port=PORT)

if __name__ == "__main__":
    router = FoyerRouter()
    router.run()
