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

# Add src to path
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if LAB_DIR not in sys.path:
    sys.path.append(LAB_DIR)

from v5.common.types import IntentEvent, LabStatus
from v5.common.residents import ResidentManager
from logic.cognitive_hub import CognitiveHub
from equipment.sensory_manager import SensoryManager

# [Task 4.2] V5 Foyer: The Logic Master
# Objective: Host the Cognitive Hub and manage logical node lifecycle.

PORT = 8765
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")

# Configure logging early
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [FOYER] - %(levelname)s - %(message)s')
logger = logging.getLogger("foyer")

# [FEAT-122] Kernel-Level Visibility
try:
    import setproctitle
except ImportError:
    setproctitle = None

def get_style_key():
    """[FEAT-267] Dynamic Key Discovery for Lab REST calls."""
    style_path = os.path.join(WORKSPACE_DIR, "field_notes/style.css")
    if os.path.exists(style_path):
        import hashlib
        with open(style_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    return "default_key"

class FoyerRouter:
    def __init__(self):
        # Rename process
        if setproctitle:
            setproctitle.setproctitle("acme_foyer_v5")
            
        self.connected_clients = set()
        self.session_token = uuid.uuid4().hex[:8]
        self.residents = ResidentManager(self.session_token)
        self.sensory = SensoryManager(self.broadcast)
        self.waterfall_queue = asyncio.Queue()
        
        self.status = LabStatus()
        self.cognitive = CognitiveHub(
            self.residents.residents, 
            self.broadcast, 
            self.sensory, 
            get_vram_status=self.get_vram_status,
            trigger_morning_briefing=self.trigger_morning_briefing,
            waterfall_queue=self.waterfall_queue
        )
        self.app = web.Application()
        self.app.on_startup.append(self.on_startup)
        self.setup_routes()
        
    def get_vram_status(self, force=False):
        return self.status.vocal

    async def trigger_morning_briefing(self):
        logger.info("Triggering Morning Briefing...")
        pass

    def setup_routes(self):
        self.app.add_routes([
            web.get('/', self.handle_websocket),
            web.get('/hub', self.handle_websocket),
            web.post('/inject', self.handle_rest_inject),
            web.post('/stream_ingest', self.handle_stream_ingest),
            web.post('/status_update', self.handle_status_update),
            web.get('/health', self.handle_health),
            web.get('/status', self.handle_status)
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

    async def handle_status_update(self, request):
        """REST endpoint for the Ignition Manager to push state changes."""
        try:
            data = await request.json()
            # Update local status object
            self.status.state = data.get("state", self.status.state)
            self.status.vocal = data.get("vocal", self.status.vocal)
            self.status.engine_up = data.get("engine_up", self.status.engine_up)
            
            # Relay to Hub if nodes need booting
            if self.status.vocal and not self.residents.booted:
                asyncio.create_task(self.sensory.load())
            
            return web.Response(status=200)
        except Exception as e:
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

    async def on_startup(self, app):
        """[FEAT-339] Clean task scheduling on event loop start."""
        logger.info("V5 Foyer Router starting background tasks...")
        asyncio.create_task(self.reflex_loop())
        asyncio.create_task(self.ear_poller_loop())
        asyncio.create_task(self.scheduled_tasks_loop())
        asyncio.create_task(self.queue_drainer())
        asyncio.create_task(self.waterfall_drainer())

    async def handle_health(self, request):
        return web.json_response({"status": "ONLINE", "version": "5.0.0-foyer"})

    async def handle_status(self, request):
        return web.json_response(self.status.to_dict())

    async def handle_rest_inject(self, request):
        data = await request.json()
        query = data.get("query")
        if query:
            event = await self.enqueue_intent(query, source="REST")
            return web.json_response({"status": "QUEUED", "id": event.id})
        return web.json_response({"status": "ERROR", "message": "No query provided"}, status=400)

    async def handle_websocket(self, ws_request):
        # [FEAT-326] Socket Persistence: 300s heartbeat for cold-wake resilience
        ws = web.WebSocketResponse(heartbeat=300.0)
        await ws.prepare(ws_request)
        
        socket_id = str(uuid.uuid4())[:8]
        self.connected_clients.add(ws)
        logger.info(f"Client connected: {socket_id}")
        
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
                        await self.enqueue_intent(query, source=f"WS_{socket_id}")
                    elif m_type == "workspace_save":
                        fn = data.get("filename")
                        content = data.get("content")
                        asyncio.create_task(self.cognitive.handle_workspace_save(fn, content))
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
                        logger.info(f"Mic state changed: {active}")
                        
        finally:
            if ws in self.connected_clients:
                self.connected_clients.remove(ws)
            logger.info(f"Client disconnected: {socket_id}")
            
        return ws

    async def handle_stream_ingest(self, request):
        """[FEAT-233.7] Real-time token ingestion from decoupled nodes."""
        try:
            data = await request.json()
            # Relay to Cognitive Hub for waterfall overhearing
            self.cognitive.on_token({
                "brain": data.get("text", ""),
                "brain_source": data.get("source", "Unknown"),
                "final": data.get("final", False)
            })
            return web.Response(status=200)
        except Exception as e:
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

    async def enqueue_intent(self, query, source):
        event = IntentEvent(query=query, source=source)
        try:
            os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
            with open(QUEUE_FILE, "a") as f:
                f.write(event.to_json() + "\n")
            
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"[FOYER] Request {event.id} secured in queue. Igniting Brain...",
                "brain_source": "Foyer"
            })
            return event
        except Exception as e:
            logger.error(f"Failed to enqueue: {e}")
            raise

    async def broadcast(self, message_dict):
        """[FEAT-221] Safe broadcast with loop-congestion protection."""
        m_type = message_dict.get("type", "chat")
        m_content = message_dict.get("brain") or message_dict.get("message")
        if not m_content:
            if m_type == "status": pass
            else: return

        # [NEW] Check if we are being called from a synchronous context
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                 # Should not happen in aiohttp
                 return
        except Exception: return

        # Perform formatting and logging
        m_source = message_dict.get("brain_source", "System")
        try:
            from infra.forensic_ledger import ledger
            if m_type in ["chat", "crosstalk"]:
                ledger.record_thought(m_source, m_content, role=m_type.upper())
        except Exception: pass

        message_dict["type"] = m_type
        message_dict["brain"] = m_content
        message_dict["brain_source"] = m_source
        message_dict["hub_pid"] = os.getpid()
        if "msg_id" not in message_dict:
            message_dict["msg_id"] = uuid.uuid4().hex[:12]

        msg_str = json.dumps(message_dict)

        # Non-blocking WebSocket fan-out
        for ws in list(self.connected_clients):
            try:
                if not ws.closed:
                    # Fire-and-forget the send_str to avoid blocking the main loop
                    asyncio.create_task(asyncio.wait_for(ws.send_str(msg_str), timeout=1.0))
                else:
                    self.connected_clients.remove(ws)
            except Exception:
                if ws in self.connected_clients:
                    self.connected_clients.remove(ws)

    async def waterfall_drainer(self):
        """[FEAT-233.2] Drains the internal token buffer and broadcasts to clients."""
        logger.info("Waterfall drainer active.")
        while True:
            try:
                data = await self.waterfall_queue.get()
                await self.broadcast(data)
                self.waterfall_queue.task_done()
            except Exception as e:
                logger.error(f"Waterfall drainer error: {e}")
                await asyncio.sleep(0.1)

    async def reflex_loop(self):
        """[FEAT-365] Characterful reflexes and persistence heartbeats."""
        tics = ["Narf!", "Poit!", "Zort!", "Checking circuits...", "Egad!", "Trotro!"]
        while True:
            # Persistent heartbeat to prevent browser timeouts
            if self.connected_clients:
                await self.broadcast({"type": "status", "state": "HEARTBEAT", "message": "Neural link stable.", "brain_source": "System"})
                
                # Random character tics
                if self.status.vocal and random.random() < 0.1:
                    await self.broadcast({"type": "crosstalk", "brain": random.choice(tics), "brain_source": "Pinky"})
            await asyncio.sleep(10)

    async def ear_poller_loop(self):
        """[FEAT-259.1] Global Sensory Sentinel."""
        while True:
            try:
                query = self.sensory.check_turn_end()
                if query:
                    asyncio.create_task(self.cognitive.process_query(f"[ME] {query}"))
            except Exception: pass
            await asyncio.sleep(0.1)

    async def scheduled_tasks_loop(self):
        """[FEAT-266] Periodic Maintenance (Nibbler)."""
        while True:
            # Periodic tasks...
            await asyncio.sleep(600)

    async def queue_drainer(self):
        """[Task 4.3] Neural Queue Drainer."""
        logger.info("Queue drainer active.")
        last_pos = 0
        if os.path.exists(QUEUE_FILE):
            last_pos = os.path.getsize(QUEUE_FILE)

        processed_ids = set()

        while True:
            try:
                if self.status.vocal:
                    # 1. Boot logical nodes if not ready
                    if not self.residents.booted:
                        logger.info("Lab is vocal. Booting logical nodes...")
                        await self.residents.boot_all()
                    
                    if os.path.exists(QUEUE_FILE):
                        size = os.path.getsize(QUEUE_FILE)
                        if size > last_pos:
                            with open(QUEUE_FILE, "r") as f:
                                f.seek(last_pos)
                                for line in f:
                                    if not line.strip(): continue
                                    try:
                                        event = IntentEvent.from_json(line)
                                        if event.status == "PENDING" and event.id not in processed_ids:
                                            logger.info(f"Draining Intent: {event.id} ({event.query[:20]}...)")
                                            processed_ids.add(event.id)
                                            
                                            # [FIX] Keep WebSocket alive during long node boot
                                            await self.broadcast({
                                                "type": "status", 
                                                "state": "SYNCING", 
                                                "message": "Physical silicon ready. Syncing logical nodes...", 
                                                "brain_source": "System"
                                            })
                                            
                                            asyncio.create_task(self.cognitive.process_query(event.query))
                                    except Exception as e:
                                        logger.error(f"Intent parse error: {e}")
                                last_pos = f.tell()
                
            except Exception as e:
                logger.error(f"Queue drainer failure: {e}")
            await asyncio.sleep(1)

    def run(self):
        web.run_app(self.app, port=PORT)

if __name__ == "__main__":
    router = FoyerRouter()
    router.run()
