import asyncio
import gc
import json
import logging
import os
import re
import time
import uuid
# [STORY-5] Cold-start wake thread caps: bound BLAS/ML worker threads to 2
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["TORCH_NUM_THREADS"] = "2"
import random
import aiohttp
from aiohttp import web
import numpy as np
import sys
import subprocess
import socket

# Add src to path
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC_DIR = os.path.join(LAB_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from v5.common.types import IntentEvent, LabStatus, LAB_VERSION, SensoryMode  # noqa: E402
from v5.common.residents import ResidentManager  # noqa: E402
from logic.cognitive_hub import CognitiveHub  # noqa: E402
from equipment.sensory_manager import SensoryManager  # noqa: E402
from infra.pager_relay import trigger_pager  # noqa: E402
from infra.atomic_io import atomic_write_json  # noqa: E402
from v5.foyer.maintenance_sweeper import MaintenanceSweeper  # noqa: E402

# [LAB-010] Lazy import — M5 Air may not be available at startup.
try:
    from nodes.mlx_judge_node import MLXAsyncJudge as _MLXAsyncJudge
    _mlx_judge = _MLXAsyncJudge()
except Exception:
    _mlx_judge = None

# [Task 4.2] V5 Foyer: The Logic Master
# Objective: Host the Cognitive Hub and manage logical node lifecycle.

PORT = 8765
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")
JUDGE_BACKPRESSURE_PATH = os.path.join(DATA_DIR, "judge_backpressure.jsonl")  # [FEAT-444]
INFRA_CONFIG = os.path.join(LAB_DIR, "config", "infrastructure.json")  # [FEAT-028] Deep Thought topology

# [SPR-52.0 / Task 52.3] 5-Stage Division of Labor Orchestration
DIVISION_OF_LABOR_STAGES = (
    ("stage1_kender_triage",  "Deep Thought / Lab Node (Kender · t=0)", "Preamble & Triage"),
    ("stage2_pinky_hyde",     "Pinky (vLLM + LoRA)",                    "HyDE & Persona Alignment"),
    ("stage3_brain_query",    "Brain (Right Hemisphere)",               "Short Technical Answer / ChromaDB"),
    ("stage4_dt_synthesis",   "Deep Thought (Kender)",                  "Strategic Synthesis (importance >= 0.7)"),
    ("stage5_pinky_review",   "Pinky (Sanity / Vibe Check)",            "Out-Loud Delivery -> Waterfall Drainer"),
)
STAGE_SOURCE_MAP = {
    "Deep Thought": "stage1_kender_triage",
    "Lab (Triage)": "stage1_kender_triage",
    "Pinky":        "stage2_pinky_hyde",
    "Brain":        "stage3_brain_query",
}
STAGE_TIMEOUTS = {
    "stage1_kender_triage": 45,
    "stage2_pinky_hyde":    30,
    "stage3_brain_query":   30,
    "stage4_dt_synthesis":  60,
    "stage5_pinky_review":  20,
}
STAGE_LEDGER_PATH = os.path.join(DATA_DIR, "foyer_stage_ledger.jsonl")

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

def resolve_thought_url():
    """[FEAT-028] Resolves Deep Thought heartbeat URL from infrastructure config."""
    try:
        if os.path.exists(INFRA_CONFIG):
            with open(INFRA_CONFIG, "r") as f:
                infra = json.load(f)
            primary = (
                infra.get("nodes", {}).get("thought", {}).get("primary", "localhost")
            )
            host_cfg = infra.get("hosts", {}).get(primary, {})
            ip_hint = host_cfg.get("ip_hint", "127.0.0.1")
            port = host_cfg.get("ollama_port", 11434)

            # Dynamic resolution: DNS first, fall back to config hint
            try:
                ip = socket.gethostbyname(primary)
                logging.debug(f"[RESOLVE] Brain host '{primary}' -> {ip}")
            except Exception:
                ip = ip_hint
                logging.debug(f"[RESOLVE] DNS failed for '{primary}'. Using hint: {ip}")

            return f"http://{ip}:{port}/api/tags"
    except Exception as e:
        logging.error(f"[RESOLVE] Failed to resolve Brain URL: {e}")
        return ""
    return "http://localhost:11434/api/tags"

class FoyerRouter:
    def __init__(self, trigger_task=None, mode="SERVICE_UNATTENDED", afk_timeout=300, disable_ear=False):
        try:
            _hr = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"],
                                 capture_output=True, text=True, cwd="/home/jallred/Dev_Lab/HomeLabAI", timeout=5)
            self.boot_commit = _hr.stdout.strip() if _hr.returncode == 0 and _hr.stdout.strip() else "unknown"
        except Exception:
            self.boot_commit = "unknown"
        self.boot_timestamp = int(time.time())
        self.disable_ear = disable_ear
        # ... existing ...
        if setproctitle:
            setproctitle.setproctitle("acme_foyer_v5")
            
        self.connected_clients = set()
        self.mode = mode
        self.afk_timeout = afk_timeout
        self.disconnect_timer = None
        self.session_token = uuid.uuid4().hex[:8]
        self.session_horizon_ts = self.boot_timestamp
        self.residents = ResidentManager(self.session_token)
        self.sensory = SensoryManager(self.broadcast)
        self.waterfall_queue = asyncio.Queue()
        self.broadcast_queue = asyncio.Queue()
        self.trigger_task = trigger_task
        
        # [Task 6.3] Hygiene: Global Process Tracking
        from collections import deque
        self.processed_ids = deque(maxlen=1000)
        # [SPR-52.0 / Task 52.3] Stage-hook registry for the 5-Stage Division of Labor
        self.stage_hooks = {sid: [] for sid, _, _ in DIVISION_OF_LABOR_STAGES}
        self.stage_memory = {}  # request_id -> {stage_id: status}
        
        self.status = LabStatus()
        # [FEAT-028] Deep Thought health-tracking state (restored from V4 acme_lab.py)
        self.thought_online = False
        self._last_brain_fail = 0
        self._last_brain_ping = 0
        self._last_brain_prime = 0
        self._priming_in_progress = False
        self._last_thought_fail = 0
        self.cognitive = CognitiveHub(
            self.residents.residents, 
            self.broadcast, 
            self.sensory, 
            get_vram_status=self.get_vram_status,
            get_lab_state=self.get_lab_state,
            is_deep_thought_reachable=self.is_deep_thought_reachable,
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
                except (ImportError, FileNotFoundError):
                    logger.warning("[FOYER] forensic ledger unavailable", exc_info=True)
                except Exception:
                    logger.warning("[FOYER] forensic ledger record failed", exc_info=True)

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

    def register_stage_hook(self, stage_id, hook):
        """[SPR-52.0 / Task 52.3] Register a callable fired on stage transitions."""
        if stage_id not in self.stage_hooks:
            raise KeyError(f"Unknown stage: {stage_id}")
        self.stage_hooks[stage_id].append(hook)

    async def _emit_stage_progress(self, stage_id, request_id, status, detail=""):
        """[SPR-52.0 / Task 52.3] Non-fatal stage transition: broadcast + ledger + hooks.

        NEVER raises into the caller. Stage hooks are observer callbacks
        (fire-and-forget); a bad hook only logs a warning.
        """
        try:
            stage_node, stage_purpose = next(
                ((s[1], s[2]) for s in DIVISION_OF_LABOR_STAGES if s[0] == stage_id),
                (stage_id, ""),
            )
            self.stage_memory.setdefault(request_id, {})[stage_id] = status
            try:
                os.makedirs(os.path.dirname(STAGE_LEDGER_PATH), exist_ok=True)
                with open(STAGE_LEDGER_PATH, "a") as f:
                    f.write(json.dumps({
                        "ts": time.time(),
                        "request_id": request_id,
                        "stage": stage_id,
                        "node": stage_node,
                        "purpose": stage_purpose,
                        "status": status,
                        "detail": detail,
                    }, default=str) + "\n")
            except Exception as e:
                logger.warning(f"[SPR-52.0] Stage ledger append failed: {e}")
            stage_index = next((i for i, s in enumerate(DIVISION_OF_LABOR_STAGES) if s[0] == stage_id), 0) + 1
            await self.broadcast({
                "type": "crosstalk",
                "channel": "stage",
                "stage": stage_id,
                "stage_index": stage_index,
                "stage_total": len(DIVISION_OF_LABOR_STAGES),
                "node": stage_node,
                "purpose": stage_purpose,
                "stage_status": status,
                "detail": detail,
                "brain": f"[STAGE {stage_index}/5] {stage_purpose} — {status}",
                "brain_source": "Foyer",
                "request_id": request_id,
                "version": LAB_VERSION,
            })
            for hook in self.stage_hooks.get(stage_id, []):
                try:
                    hook(request_id, status, detail)
                except Exception as e:
                    logger.warning(f"[SPR-52.0] Stage hook error ({stage_id}): {e}")
        except Exception as e:
            logger.warning(f"[SPR-52.0] Stage progress emission failed (non-fatal): {e}")

    async def _stream_pinky_fallback(self, request_id):
        """[SPR-52.0 / Task 52.3] Graceful degradation: guarantee UI delivery on failure."""
        try:
            await self.broadcast({
                "type": "chat",
                "brain": "The pipeline hit a snag mid-synthesis. Retrying via Pinky's direct line...",
                "brain_source": "Pinky",
                "final": True,
                "channel": "chat",
                "request_id": request_id,
            })
        except Exception as e:
            logger.warning(f"[SPR-52.0] Pinky fallback emit failed: {e}")

    async def run_division_of_labor(self, query, source="REST", request_id=None):
        """[SPR-52.0 / Task 52.3] 5-Stage Division of Labor orchestrator.

        Wraps the Cognitive Hub waterfall with per-stage hooks and graceful
        error containment. Stage 1 (Kender triage) is idempotent: the WS path
        emits STARTED at t=0 via _spawn_deep_thought_preamble; REST paths emit
        it here. Stages 2-4 progress is deduced from incoming node streams via
        STAGE_SOURCE_MAP in handle_stream_ingest. Stage 5 completes when the
        waterfall drainer flushes the final Pop for this request_id.
        """
        if request_id is None:
            import uuid
            request_id = uuid.uuid4().hex[:8]

        # Stage 1: Preamble & Triage (Kender · t=0, local fallback)
        if self.stage_memory.get(request_id, {}).get("stage1_kender_triage") is None:
            await self._emit_stage_progress("stage1_kender_triage", request_id, "STARTED")

        kender_online = False
        try:
            thought = self.residents.get_node("thought")
            if thought is not None:
                res = await asyncio.wait_for(thought.call_tool("ping_engine", {"force": False}), timeout=5.0)
                if getattr(res, "content", None):
                    kender_online = '"success": true' in res.content[0].text
        except Exception as e:
            logger.warning(f"[SPR-52.0][STAGE1] Kender ping failed — local fallback engaged: {e}")
        await self._emit_stage_progress(
            "stage1_kender_triage", request_id, "COMPLETED",
            detail="kender_online" if kender_online else "local_fallback",
        )

        # Stages 2-4 run inside the hub; guarded by a total-budget timeout.
        shutdown_ev = asyncio.Event()
        try:
            await asyncio.wait_for(
                self.cognitive.process_query(query, shutdown_event=shutdown_ev, request_id=request_id),
                timeout=STAGE_TIMEOUTS["stage4_dt_synthesis"] * 4,
            )
        except asyncio.TimeoutError:
            logger.error(f"[SPR-52.0] Division of Labor exceeded total budget for {request_id}")
            await self._emit_stage_progress("stage4_dt_synthesis", request_id, "FAILED", detail="total_timeout")
            await self._stream_pinky_fallback(request_id)
        except Exception as e:
            logger.error(f"[SPR-52.0] Division of Labor failed for {request_id}: {e}")
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"[PIPELINE ERROR] Division of Labor failed ({request_id}): {e}",
                "brain_source": "System"
            })
            await self._emit_stage_progress("stage5_pinky_review", request_id, "FAILED", detail=str(e)[:200])
            await self._stream_pinky_fallback(request_id)

    async def cleanup(self, app):
        """[FEAT-339/FEAT-430] Clean task release for aiohttp with C-Arena Heap Trimming."""
        logger.info("V5 Foyer Router shutting down...")
        try:
            import ctypes
            ctypes.CDLL('libc.so.6').malloc_trim(0)
            logger.info("[FEAT-430] Executed malloc_trim(0) heap flush.")
        except Exception as trim_ex:
            logger.warning(f"[FEAT-430] malloc_trim failed: {trim_ex}")
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
                logger.warning("[FOYER] task cancellation error", exc_info=True)

    def get_vram_status(self, force=False):
        """[BKM-039] Local engine vocal status (vLLM speaking/outputting).

        NOTE: This is a LOCAL node check. It is NOT a remote reachability probe.
        Use `is_deep_thought_reachable()` for remote Deep Thought availability.
        """
        return self.status.vocal

    def get_lab_state(self):
        """[FEAT-028] Returns the current lab state string (OPERATIONAL/WAKING/HIBERNATING/...)."""
        return getattr(self.status, "state", "UNKNOWN")

    async def is_deep_thought_reachable(self, force=False):
        """[FEAT-028] Tier 1: Ping->API reachability probe for Deep Thought (remote primary).

        Order: TCP socket ping first (fails fast), THEN /api/tags API check.
        Reachable == socket connects AND API returns 200 with a non-empty model list.
        [BKM-026] 60s failure penalty box: after a failure, suppress probes for 60s.
        """
        now = time.time()
        if not hasattr(self, "_last_thought_fail"):
            self._last_thought_fail = 0
        if not force and (now - self._last_thought_fail < 60):
            return False

        target_url = resolve_thought_url()
        if not target_url:
            return False

        # --- Step 1: TCP socket ping (fails fast) ---
        try:
            from urllib.parse import urlparse
            _u = urlparse(target_url)
            host, port = _u.hostname, _u.port or 11434
            _reader, _writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            _writer.close()
            try:
                await _writer.wait_closed()
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"[HEALTH] Deep Thought socket ping failed: {e}")
            self._last_thought_fail = now
            return False

        # --- Step 2: Light API Check ---
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(target_url, timeout=aiohttp.ClientTimeout(total=2.0)) as r:
                    if r.status != 200:
                        self._last_thought_fail = now
                        return False
                    data = await r.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    if not models:
                        self._last_thought_fail = now
                        return False
            return True
        except Exception as e:
            logger.debug(f"[HEALTH] Deep Thought API check failed: {e}")
            self._last_thought_fail = now
            return False

    async def check_thought_health(self, force=False):
        """[FEAT-265.31/FEAT-028] State-Aware Deep Thought probe: ping->API + Heavy Prime (GPU Wake)."""
        # [FEAT-344] Sovereignty Gate: Suppress probes during raw silicon boot / hibernation.
        state = getattr(self.status, "state", "UNKNOWN")
        if state in ["BOOTING", "INIT", "HIBERNATING"]:
            logger.debug(f"[HEALTH] Sovereignty Gate: Aborting probe during {state}.")
            return

        now = time.time()
        if not hasattr(self, "_last_brain_fail"):
            self._last_brain_fail = 0
        if not hasattr(self, "_last_brain_ping"):
            self._last_brain_ping = 0

        # [BKM-026] 60s Failure Penalty Box
        if not force and not self.thought_online and (now - self._last_brain_fail < 60):
            return

        try:
            target_url = resolve_thought_url()
            async with aiohttp.ClientSession() as session:
                # Tier 1: Light API Check (Status only)
                try:
                    async with session.get(target_url, timeout=2.0) as r:
                        is_reachable = r.status == 200
                        if not is_reachable:
                            if self.thought_online:
                                logger.info("[HEALTH] Deep Thought Offline. Entering 60s penalty box.")
                                await self.broadcast({
                                    "type": "crosstalk",
                                    "brain": "Strategic Sovereignty: DEEP THOUGHT (Primary Offline)",
                                    "brain_source": "System",
                                    "version": LAB_VERSION
                                })
                            self.thought_online = False
                            self._last_brain_fail = now
                            return

                        data = await r.json()
                        models = [m.get("name") for m in data.get("models", [])]
                        if not models:
                            self.thought_online = False
                            return

                        # [FIX] Distinguish transition vs stable state
                        if not self.thought_online:
                            logger.info("[BRAIN] Strategic Sovereignty: PRIMARY (Online)")
                            await self.broadcast({
                                "type": "crosstalk",
                                "brain": "Strategic Sovereignty: PRIMARY",
                                "brain_source": "System",
                                "version": LAB_VERSION
                            })
                        self.thought_online = True  # API is at least talking
                except Exception as e:
                    if self.thought_online:
                        logger.info(f"[HEALTH] Deep Thought Offline. Entering 60s penalty box. (Error: {e})")
                        await self.broadcast({
                            "type": "crosstalk",
                            "brain": "Strategic Sovereignty: SHADOW (Primary Offline)",
                            "brain_source": "System",
                            "version": LAB_VERSION
                        })
                    self.thought_online = False
                    self._last_brain_fail = now
                    return

                # --- Tier 2: Heavy Prime (GPU Wake) ---
                # [FEAT-134] AFK Presence Gate: Never wake GPU if room is empty
                is_restoring = state in ["WAKING", "BOOTING"]
                if len(self.connected_clients) == 0 and not force:
                    logger.debug("[HEALTH] Heavy Prime Bypassed: No clients connected to foyer.")
                    return

                # [FEAT-285] Cooldown Management
                last_prime_delta = now - getattr(self, "_last_brain_prime", 0)
                should_prime = force or is_restoring or (last_prime_delta > 120)
                if not should_prime:
                    logger.debug(f"[HEALTH] Heavy Prime Bypassed: Cooldown active ({int(last_prime_delta)}s < 120s).")
                    return

                # [FEAT-286.2] Strict Latching: Only one active background prime
                if getattr(self, "_priming_in_progress", False):
                    logger.debug("[HEALTH] Heavy Prime Bypassed: Task already in progress.")
                    return

                # [FEAT-155] Speed over Scale: Prioritize 8B models for <10s load times
                probe_model = models[0] if models else "llama3.1:8b"  # Fallback to 8B standard
                preferred = ["llama3.1:8b", "mixtral:8x7b", "gemma2:2b"]
                for p in preferred:
                    if p in models:
                        probe_model = p
                        break

                logger.info(f"[HEALTH] Initiating Heavy Prime on Deep Thought: {probe_model} (Force={force}, Restoring={is_restoring})")

                p_url = target_url.replace("/api/tags", "/api/generate")
                payload = {"model": probe_model, "prompt": "ping", "stream": False, "options": {"num_predict": 1}}

                # [BKM] Parallel Execution: Generation probe runs in background to prevent Hub hangs
                self._priming_in_progress = True

                async def _bg_prime():
                    try:
                        async with aiohttp.ClientSession() as p_session:
                            async with p_session.post(p_url, json=payload, timeout=30) as pr:
                                if pr.status == 200:
                                    logger.info(f"[HEALTH] Strategic Sovereign SUCCESS: {probe_model} is resident in VRAM.")
                                    self._last_brain_prime = time.time()
                                else:
                                    logger.error(f"[HEALTH] Heavy Prime Failed on Deep Thought ({pr.status})")
                    except Exception as pe:
                        logger.error(f"[HEALTH] Heavy Prime Exception (Deep Thought): {pe}")
                    finally:
                        self._priming_in_progress = False

                asyncio.create_task(_bg_prime())

        except Exception as e:
            logger.debug(f"[HEALTH] Overall brain probe failed: {e}")

    async def thought_health_loop(self):
        """[FEAT-028] Periodic Deep Thought health probe: ping->API every 20s, Heavy Prime per FEAT-285."""
        logger.info("[HEALTH] Deep Thought health loop active.")
        while True:
            try:
                await self.check_thought_health()
            except Exception as e:
                logger.warning(f"[HEALTH] thought_health_loop iteration failed: {e}")
            await asyncio.sleep(20)

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
            web.get('/version', self.handle_version),
            web.get('/logs', self.handle_logs),
            web.get('/sys_metrics', self.handle_sys_metrics),    # [FEAT-T20.5] Live graph feed
            web.get('/telemetry_kpi', self.handle_telemetry_kpi),  # [FEAT-T20.3]
            web.get('/benchmarks_kpi', self.handle_benchmarks_kpi),  # [FEAT-T21.2]
            # [FEAT-143] Remote Control endpoints (Standard & Cloudflare /attendant/ Path Prefix)
            web.post('/wake', self.handle_remote_action),
            web.post('/sleep', self.handle_remote_action),
            web.post('/lock', self.handle_remote_action),
            web.post('/shutdown', self.handle_remote_action),
            web.post('/attendant/wake', self.handle_remote_action),
            web.post('/attendant/sleep', self.handle_remote_action),
            web.post('/attendant/lock', self.handle_remote_action),
            web.post('/attendant/shutdown', self.handle_remote_action),
            web.get('/attendant/status', self.handle_status),
            web.get('/attendant/version', self.handle_version),
            # [LAB-088] EarNode Emergency Deafness: Manual rearm endpoint
            web.post('/rearm_ear', self.handle_rearm_ear)
        ])
        
        # [FIX-CORS] Middleware handles CORS at app creation; no per-route setup needed.

    async def handle_remote_action(self, request):
        """REST endpoint for remote control UI."""
        path = request.path.replace('/attendant/', '/')
        action = path.lstrip('/')
        await self.enqueue_intent(f"[OPERATIONAL] {action.upper()}", source="REMOTE")
        return web.json_response({"status": "success", "message": f"{action.capitalize()} signal enqueued."})

    async def handle_rearm_ear(self, request):
        """REST endpoint to manually rearm EarNode after emergency unload. [LAB-088]"""
        try:
            if self.status.sensory_mode != SensoryMode.PAUSED:
                return web.json_response({
                    "status": "ERROR", 
                    "message": "EarNode not in rearm-ready state (must be paused after unload)."
                }, status=400)
                
            logger.info("[FOYER] Manual EarNode rearm requested...")
            success = await self.sensory.rearm_sensory_ear()
            if success:
                self.status.sensory_mode = SensoryMode.ACTIVE
                return web.json_response({"status": "REARMED"})
            else:
                return web.json_response({"status": "ERROR", "message": "Failed to rearm EarNode."})
        except Exception as e:
            return web.json_response({"status": "ERROR", "message": str(e)}, status=400)

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
            if "state_changed_at" in data:
                self.status.state_changed_at = data["state_changed_at"]
            self.status.vocal = data.get("vocal", self.status.vocal)
            self.status.engine_up = data.get("engine_up", self.status.engine_up)
            self.status.vram_used = data.get("vram_used", self.status.vram_used)
            self.status.vram_total = data.get("vram_total", self.status.vram_total)
            self.status.ram_pct = data.get("ram_pct", self.status.ram_pct)
            
            # [LAB-088] EarNode Emergency Deafness: Track available RAM and sensory mode
            self.status.available_ram = data.get("available_ram", self.status.available_ram)
            swarm_mode = data.get("swarm_mode", False)
            heads_down_mode = data.get("heads_down_mode", False)
            
            # Trigger unload if RAM < 3.0GB or in Swarm/Heads-Down mode
            if self.status.available_ram < 3.0 or swarm_mode or heads_down_mode:
                if self.status.sensory_mode != SensoryMode.DISABLED:
                    logger.info(f"[FOYER] Triggering EarNode unload: RAM={self.status.available_ram:.1f}GB, Swarm={swarm_mode}, HeadsDown={heads_down_mode}")
                    await self.sensory.unload_sensory_ear(self.status.available_ram, swarm_mode or heads_down_mode)
                    self.status.sensory_mode = SensoryMode.DISABLED
            else:
                if self.status.sensory_mode == SensoryMode.DISABLED:
                    logger.info("[FOYER] EarNode rearm conditions met. Ready to restore.")
                    self.status.sensory_mode = SensoryMode.PAUSED  # Ready for manual rearm
            
            # [FEAT-265.15] Unified Boot: Trigger Ear and logical nodes concurrently based on state transitions
            if self.status.state in ["HIBERNATING", "OFFLINE"]:
                if self.residents.booted:
                    logger.info(f"[FOYER] Lab state is {self.status.state}. Hibernating logical nodes...")
                    asyncio.create_task(self.residents.shutdown())
            elif self.status.state in ["OPERATIONAL"]:
                if not self.residents.booted and not self.residents.booting:
                    logger.info("[FOYER] Lab is OPERATIONAL. Initiating logical boot...")
                    self._launch_resident_boot_async()
            
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
        # [FEAT-028] Periodic Deep Thought (remote) health probe: ping->API + Heavy Prime
        asyncio.create_task(self.thought_health_loop())

    async def handle_health(self, request):
        return web.json_response({"status": "ONLINE", "version": LAB_VERSION})

    async def handle_version(self, request):
        return web.json_response({
            "boot_commit": getattr(self, "boot_commit", "unknown"),
            "boot_timestamp": getattr(self, "boot_timestamp", 0),
            "service": "lab-attendant",
        })

    async def handle_status(self, request):
        status_dict = self.status.to_dict()
        status_dict["connected_clients"] = len(self.connected_clients)
        # [FEAT-426] Expose the session token so the browser client can present it
        # as the WS handshake `lab_key` (browsers cannot set custom WS headers).
        status_dict["session_token"] = self.session_token
        status_dict["boot_commit"] = getattr(self, "boot_commit", "unknown")
        status_dict["boot_timestamp"] = getattr(self, "boot_timestamp", 0)
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

            # Swap usage % (defensive: default 0.0 if unreadable)
            try:
                swap_pct = psutil.swap_memory().percent
            except Exception:
                swap_pct = 0.0

            # Memory pressure avg10 from /proc/pressure/memory (defensive: default 0.0)
            pressure_pct = 0.0
            try:
                with open('/proc/pressure/memory', 'r') as f:
                    for line in f:
                        if line.startswith('some'):
                            pressure_pct = float(line.split('avg10=')[1].split()[0])
                            break
            except Exception:
                pressure_pct = 0.0

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
                "swap_pct": round(swap_pct, 1),
                "pressure_pct": round(pressure_pct, 2),
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
                            logger.warning("[FOYER] failed to parse sample JSON line", exc_info=True)
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
                            logger.warning("[FOYER] failed to parse benchmark run line", exc_info=True)

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
        # [FEAT-426] Origin Security Guard: browsers cannot set custom WS headers,
        # so the authoritative check is the handshake-frame `lab_key` below. The
        # pre-prepare header check is defense-in-depth for non-browser clients:
        # a PRESENT-but-invalid X-Lab-Key header is rejected with 403; an absent
        # header is allowed through to the handshake-frame check (browser case).
        presented_key = ws_request.headers.get("X-Lab-Key", "")
        if presented_key and presented_key != self.session_token:
            peer = ws_request.remote
            logger.warning(f"[FOYER] Rejected WS connection from {peer}: missing/invalid X-Lab-Key")
            raise web.HTTPForbidden(reason="missing or invalid X-Lab-Key")

        ws = web.WebSocketResponse(heartbeat=300.0)
        await ws.prepare(ws_request)
        
        socket_id = str(uuid.uuid4())[:8]
        self.connected_clients.add(ws)
        logger.info(f"Client connected: {socket_id}")
        # Note: Routine handshakes logged to stdout only to keep pager_activity.json clean.
        
        # Cancel disconnect timer if it is running
        if self.disconnect_timer is not None:
            logger.info("[FOYER] Client reconnected. Cancelling idle shutdown timer.")
            self.disconnect_timer.cancel()
            self.disconnect_timer = None
            
        await ws.send_str(json.dumps(self.status.to_dict()))
        
        authenticated = False  # [FEAT-426] First frame must be a valid handshake.
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    m_type = data.get("type")
                    
                    if m_type == "handshake":
                        # [FEAT-426] Origin Security Guard: the browser WebSocket
                        # API cannot set custom headers, so the X-Lab-Key rides the
                        # first frame as `lab_key` and must match the session token.
                        if not authenticated:
                            if data.get("lab_key") != self.session_token:
                                peer = ws_request.remote
                                logger.warning(f"[FOYER] Rejected WS connection from {peer}: missing/invalid X-Lab-Key")
                                await ws.close(code=1008, message=b"missing or invalid X-Lab-Key")
                                break
                            authenticated = True
                            self.session_horizon_ts = int(time.time())
                            logger.info(f"[FOYER] WS client authenticated: {socket_id} (Token: {self.session_token}, Horizon: {self.session_horizon_ts})")
                        await ws.send_str(json.dumps({
                            "type": "status", 
                            "state": "connected", 
                            "socket_id": socket_id,
                            "session_token": self.session_token,
                            "session_horizon_ts": self.session_horizon_ts,
                            "version": LAB_VERSION
                        }))
                    elif not authenticated:
                        # [FEAT-426] Any frame before a valid handshake is refused.
                        peer = ws_request.remote
                        logger.warning(f"[FOYER] Rejected WS connection from {peer}: first frame was not an authenticated handshake")
                        await ws.close(code=1008, message=b"missing or invalid X-Lab-Key")
                        break
                    elif m_type == "text_input":
                        query = data.get("content")
                        req_id = data.get("request_id")
                        # [FEAT-455] Zero-Latency Un-blocked Async Preamble: the receive
                        # loop must return instantly — never await file I/O or the
                        # broadcast inline. The Deep Thought preamble + enqueue run as
                        # an un-gated background task (no boot/wake/VRAM gating here;
                        # queue_drainer owns those gates).
                        asyncio.create_task(self._spawn_deep_thought_preamble(query, source=f"WS_{socket_id}", request_id=req_id))
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
                    if not authenticated:
                        # [FEAT-426] Refuse audio before an authenticated handshake.
                        logger.warning(f"[FOYER] Rejected WS connection from {ws_request.remote}: binary frame before authenticated handshake")
                        await ws.close(code=1008, message=b"Unauthorized")
                        break
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

            # Disconnect memory reclaim: flush audio ring-buffer and force GC.
            # Defensive — a failure here must never break the disconnect/timer path.
            try:
                self.sensory.audio_buffer = np.zeros(0, dtype=np.int16)
                gc.collect()
                logger.info("[FOYER] Disconnect cleanup: audio ring-buffer flushed and gc.collect() invoked.")
            except Exception as exc:
                logger.warning(f"[FOYER] Disconnect cleanup failed (non-blocking): {exc}")
            
        return ws

# [FEAT-412] Connection-Aware Idle Hibernation Deferral
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
            # [SPR-52.0 / Task 52.3] Stage 2-4 hooks: deduce progress from node streams
            stage_id = STAGE_SOURCE_MAP.get(data.get("source", ""))
            if stage_id and data.get("final"):
                await self._emit_stage_progress(stage_id, data.get("request_id", "default"), "COMPLETED")
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

    async def _spawn_deep_thought_preamble(self, query, source, request_id=None):
        # [FEAT-459 / Sprint 54 Story 5] Non-Blocking Intent Ignition Fork:
        # Enqueue intent at millisecond zero so vLLM/engine ignition starts immediately,
        # while deep thought synthesis and insight broadcast run in parallel as a background task.
        try:
            # [Story 54.5] Step 1: Millisecond zero intent queueing (non-blocking)
            await self.enqueue_intent(query, source=source, request_id=request_id)

            # [Story 54.5] Step 2: Spawn parallel background preamble synthesis & broadcast
            async def _run_synthesis_and_broadcast():
                try:
                    if not self.stage_memory.get(request_id, {}).get("stage1_kender_triage"):
                        await self._emit_stage_progress(
                            "stage1_kender_triage", request_id, "STARTED",
                            detail="unified_llm_synthesis"
                        )

                    hyde_result = await self.cognitive.synthesize_hyde_vector(query)
                    
                    greeting_msg = "Deep Thought: System operational. Awaiting command parameters."
                    
                    if hyde_result:
                        try:
                            m = re.search(r'(\{.*\})', hyde_result, re.DOTALL)
                            if m:
                                data = json.loads(m.group(1))
                                if data.get("greeting"):
                                    greeting_msg = data.get("greeting")
                            elif "[VALIDATION]" in hyde_result:
                                greeting_msg = "Deep Thought: Technical domain match detected. Synthesizing Composite HyDE..."
                        except Exception:
                            pass

                    preamble = {
                        "type": "crosstalk",
                        "brain": f"[DEEP THOUGHT]: {greeting_msg}",
                        "brain_source": "Deep Thought",
                        "channel": "insight",
                        "final": False,
                        "version": LAB_VERSION
                    }
                    if request_id:
                        preamble["request_id"] = request_id
                    await self.broadcast(preamble)
                except Exception as inner_e:
                    logger.error(f"[FEAT-459] Background preamble synthesis failed: {inner_e}")
                    await self.broadcast({
                        "type": "crosstalk",
                        "brain": f"[PREAMBLE ERROR] Preamble synthesis failed: {inner_e}",
                        "brain_source": "System"
                    })

            asyncio.create_task(_run_synthesis_and_broadcast())
        except Exception as e:
            logger.error(f"[FEAT-459] Deep Thought intent ignition failed: {e}")
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"[IGNITION ERROR] Intent enqueue failed: {e}",
                "brain_source": "System"
            })

    async def waterfall_drainer(self):
        """[Task 12.3] Drains internal token buffer into final Pop messages for UI."""
        logger.info("Waterfall drainer active (Pop Mode).")
        from collections import defaultdict
        
        # [Task 14.2] Isolated buffers by (request_id, source)
        pending_chunks = defaultdict(str)
        chunk_timestamps = {}
        _judge_semaphore = asyncio.Semaphore(2)

        while True:
            try:
                data = await self.waterfall_queue.get()

                source = str(data.get("brain_source", data.get("source", "Unknown")))
                token = data.get("brain", "")
                final = data.get("final", False)
                request_id = data.get("request_id", "default")
                
                buf_key = (request_id, source)
                chunk_timestamps[buf_key] = time.time()

                if token:
                    # [Story 54.7] Standalone t=0 Warming Pop:
                    # If token is a warming status notice from loader.py, pop it immediately
                    # to the chat console and do not concatenate into the eventual response buffer.
                    if "The local engine is warming its anchors" in token:
                        await self.broadcast({
                            "type": "chat",
                            "brain": token.strip(),
                            "brain_source": source,
                            "final": True,
                            "channel": "chat",
                            "request_id": request_id
                        })
                    else:
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

                        # [SPR-52.0 / Task 52.3] Stage 5: contract completion (idempotent)
                        if self.stage_memory.get(request_id, {}).get("stage5_pinky_review") is None:
                            await self._emit_stage_progress("stage5_pinky_review", request_id, "COMPLETED")

                        # [LAB-010/LAB-096] Judge Evaluation with Semaphore (max 2 concurrent)
                        if _mlx_judge is not None:
                            turn_trace = f"SOURCE:{source}\n{content}"
                            context_window = f"request_id:{request_id}"
                            async def _run_mlx_judge(tt=turn_trace, cw=context_window, rid=request_id, src=source):
                                try:
                                    async with _judge_semaphore:
                                        result = await _mlx_judge.evaluate_256k_context(tt, cw)
                                        score = result.get("score", 0)
                                        status = result.get("status", "UNKNOWN")
                                        logger.info(
                                            f"[LAB-010][M5 JUDGE] request={rid} source={src} "
                                            f"status={status} score={score}"
                                        )
                                        # [FEAT-444] Write to judge_backpressure.jsonl
                                        try:
                                            entry = {
                                                "timestamp": time.time(),
                                                "iso_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                                                "request_id": rid,
                                                "source": src,
                                                "turn_trace_length": len(tt),
                                                "context_window_length": len(cw),
                                                "score": score,
                                                "status": status,
                                                "critique": result.get("critique", ""),
                                                "route_feedback": result.get("route_feedback", {}),
                                                "refusal": result.get("refusal", False),
                                                "refusal_reason": result.get("reason", ""),
                                                "context_eval_length": result.get("context_eval_length", 0),
                                                "factual_drift_detected": result.get("factual_drift_detected", None),
                                                "style_critique": result.get("style_critique", ""),
                                            }
                                            os.makedirs(os.path.dirname(JUDGE_BACKPRESSURE_PATH), exist_ok=True)
                                            with open(JUDGE_BACKPRESSURE_PATH, "a") as jf:
                                                jf.write(json.dumps(entry, default=str) + "\n")
                                        except Exception as write_ex:
                                            logger.warning(f"[FEAT-444][JUDGE] Backpressure write failed (non-fatal): {write_ex}")
                                except Exception as je:
                                    logger.warning(f"[LAB-010][M5 JUDGE] Evaluation failed (non-fatal): {je}")
                            asyncio.create_task(_run_mlx_judge())

                        pending_chunks.pop(buf_key, None)
                        chunk_timestamps.pop(buf_key, None)

                # [LAB-095] TTL Sweeper: Clean orphaned pending_chunks keys inactive > 30 seconds
                purged_keys = MaintenanceSweeper.prune_ttl_buffer(pending_chunks, chunk_timestamps, max_age_s=30.0)
                for k in purged_keys:
                    logger.warning(f"[LAB-095] TTL Purge orphaned waterfall buffer key: {k}")

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
                    await self.broadcast({"type": "chat", "brain": random.choice(tics), "brain_source": "Pinky", "channel": "chat"})
            await asyncio.sleep(30)

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
            except Exception as e:
                logger.warning("[FOYER] resident wake failed", exc_info=True)
                await self.broadcast({"type": "error", "message": "Wake failed: " + str(e)})
            await asyncio.sleep(0.5)

    async def scheduled_tasks_loop(self):
        """[FEAT-266/LAB-096/LAB-099] Periodic Maintenance, Heap Scavenger & Thermal Guard Loop."""
        logger.info("Scheduled tasks loop active.")
        last_nibble_time = 0
        while True:
            try:
                # [LAB-099] Thermal Guard: Monitor CPU package thermal zones (thermal_zone0 / thermal_zone3)
                thermal_halt, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(threshold_milli=78000)
                if thermal_halt:
                    logger.warning(
                        f"[LAB-099][THERMAL ALERT] CPU package temp high ({temp_c:.1f}°C). "
                        f"Cooling down background loops 15s..."
                    )
                    await asyncio.sleep(15)
                    continue

                # [LAB-096] Heap Scavenger: Periodic garbage collection every 60s
                collected = MaintenanceSweeper.run_heap_scavenger()
                if collected > 0:
                    logger.debug(f"[LAB-096][GC] Scavenger collected {collected} unreachable objects.")

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

    def _launch_resident_boot_async(self):
        """[STORY-3-5] Guarded detached background boot: never block the drainer loop."""
        if getattr(self.residents, "booted", False) or getattr(self.residents, "booting", False):
            return
        try:
            asyncio.create_task(self.residents.boot_all())
        except Exception as e:
            logger.error("[FOYER] Background resident boot failed: %s", e, exc_info=True)

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
                        # [FEAT-283] Neural Buffer: Cache pre-wake intents received during cold-boot
                        is_cold_boot = not self.residents.booted
                        if is_cold_boot:
                            logger.info("[FEAT-283] Pre-wake intent detected during cold boot. Initiating resident node ignition...")
                            self._launch_resident_boot_async()
                        
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
                                        
                                        # Keep WebSocket alive during node boot
                                        await self.broadcast({
                                            "type": "status",
                                            "state": "SYNCING",
                                            "message": "Physical silicon ready. Syncing logical nodes...",
                                            "brain_source": "System",
                                            "version": LAB_VERSION
                                        })
                                        
                                        # [FEAT-283] Neural Buffer Replay: Wait for node boot if cold, then dispatch
                                        async def _dispatch_buffered_intent(evt_query, evt_src, evt_id):
                                            if not self.residents.booted:
                                                logger.info(f"[FEAT-283] Neural Buffer holding prompt '{evt_query[:20]}...' until node ignition finishes...")
                                                while not self.residents.booted:
                                                    await asyncio.sleep(0.5)
                                                logger.info(f"[FEAT-283] Silicon booted! Replaying buffered prompt '{evt_query[:20]}...' to Division of Labor.")
                                            await self.run_division_of_labor(evt_query, source=evt_src, request_id=evt_id)

                                        asyncio.create_task(_dispatch_buffered_intent(event.query, event.source, event.id))
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
        # [FEAT-426] Explicit loopback binding: the Foyer WS must never listen on 0.0.0.0.
        web.run_app(self.app, host="127.0.0.1", port=PORT)

if __name__ == "__main__":
    router = FoyerRouter()
    router.run()
