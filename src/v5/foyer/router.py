import asyncio
import json
import logging
import os
import time
import uuid
import random
import aiohttp
from aiohttp import web
import sys
import subprocess

# Add src to path
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC_DIR = os.path.join(LAB_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from v5.common.types import IntentEvent, LabStatus, LAB_VERSION  # noqa: E402
from v5.common.residents import ResidentManager  # noqa: E402
from logic.cognitive_hub import CognitiveHub  # noqa: E402
from equipment.sensory_manager import SensoryManager  # noqa: E402
from infra.pager_relay import trigger_pager  # noqa: E402
from infra.atomic_io import atomic_write_json  # noqa: E402

# [Task 4.2] V5 Foyer: The Logic Master
# Objective: Host the Cognitive Hub and manage logical node lifecycle.

PORT = 8765
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")

# Configure logging early
# [BKM-016] Montana Protocol: Log Reclamation
from infra.montana import reclaim_logger  # noqa: E402
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
    def __init__(self, trigger_task=None, mode="SERVICE_UNATTENDED", afk_timeout=300, disable_ear=False):
        self.disable_ear = disable_ear
        # ... existing ...
        if setproctitle:
            setproctitle.setproctitle("acme_foyer_v5")
            
        self.connected_clients = set()
        self.mode = mode
        self.afk_timeout = afk_timeout
        self.disconnect_timer = None
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
            waterfall_queue=self.waterfall_queue,
            set_active_domain=self.update_active_domain
        )
        # [FIX] CORS must be registered at Application creation time in aiohttp.
        # Wildcard origin is incompatible with allow_credentials=True (browser spec).
        # This middleware echoes back the exact request origin if it is in the allowlist.
        _CORS_ORIGINS = {
            "https://notes.jason-lab.dev",
            "https://www.jason-lab.dev",
            "http://localhost",
            "http://localhost:9001",
            "http://127.0.0.1",
            "http://127.0.0.1:9001",
        }

        @web.middleware
        async def _cors_mw(request, handler):
            origin = request.headers.get("Origin", "")
            if request.method == "OPTIONS":
                resp = web.Response(status=204)
            else:
                try:
                    resp = await handler(request)
                except web.HTTPException as ex:
                    resp = ex
            if origin in _CORS_ORIGINS:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, CF-Authorization"
                resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                resp.headers["Access-Control-Expose-Headers"] = "*"
            return resp

        self.app = web.Application(middlewares=[_cors_mw])
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
                except Exception:
                    pass

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
        await self.cognitive.trigger_morning_briefing()

    def setup_routes(self):
        self.app.add_routes([
            web.get('/', self.handle_websocket),
            web.get('/hub', self.handle_websocket),
            web.post('/inject', self.handle_rest_inject),
            web.post('/stream_ingest', self.handle_stream_ingest),
            web.post('/telemetry_ingest', self.handle_telemetry_ingest),
            web.post('/status_update', self.handle_status_update),
            web.post('/trigger_task', self.handle_trigger_task),
            web.post('/release_nodes', self.handle_release_nodes),
            web.post('/train', self.handle_train_rest),
            web.get('/health', self.handle_health),
            web.get('/status', self.handle_status),
            web.get('/logs', self.handle_logs),
            web.get('/sys_metrics', self.handle_sys_metrics),    # [FEAT-T20.5] Live graph feed
            web.get('/telemetry_kpi', self.handle_telemetry_kpi),  # [FEAT-T20.3]
            web.get('/benchmarks_kpi', self.handle_benchmarks_kpi),  # [FEAT-T21.2]
            # [FEAT-143] Remote Control endpoints
            web.post('/wake', self.handle_remote_action),
            web.post('/sleep', self.handle_remote_action),
            web.post('/lock', self.handle_remote_action),
            web.post('/shutdown', self.handle_remote_action)
        ])
        
        # [FIX-CORS] Middleware handles CORS at app creation; no per-route setup needed.

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

    async def handle_train_rest(self, request):
        """REST endpoint to trigger adapter training."""
        try:
            data = await request.json()
            adapter_name = data.get("adapter")
            steps = data.get("steps", 60)
            
            if not adapter_name:
                return web.json_response({"status": "ERROR", "message": "Missing adapter name"}, status=400)
            
            adapters = [a.strip() for a in adapter_name.split(",")]
            logger.info(f"[FORGE] Initiating sequenced batch training for: {adapters} ({steps} steps each).")
            
            results = []
            for target in adapters:
                clean_target = target
                if clean_target.endswith("_v1") or clean_target.endswith("_v2"):
                    clean_target = clean_target.rsplit("_", 1)[0]
                
                dataset_map = {
                    "lab_history": os.path.join(SRC_DIR, "forge/expertise/lab_history_training.jsonl"),
                    "cli_voice": os.path.join(SRC_DIR, "forge/expertise/cli_voice_training.jsonl"),
                    "lab_sentinel": os.path.join(SRC_DIR, "forge/expertise/lab_sentinel_training.jsonl"),
                    "cli_voice_v1": os.path.join(SRC_DIR, "forge/expertise/cli_voice_training.jsonl"),
                    "shadow_brain_v2": os.path.join(SRC_DIR, "forge/expertise/lab_history_training.jsonl"),
                    "lab_history_v1": os.path.join(SRC_DIR, "forge/expertise/lab_history_training.jsonl"),
                }
                dataset = dataset_map.get(target) or dataset_map.get(clean_target)
                output_dir = f"/speedy/models/adapters/{target}"
                
                if not dataset or not os.path.exists(dataset):
                    logger.error(f"[FORGE] Dataset not found for {target} (searched: {dataset})")
                    results.append({"adapter": target, "status": "missing_dataset"})
                    continue
                
                logger.info(f"[FORGE] Training {target} using {dataset}...")
                
                cmd = [sys.executable, os.path.join(SRC_DIR, "forge/train_expert.py"), dataset, output_dir, str(steps)]
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd, 
                        stdout=asyncio.subprocess.PIPE, 
                        stderr=asyncio.subprocess.PIPE,
                        cwd=SRC_DIR
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        logger.info(f"[FORGE] {target} completed successfully.")
                        results.append({"adapter": target, "status": "complete"})
                    else:
                        logger.error(f"[FORGE] {target} failed: {stderr.decode()}")
                        results.append({"adapter": target, "status": "failed", "error": stderr.decode()})
                except Exception as ex:
                    logger.error(f"[FORGE] Subprocess error training {target}: {ex}")
                    results.append({"adapter": target, "status": "error", "message": str(ex)})
            
            return web.json_response({"status": "success", "results": results})
        except Exception as e:
            logger.error(f"Train handler error: {e}")
            return web.json_response({"status": "ERROR", "message": str(e)}, status=500)

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
                # [FEAT-217] Sequenced Batch Forge - bypass MCP catch-22
                async def _run_batch_forge():
                    try:
                        async with aiohttp.ClientSession() as session:
                            payload = {"adapter": "cli_voice_v1,shadow_brain_v2,lab_history_v1", "steps": 60}
                            url = f"http://127.0.0.1:{PORT}/train"
                            async with session.post(url, json=payload, timeout=3600) as r:
                                logger.info(f"[TRIGGER] Sequenced Batch Forge completed. Status: {r.status}")
                    except Exception as e:
                        logger.error(f"[TRIGGER] Sequenced Batch Forge failed: {e}")
                asyncio.create_task(_run_batch_forge())
            elif task == "eval":
                # [FEAT-T21.3] BKM-032: Background benchmark eval run
                tag = data.get("tag", "baseline")
                eval_script = os.path.join(LAB_DIR, "src", "run_evals.py")
                import subprocess
                import sys
                subprocess.Popen(
                    [sys.executable, eval_script, "--tag", tag, "--engine", "vllm"],
                    cwd=os.path.join(LAB_DIR, "src"),
                    env={**os.environ, "PYTHONPATH": os.path.join(LAB_DIR, "src")}
                )
                logger.info(f"[TRIGGER] Eval run dispatched for tag: {tag}")

            
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
            
            # [FEAT-265.15] Unified Boot: Trigger Ear and logical nodes concurrently based on state transitions
            if self.status.state in ["HIBERNATING", "OFFLINE"]:
                if self.residents.booted:
                    logger.info(f"[FOYER] Lab state is {self.status.state}. Hibernating logical nodes...")
                    asyncio.create_task(self.residents.shutdown())
            elif self.status.state in ["OPERATIONAL"]:
                if not self.residents.booted and not self.residents.booting:
                    logger.info("[FOYER] Lab is OPERATIONAL. Initiating logical boot...")
                    asyncio.create_task(self.residents.boot_all())
            
            return web.Response(status=200)
        except Exception as e:
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

    async def on_startup(self, app):
        """[FEAT-339] Clean task scheduling on event loop start."""
        logger.info(f"[FOYER_BOOT] V5 Foyer Router starting background tasks... (Token: {self.session_token})")
        self.record_pager("Foyer Logic Hub Started.", source="Foyer")
        
        # [FEAT-145] VRAM Fragmentation Optimization: Load EarNode FIRST (if enabled)
        if not self.disable_ear:
            logger.info("[BOOT] Pre-emptively loading Sensory EarNode...")
            asyncio.create_task(self.sensory.load())
        else:
            logger.info("[BOOT] Sensory EarNode disabled by configuration.")
        
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
        return web.json_response({"status": "ONLINE", "version": LAB_VERSION})

    async def handle_status(self, request):
        status_dict = self.status.to_dict()
        status_dict["connected_clients"] = len(self.connected_clients)
        return web.json_response(status_dict)

    async def handle_logs(self, request):
        """
        [FEAT-309.3] Serve specific log trace files or the main log.
        """
        try:
            target_file = request.rel_url.query.get('file')
            if target_file:
                # Sanitize: No path traversal
                safe_name = os.path.basename(target_file)
                log_path = os.path.join(LAB_DIR, 'logs', safe_name)
                if os.path.exists(log_path):
                    with open(log_path, 'r') as f:
                        return web.Response(text=f.read())
                return web.Response(status=404, text=f'Log {safe_name} not found.')
                
            # If no file requested, serve last 5000 chars of attendant.log or similar
            attendant_log = os.path.join(LAB_DIR, 'logs', 'attendant.log')
            if not os.path.exists(attendant_log):
                # Check workspace parent folder
                attendant_log = os.path.expanduser('~/Dev_Lab/attendant.log')
            if os.path.exists(attendant_log):
                with open(attendant_log, 'r') as f:
                    return web.Response(text=f.read()[-5000:])
            return web.Response(status=404, text='No log file found.')
        except Exception as e:
            return web.Response(status=500, text=str(e))

    async def handle_sys_metrics(self, request):
        """
        [FEAT-T20.5] Live system metrics endpoint for the SYSTEM graph tab.
        Returns a single-point snapshot: CPU %, RAM %, VRAM %, GPU temp, GPU power.
        Polled every 5s by the frontend to build a rolling 60-point canvas graph.
        """
        try:
            import psutil
            cpu_pct = psutil.cpu_percent(interval=None)   # non-blocking
            ram = psutil.virtual_memory()
            ram_pct = ram.percent

            # DCGM snapshot (reuse TelemetryCollector singleton)
            gpu_temp = 0.0
            gpu_power = 0.0
            vram_pct = 0.0
            try:
                from infra.telemetry_collector import get_collector
                col = get_collector()
                snap = col.snapshot()
                gpu_temp = snap.gpu_temp_c
                gpu_power = snap.gpu_power_w
                if snap.vram_total_mb > 0:
                    vram_pct = round(snap.vram_used_mb / snap.vram_total_mb * 100, 1)
            except Exception:
                # Fallback to LabStatus VRAM if collector unavailable
                if self.status.vram_total > 0:
                    vram_pct = round(self.status.vram_used / self.status.vram_total * 100, 1)

            return web.json_response({
                "ts": time.time(),
                "cpu_pct": round(cpu_pct, 1),
                "ram_pct": round(ram_pct, 1),
                "vram_pct": vram_pct,
                "gpu_temp_c": round(gpu_temp, 1),
                "gpu_power_w": round(gpu_power, 1),
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_telemetry_kpi(self, request):
        """
        [FEAT-T20.3] KPI endpoint: serves last N telemetry samples from ledger.
        Query param: ?n=50 (default 50, max 200)
        """
        try:
            n = min(int(request.rel_url.query.get("n", 50)), 200)
            ledger_path = os.path.join(LAB_DIR, "logs", "telemetry_ledger.jsonl")
            samples = []
            if os.path.exists(ledger_path):
                with open(ledger_path, "r") as f:
                    lines = f.readlines()
                for line in lines[-n:]:
                    line = line.strip()
                    if line:
                        try:
                            samples.append(json.loads(line))
                        except Exception:
                            pass
            return web.json_response({"samples": samples, "count": len(samples)})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_benchmarks_kpi(self, request):
        """
        [FEAT-T21.2] Benchmarks endpoint: serves benchmark runs with per-model aggregates.
        Query params: ?n=100 (last N runs), ?tag=telemetry (filter by tag)
        """
        try:
            n = min(int(request.rel_url.query.get("n", 100)), 500)
            tag_filter = request.rel_url.query.get("tag", None)
            ledger_path = os.path.join(LAB_DIR, "logs", "benchmarks.jsonl")
            runs = []
            if os.path.exists(ledger_path):
                with open(ledger_path, "r") as f:
                    lines = f.readlines()
                for line in lines[-n:]:
                    line = line.strip()
                    if line:
                        try:
                            r = json.loads(line)
                            if tag_filter and tag_filter not in r.get("tags", []):
                                continue
                            runs.append(r)
                        except Exception:
                            pass

            # Per-model aggregates
            from collections import defaultdict
            model_stats = defaultdict(lambda: {"runs": 0, "total_score": 0, "total_tps": 0,
                                                "total_power": 0, "total_j_tok": 0, "tags": set()})
            for r in runs:
                m = r.get("model", "unknown")
                model_stats[m]["runs"] += 1
                model_stats[m]["total_score"] += r.get("judge_score", 0)
                model_stats[m]["total_tps"] += r.get("tokens_per_sec", 0)
                model_stats[m]["total_power"] += r.get("gpu_power_w", 0)
                model_stats[m]["total_j_tok"] += r.get("joules_per_token", 0)
                model_stats[m]["tags"].update(r.get("tags", []))

            aggregates = {}
            for model, s in model_stats.items():
                n_runs = s["runs"] or 1
                aggregates[model] = {
                    "runs": s["runs"],
                    "avg_score": round(s["total_score"] / n_runs, 2),
                    "avg_tps": round(s["total_tps"] / n_runs, 2),
                    "avg_power_w": round(s["total_power"] / n_runs, 2),
                    "avg_j_tok": round(s["total_j_tok"] / n_runs, 6),
                    "tags": list(s["tags"]),
                }

            all_tags = sorted({t for r in runs for t in r.get("tags", [])})
            return web.json_response({
                "runs": list(reversed(runs)),  # newest first
                "aggregates": aggregates,
                "total": len(runs),
                "tags": all_tags,
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

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
        
        # Cancel disconnect timer if it is running
        if self.disconnect_timer is not None:
            logger.info("[FOYER] Client reconnected. Cancelling idle shutdown timer.")
            self.disconnect_timer.cancel()
            self.disconnect_timer = None
            
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
                            "version": LAB_VERSION
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
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    text = self.sensory.process_binary_chunk(msg.data)
                    if text:
                        await self.broadcast({
                            "type": "hearing",
                            "text": text,
                            "socket_id": socket_id
                        })
                        
        finally:
            if ws in self.connected_clients:
                self.connected_clients.remove(ws)
            logger.info(f"Client disconnected: {socket_id}")
            
            # Start disconnect timer if no clients connected and mode is DEBUG_BRAIN
            if not self.connected_clients and self.mode == "DEBUG_BRAIN":
                logger.info(f"[FOYER] No clients connected. Starting {self.afk_timeout}s idle shutdown timer.")
                self.disconnect_timer = asyncio.create_task(self.delayed_shutdown(self.afk_timeout))
            
        return ws

    async def delayed_shutdown(self, delay):
        try:
            await asyncio.sleep(delay)
            logger.warning(f"[FOYER] {delay}s client disconnect timeout reached in {self.mode} mode. Initiating shutdown...")
            self.record_pager("Client disconnect timeout reached. Shutting down Foyer.", severity="WARNING", source="Foyer")
            await self.enqueue_intent("[OPERATIONAL] SHUTDOWN", source="TIMEOUT")
            await asyncio.sleep(5.0)
            logger.info("[FOYER] Exiting Foyer process.")
            sys.exit(0)
        except asyncio.CancelledError:
            logger.info("[FOYER] Delayed shutdown timer cancelled.")

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

    async def handle_telemetry_ingest(self, request):
        """[FEAT-T20.3] Ingests metrics from decoupled resident nodes and appends to ledger."""
        try:
            data = await request.json()
            if self.cognitive and self.cognitive._tel_collector:
                # Scrape raw GPU info from DCGM first to enrich
                sample = self.cognitive._tel_collector.snapshot(
                    node=data.get("node", ""),
                    request_id=data.get("request_id", "default")
                )
                sample.ttft_ms = data.get("ttft_ms", 0.0)
                sample.total_tokens = data.get("total_tokens", 0)
                sample.duration_s = data.get("duration_s", 0.0)
                sample.engine_type = data.get("engine_type", "")
                sample.model = data.get("model", "")
                sample.enrich_economics()
                self.cognitive._tel_collector.write_ledger(sample)
                logger.info(f"[TEL INGEST] Logged telemetry for {sample.node} | TTFT={sample.ttft_ms}ms")
            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Telemetry ingest error: {e}")
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
                await self.broadcast({"type": "status", "state": "HEARTBEAT", "brain_source": "System", "version": LAB_VERSION})
                
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
                    # Broadcast the final transcription event to the UI
                    await self.broadcast({
                        "type": "final",
                        "text": f"[ME] {query}"
                    })
                    shutdown_ev = asyncio.Event()
                    asyncio.create_task(self.cognitive.process_query(f"[ME] {query}", shutdown_event=shutdown_ev, request_id=request_id))
            except Exception:
                pass
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
                # [FEAT-DECOUPLED] Check for queue changes immediately even if not vocal
                if os.path.exists(QUEUE_FILE):
                    size = os.path.getsize(QUEUE_FILE)
                    if size > last_pos:
                        # Boot logical nodes on intent if not ready
                        if not self.residents.booted:
                            logger.info("New intent detected. Booting logical nodes...")
                            await self.residents.boot_all()
                        
                        with open(QUEUE_FILE, "r") as f:
                            f.seek(last_pos)
                            for line in f:
                                if not line.strip():
                                    continue
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
                                            "version": LAB_VERSION
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

    def update_active_domain(self, domain):
        """[Task 19.2] Propagate active triage domain to state and status center."""
        self.status.active_domain = domain
        try:
            atomic_write_json(STATUS_JSON, self.status.to_dict())
            logger.info(f"[FOYER] Active domain updated to {domain} and written to status.json.")
        except Exception as e:
            logger.error(f"[FOYER] Failed to write status.json with active domain {domain}: {e}")

    def run(self):
        web.run_app(self.app, port=PORT)

if __name__ == "__main__":
    router = FoyerRouter()
    router.run()
