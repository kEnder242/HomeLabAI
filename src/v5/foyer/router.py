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
import subprocess

# Add src to path
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if LAB_DIR not in sys.path:
    sys.path.append(LAB_DIR)

from v5.common.types import IntentEvent, LabStatus
from v5.common.residents import ResidentManager
from logic.cognitive_hub import CognitiveHub
from equipment.sensory_manager import SensoryManager
from infra.pager_relay import trigger_pager

# [Task 4.2] V5 Foyer: The Logic Master
# Objective: Host the Cognitive Hub and manage logical node lifecycle.

PORT = 8765
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")

# Configure logging early
# [BKM-016] Montana Protocol: Log Reclamation
from infra.montana import reclaim_logger
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
        import hashlib
        with open(style_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    return "default_key"

class FoyerRouter:
    def __init__(self, trigger_task=None):
        # ... existing ...
        if setproctitle:
            setproctitle.setproctitle("acme_foyer_v5")
            
        self.connected_clients = set()
        self.session_token = uuid.uuid4().hex[:8]
        self.residents = ResidentManager(self.session_token)
        self.sensory = SensoryManager(self.broadcast)
        self.waterfall_queue = asyncio.Queue()
        self.broadcast_queue = asyncio.Queue()
        self.trigger_task = trigger_task
        
        # [Task 6.3] Hygiene: Global Process Tracking
        from collections import deque
        self.processed_ids = deque(maxlen=1000)
        
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
        self.app.on_cleanup.append(self.cleanup)
        self.setup_routes()

    async def broadcast(self, message_dict):
        """[FEAT-233.2] Thread-safe, serialized WebSocket broadcast."""
        await self.broadcast_queue.put(message_dict)

    async def broadcast_worker(self):
        """[FIX] Sequential WebSocket Dispatcher to prevent stuttering/interleaving."""
        logger.info("Foyer broadcast worker active.")
        while True:
            message_dict = await self.broadcast_queue.get()
            try:
                m_type = message_dict.get("type", "chat")
                m_content = message_dict.get("brain", message_dict.get("message", ""))
                m_source = message_dict.get("brain_source", "System")
                
                # ... Forensic Ledger ...
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

                # Serialized Fan-out
                clients = list(self.connected_clients)
                if not clients:
                    logger.debug(f"[BROADCAST] No clients connected for msg: {m_type}")
                
                for ws in clients:
                    if not ws.closed:
                        try:
                            await asyncio.wait_for(ws.send_str(msg_str), timeout=1.0)
                        except Exception as e:
                            logger.error(f"[BROADCAST] Failed to send to client: {e}")
                            if ws in self.connected_clients:
                                self.connected_clients.remove(ws)
                    else:
                        if ws in self.connected_clients:
                            self.connected_clients.remove(ws)
            except Exception as e:
                logger.error(f"Broadcast worker error: {e}")
            finally:
                self.broadcast_queue.task_done()

    def record_pager(self, message, severity="INFO", source="Foyer"):
        """[Task 9.9] Centralized Pager Logging."""
        trigger_pager(message, severity=severity, source=source)

    async def cleanup(self, app):
        """[FEAT-339] Clean task release for aiohttp."""
        logger.info("V5 Foyer Router shutting down...")
        try:
            # [FIX] Safeguard against anyio cancel scope drift
            await self.residents.shutdown()
        except Exception as e:
            logger.error(f"Error during logical node shutdown: {e}")
        
        # Cancel all background tasks
        for task in [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

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
            web.get('/status', self.handle_status),
            # [FEAT-143] Remote Control endpoints
            web.post('/wake', self.handle_remote_action),
            web.post('/sleep', self.handle_remote_action),
            web.post('/lock', self.handle_remote_action),
            web.post('/shutdown', self.handle_remote_action)
        ])
        
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*",
            )
        })
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def handle_remote_action(self, request):
        """REST endpoint for remote control UI."""
        action = request.path.lstrip('/')
        await self.enqueue_intent(f"[OPERATIONAL] {action.upper()}", source="REMOTE")
        return web.json_response({"status": "success", "message": f"{action.capitalize()} signal enqueued."})

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
            self.status.vram_used = data.get("vram_used", self.status.vram_used)
            self.status.vram_total = data.get("vram_total", self.status.vram_total)
            self.status.ram_pct = data.get("ram_pct", self.status.ram_pct)
            
            # [FEAT-265.15] Unified Boot: Trigger Ear and logical nodes concurrently
            if self.status.vocal:
                if not self.residents.booted and not self.residents.booting:
                    logger.info("[FOYER] Physical silicon vocal. Initiating logical boot...")
                    asyncio.create_task(self.residents.boot_all())
            else:
                # [NEW] Hibernate logical nodes when silicon goes silent
                if self.residents.booted:
                    logger.info("[FOYER] Physical silicon silent. Hibernating logical nodes...")
                    asyncio.create_task(self.residents.shutdown())
            
            return web.Response(status=200)
        except Exception as e:
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

    async def on_startup(self, app):
        """[FEAT-339] Clean task scheduling on event loop start."""
        logger.info(f"[FOYER_BOOT] V5 Foyer Router starting background tasks... (Token: {self.session_token})")
        self.record_pager("Foyer Logic Hub Started.", source="Foyer")
        
        # [FEAT-145] VRAM Fragmentation Optimization: Load EarNode FIRST
        # Load it preemptively on startup, exempting it from hibernation.
        # Ensure it gets contiguous memory before vLLM or residents spawn.
        logger.info("[BOOT] Pre-emptively loading Sensory EarNode...")
        asyncio.create_task(self.sensory.load())
        
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
        asyncio.create_task(self.broadcast_worker())

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
        self.record_pager(f"Client Connected: {socket_id}", source="Foyer")
        
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
                        req_id = data.get("request_id")
                        await self.enqueue_intent(query, source=f"WS_{socket_id}", request_id=req_id)
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
            # Relay to Cognitive Hub for waterfall overhearing and queueing
            await self.cognitive.handle_stream_token({
                "brain": data.get("text", ""),
                "brain_source": data.get("source", "Unknown"),
                "final": data.get("final", False),
                "request_id": data.get("request_id", "default")
            })
            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Stream ingest error: {e}")
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

    async def enqueue_intent(self, query, source, request_id=None):
        event = IntentEvent(query=query, source=source)
        if request_id:
            event.id = request_id
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

    async def waterfall_drainer(self):
        """[Task 12.3] Drains internal token buffer into final Pop messages for UI."""
        logger.info("Waterfall drainer active (Pop Mode).")
        from collections import defaultdict
        
        # [Task 14.2] Isolated buffers by (request_id, source)
        pending_chunks = defaultdict(str)

        while True:
            try:
                data = await self.waterfall_queue.get()

                source = str(data.get("brain_source", data.get("source", "Unknown")))
                token = data.get("brain", "")
                final = data.get("final", False)
                request_id = data.get("request_id", "default")
                
                buf_key = (request_id, source)

                if token:
                    pending_chunks[buf_key] += token
                
                if final:
                    # [Task 12.3] Flush entire accumulated string immediately
                    content = pending_chunks[buf_key]
                    if content:
                        # [Task 12.4] Insight Window Routing
                        channel = "chat"
                        s_lower = source.lower()
                        if "brain" in s_lower or "thought" in s_lower:
                            channel = "insight"
                            
                        await self.broadcast({
                            "type": "chat",
                            "brain": content,
                            "brain_source": source,
                            "final": True,
                            "channel": channel,
                            "request_id": request_id
                        })
                        del pending_chunks[buf_key]

                self.waterfall_queue.task_done()

            except Exception as e:
                logger.error(f"Waterfall drainer error: {e}")
                await asyncio.sleep(0.5)

    async def reflex_loop(self):
        """[FEAT-365] Characterful reflexes and persistence heartbeats."""
        tics = ["Narf!", "Poit!", "Zort!", "Checking circuits...", "Egad!", "Trotro!"]
        while True:
            # Persistent heartbeat to prevent browser timeouts
            if self.connected_clients:
                await self.broadcast({"type": "status", "state": "HEARTBEAT", "brain_source": "System", "version": "5.0.0-foyer"})
                
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
                    import uuid
                    request_id = f"EAR_{uuid.uuid4().hex[:4]}"
                    shutdown_ev = asyncio.Event()
                    asyncio.create_task(self.cognitive.process_query(f"[ME] {query}", shutdown_event=shutdown_ev, request_id=request_id))
            except Exception: pass
            await asyncio.sleep(0.5)

    async def scheduled_tasks_loop(self):
        """[FEAT-266] Periodic Maintenance (Nibbler)."""
        logger.info("Scheduled tasks loop active.")
        last_nibble_time = 0
        while True:
            try:
                # 1. Periodic Nibble (Artifact Scanning) - DISABLED for Gauntlet
                if False and time.time() - last_nibble_time > 600:
                    last_nibble_time = time.time()
                    nibbler = os.path.join(WORKSPACE_DIR, "field_notes/nibble_v2.py")
                    if os.path.exists(nibbler):
                        # Use system python to avoid venv dependency in the subprocess call if needed
                        # but standard is to use the active executable
                        logger.info("[ALARM] Triggering Nibbler...")
                        subprocess.Popen([sys.executable, nibbler, "--one-turn"])
            except Exception as e:
                logger.error(f"[ALARM] Scheduled tasks failure: {e}")
            
            await asyncio.sleep(60)

    async def queue_drainer(self):
        """[Task 4.3] Neural Queue Drainer."""
        logger.info(f"Queue drainer active (Token: {self.session_token}).")
        last_pos = 0
        if os.path.exists(QUEUE_FILE):
            last_pos = os.path.getsize(QUEUE_FILE)

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
                                        if event.status == "PENDING" and event.id not in self.processed_ids:
                                            # [FIX] Filter out operational signals from reasoning engine
                                            if event.query.startswith("[OPERATIONAL]"):
                                                self.processed_ids.append(event.id)
                                                continue

                                            logger.info(f"Draining Intent: {event.id} ({event.query[:20]}...)")
                                            self.processed_ids.append(event.id)
                                            
                                            # [FIX] Keep WebSocket alive during long node boot
                                            await self.broadcast({
                                                "type": "status",
                                                "state": "SYNCING",
                                                "message": "Physical silicon ready. Syncing logical nodes...",
                                                "brain_source": "System",
                                                "version": "5.0.0-foyer"
                                            })
                                            
                                            # [NEW] Shutdown tracking for this intent
                                            shutdown_ev = asyncio.Event()
                                            asyncio.create_task(self.cognitive.process_query(event.query, shutdown_event=shutdown_ev, request_id=event.id))
                                    except Exception as e:
                                        logger.error(f"Intent parse error: {e}")
                                last_pos = os.path.getsize(QUEUE_FILE) # [FIX] Accurate tailing
                
            except Exception as e:
                logger.error(f"Queue drainer failure: {e}")
            await asyncio.sleep(1)

    def run(self):
        web.run_app(self.app, port=PORT)

if __name__ == "__main__":
    router = FoyerRouter()
    router.run()
