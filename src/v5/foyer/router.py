import asyncio
import json
import logging
import os
import time
import uuid
import hashlib
import sys
import aiohttp
from aiohttp import web
import aiohttp_cors

# Add src to path
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if LAB_DIR not in sys.path:
    sys.path.append(LAB_DIR)

# [Task 4.2] V5 Foyer: The Logic Master
# Objective: Host the Cognitive Hub and manage logical node lifecycle.

from v5.common.types import IntentEvent, LabStatus  # noqa: E402
from v5.common.residents import ResidentManager  # noqa: E402
from logic.cognitive_hub import CognitiveHub  # noqa: E402
from equipment.sensory_manager import SensoryManager  # noqa: E402
from infra.montana import reclaim_logger  # noqa: E402

PORT = 8765
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")

# [BKM-016] Montana Protocol: Log Reclamation
reclaim_logger(role="SENSORY")
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
        with open(style_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    return "default_key"


class FoyerRouter:
    def __init__(self, trigger_task=None):
        # Rename process
        if setproctitle:
            setproctitle.setproctitle("acme_foyer_v5")

        self.connected_clients = set()
        self.session_token = uuid.uuid4().hex[:8]
        self.residents = ResidentManager(self.session_token)
        self.sensory = SensoryManager(self.broadcast)
        self.waterfall_queue = asyncio.Queue()
        self.trigger_task = trigger_task

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
            web.post('/trigger_task', self.handle_trigger_task),
            web.post('/release_nodes', self.handle_release_nodes),
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

    async def handle_release_nodes(self, request):
        """REST endpoint to gracefully shutdown logical nodes for hibernation."""
        try:
            logger.info("[FOYER] Releasing logical nodes for hibernation...")
            await self.residents.shutdown()
            return web.json_response({"status": "RELEASED"})
        except Exception as e:
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

    async def handle_trigger_task(self, request):
        """REST endpoint to trigger one-off background tasks."""
        try:
            data = await request.json()
            task = data.get("task")
            logger.info(f"[TRIGGER] Requesting task: {task}")
            if task == "recruiter":
                from recruiter import run_recruiter_task
                asyncio.create_task(run_recruiter_task(
                    self.residents.residents.get("archive"),
                    self.residents.residents.get("brain"),
                    self.residents.residents.get("browser")
                ))
            elif task == "lab":
                lab_node = self.residents.residents.get("lab")
                if lab_node:
                    asyncio.create_task(lab_node.call_tool("build_semantic_map"))
            elif task == "forge":
                # [FEAT-217] Sequenced Batch Forge
                archive_node = self.residents.residents.get("archive")
                if archive_node:
                    for target in ["cli_voice_v1", "shadow_brain_v2", "lab_history_v1"]:
                        asyncio.create_task(archive_node.call_tool("lab_train_adapter", {"adapter_name": target, "steps": 60}))

            return web.json_response({"status": "TRIGGERED", "task": task})
        except Exception as e:
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

    async def handle_status_update(self, request):
        """REST endpoint for the Ignition Manager to push state changes."""
        try:
            data = await request.json()
            # Update local status object
            self.status.state = data.get("state", self.status.state)
            self.status.vocal = data.get("vocal", self.status.vocal)
            self.status.engine_up = data.get("engine_up", self.status.engine_up)

            # [FEAT-265.15] Unified Boot: Trigger Ear and logical nodes concurrently
            if self.status.vocal and not self.residents.booted:
                logger.info("[FOYER] Physical silicon vocal. Initiating logical boot...")
                asyncio.create_task(self.sensory.load())
                asyncio.create_task(self.residents.boot_all())

            return web.Response(status=200)
        except Exception as e:
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

    async def on_startup(self, app):
        """[FEAT-339] Clean task scheduling on event loop start."""
        logger.info("V5 Foyer Router starting background tasks...")

        # [Task 5.2] Execute one-off trigger task if requested
        trigger_task = getattr(self, "trigger_task", None)
        if trigger_task:
            logger.info(f"[BOOT] Executing deferred trigger: {trigger_task}")
            if trigger_task == "recruiter":
                from recruiter import run_recruiter_task
                asyncio.create_task(run_recruiter_task(
                    self.residents.residents.get("archive"),
                    self.residents.residents.get("brain"),
                    self.residents.residents.get("browser")
                ))
            elif trigger_task == "lab":
                lab_node = self.residents.residents.get("lab")
                if lab_node:
                    asyncio.create_task(lab_node.call_tool("build_semantic_map"))

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
            await self.enqueue_intent(query, source="REST")
            return web.json_response({"status": "QUEUED"})
        return web.json_response({"status": "ERROR", "message": "No query"}, status=400)

    async def handle_websocket(self, ws_request):
        ws = web.WebSocketResponse()
        await ws.prepare(ws_request)
        
        client_id = uuid.uuid4().hex[:8]
        self.connected_clients.add(ws)
        logger.info(f"Client connected: {client_id}")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    query = data.get("query")
                    if query:
                        await self.enqueue_intent(query, source=client_id)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    # Voice streaming
                    res = self.sensory.process_binary_chunk(msg.data)
                    if res:
                        await self.enqueue_intent(res, source=client_id)
        finally:
            self.connected_clients.remove(ws)
            logger.info(f"Client disconnected: {client_id}")
        return ws

    async def handle_stream_ingest(self, request):
        """[FEAT-233.2] Receives real-time tokens from residents."""
        try:
            data = await request.json()
            await self.waterfall_queue.put(data)
            return web.Response(status=200)
        except Exception:
            return web.Response(status=400)

    async def enqueue_intent(self, query, source):
        event = IntentEvent(query=query, source=source)
        with open(QUEUE_FILE, "a") as f:
            f.write(event.to_json() + "\n")
        
        # [FEAT-265.8] Trigger ignition if hibernating
        if self.status.state == "HIBERNATING":
            logger.info(f"[FOYER] Request {event.id} secured in queue. Igniting Brain...")
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post("http://localhost:9999/ignite", json={"reason": "INTENT"}, timeout=1.0)
            except Exception:
                pass
        return event

    async def broadcast(self, message_dict):
        """[FEAT-145] Send logical updates to all connected UIs."""
        m_type = message_dict.get("type", "chat")
        m_source = message_dict.get("brain_source", "System")
        m_content = message_dict.get("brain") or message_dict.get("message")
        
        if not m_content:
            if m_type == "status":
                pass
            else:
                return

        # [NEW] Check if we are being called from a synchronous context
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                # Should not happen in aiohttp
                return
        except Exception:
            return

        # Perform formatting and logging
        try:
            from v5.common.ledger import ForensicLedger
            ledger = ForensicLedger()
            if m_type in ["chat", "crosstalk"]:
                ledger.record_thought(m_source, m_content, role=m_type.upper())
        except Exception:
            pass

        message_dict["type"] = m_type
        message_dict["timestamp"] = time.time()
        
        payload = json.dumps(message_dict)
        for ws in list(self.connected_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                self.connected_clients.remove(ws)

    async def reflex_loop(self):
        """[FEAT-031] Autonomous Reflexes."""
        while True:
            # Placeholder for future fast-path reflexes
            await asyncio.sleep(60)

    async def ear_poller_loop(self):
        """Polls for ASR results if sensory model is active."""
        while True:
            await asyncio.sleep(1)

    async def scheduled_tasks_loop(self):
        """[FEAT-072] Nightly Induction & Archive Sync."""
        logger.info("Scheduled tasks loop active.")
        while True:
            # Polled via Ignition Manager in V5
            await asyncio.sleep(300)

    async def waterfall_drainer(self):
        """[FEAT-233.2] Ingests and broadcasts tokens from the internal buffer."""
        logger.info("Waterfall drainer active.")
        while True:
            item = await self.waterfall_queue.get()
            # Relay to all clients
            await self.broadcast({
                "type": "chat",
                "brain": item.get("text", ""),
                "brain_source": item.get("source", "Resident"),
                "final": item.get("final", False)
            })
            self.waterfall_queue.task_done()

    async def queue_drainer(self):
        """[Task 4.3] Neural Queue Drainer."""
        logger.info("Queue drainer active.")
        last_pos = 0
        if os.path.exists(QUEUE_FILE):
            last_pos = os.path.getsize(QUEUE_FILE)

        from collections import deque
        processed_ids = deque(maxlen=1000) # [Task 6.3] Hygiene: Prevent memory leaks

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
                                    if not line.strip():
                                        continue
                                    try:
                                        event = IntentEvent.from_json(line)
                                        if event.status == "PENDING" and event.id not in processed_ids:
                                            logger.info(f"Draining Intent: {event.id} ({event.query[:20]}...)")
                                            processed_ids.append(event.id)
                                            
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
