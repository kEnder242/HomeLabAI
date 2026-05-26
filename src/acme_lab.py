import asyncio
import json
import logging
import os
import psutil
import random
import socket
import sys
import time
import uuid
from typing import Dict, Set

from infra.atomic_io import atomic_write_json
from infra.montana import reclaim_logger
import aiohttp
from aiohttp import web
import aiohttp_cors
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# Internal Task Imports
import recruiter
from equipment.sensory_manager import SensoryManager
from logic.cognitive_hub import CognitiveHub

# Configuration
PORT = 8765
PYTHON_PATH = sys.executable
VERSION = "3.8.2"  # singleton_lock and engine_probe
ATTENDANT_PORT = 9999
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
STATUS_JSON = os.path.join(WORKSPACE_DIR, "field_notes/data/status.json")
INFRA_CONFIG = os.path.join(LAB_DIR, "config/infrastructure.json")
ORACLE_CONFIG = os.path.join(LAB_DIR, "config/oracle.json")
NIGHTLY_DIALOGUE_FILE = os.path.join(
    WORKSPACE_DIR, "field_notes/data/nightly_dialogue.json"
)
ROUND_TABLE_LOCK = os.path.join(LAB_DIR, "round_table.lock")
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
MAINTENANCE_LOCK = os.path.join(WORKSPACE_DIR, "field_notes/data/maintenance.lock")
STYLE_CSS = os.path.join(WORKSPACE_DIR, "field_notes/style.css")
PAGER_FILE = os.path.join(WORKSPACE_DIR, "field_notes/data/pager_activity.json")


def get_style_key():
    """[FEAT-267] Dynamic Key Discovery for Lab REST calls."""
    import hashlib
    if not os.path.exists(STYLE_CSS):
        return "missing"
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def resolve_brain_url():
    """Resolves the Brain's heartbeat URL from infrastructure config."""
    try:
        if os.path.exists(INFRA_CONFIG):
            with open(INFRA_CONFIG, "r") as f:
                infra = json.load(f)
            primary = (
                infra.get("nodes", {}).get("brain", {}).get("primary", "localhost")
            )
            host_cfg = infra.get("hosts", {}).get(primary, {})
            ip_hint = host_cfg.get("ip_hint", "127.0.0.1")
            port = host_cfg.get("ollama_port", 11434)

            # Dynamic resolution
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


async def verify_engine_liveness():
    """[FEAT-265.7] Checks if the vLLM engine actually has weights loaded and is responding."""
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Port Check
            async with session.get("http://localhost:8088/v1/models", timeout=2) as r:
                if r.status != 200:
                    return False
                data = await r.json()
                # vLLM /v1/models returns data: [{id: ...}]
                models = [m.get("id") for m in data.get("data", [])]
                # If weights are offloaded (Level 2), the model list is usually empty
                # or missing the primary 3B weight set.
                if not any("llama-3.2-3b" in str(m).lower() for m in models):
                    return False
            
            # 2. [FEAT-265.9] Functional Probe: Minimal inference check
            # This prevents the "Nominal but garbage" failure state
            # Note: We use a very low temperature and 1 token to keep it fast.
            probe_payload = {
                "model": "unified-base", 
                "prompt": "ping",
                "max_tokens": 1,
                "temperature": 0.0
            }
            async with session.post("http://localhost:8088/v1/completions", json=probe_payload, timeout=5) as p:
                return p.status == 200
    except Exception:
        return False


class AcmeLab:
    def __init__(self, mode="VLLM", afk_timeout=600, role="HUB"):
        # [FEAT-220] Silicon Handshake: Derive stable session token from fingerprint
        self.role = role
        from infra.montana import get_fingerprint
        self.session_token = get_fingerprint(self.role)
        title = f"acme_lab {self.session_token}"
        try:
            import setproctitle
            setproctitle.setproctitle(title)
        except ImportError:
            sys.argv[0] = title

        # [SINGLETON] Ensure only one instance of AcmeLab runs
        self._lock_file = "/tmp/acme_lab.lock"
        try:
            self._lock_fd = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except OSError:
            # Check if process is actually alive
            try:
                with open(self._lock_file, "r") as f:
                    old_pid = int(f.read().strip())
                if psutil.pid_exists(old_pid):
                    p = psutil.Process(old_pid)
                    if p.status() != psutil.STATUS_ZOMBIE:
                        print(f"[FATAL] AcmeLab already running as PID {old_pid}. Aborting.", file=sys.stderr)
                        sys.exit(0)
                # Reclaim stale or zombie lock
                os.remove(self._lock_file)
                self._lock_fd = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except Exception:
                # Fallback: force open
                self._lock_fd = os.open(self._lock_file, os.O_RDWR)

        os.write(self._lock_fd, str(os.getpid()).encode())
        os.fsync(self._lock_fd)

        self.mode = mode
        self.idle_gate = 600 # [FEAT-363] Standardize on 10m window
        self.status = "INIT"
        self._spark_active = True # [FEAT-314.5] Boot Lock: Prevent early triggers
        self._ignition_lock = asyncio.Lock() # [FEAT-342] Atomic Ignition Lock
        self._handshake_lock = set() # [FIX] Prevent rapid double-sparking
        self.connected_clients: Set[web.WebSocketResponse] = set()
        self.residents: Dict[str, ClientSession] = {}
        # [FEAT-233.2] Waterfall Queue: Shared buffer for real-time inter-node overhearing
        self.waterfall_queue = asyncio.Queue()
        self.shutdown_event = asyncio.Event()
        self._residents_ready = asyncio.Event() # [FIX] Task-safe boot signal
        self.last_activity = time.time()
        self.last_save_event = 0.0
        self.last_typing_event = 0.0  # [FEAT-052] Typing Awareness
        self.reflex_ttl = 1.0
        self.banter_backoff = 0
        self.brain_online = False
        self._last_brain_prime = 0  # [FEAT-085] Keep-alive tracking
        self._priming_in_progress = False # [FEAT-286.2] Strict Latching
        self.mic_active = False  # [FEAT-025] Amygdala Switch State
        self.sensory = SensoryManager(self.broadcast)
        self.cognitive = CognitiveHub(
            self.residents, 
            self.broadcast, 
            self.sensory, 
            get_vram_status=lambda force=False: self.brain_online,
            trigger_morning_briefing=self.trigger_morning_briefing,
            monitor_task_with_tics=self.monitor_task_with_tics,
            last_prime_callback=self._update_prime_timer,
            waterfall_queue=self.waterfall_queue,
            hibernate_callback=self._hibernate
        )
        self.recent_interactions = []
        self.turn_density = 0.0  # [FEAT-154] Sentient Sentinel
        self.last_turn_time = 0.0
        self._disconnect_task = None # [FEAT-171] Idle timer task
        self.last_induction_date = None # [FEAT-202] Track daily grounding
        self.message_history = [] # [FEAT-225] Short-Term Memory Buffer
        self._background_tasks = set() # [FEAT-339] Lifecycle Hardening
        self.current_processing_task = None
        self.engine_ready = asyncio.Event() # [FEAT-265] Waking State synchronization
        self._neural_queue = asyncio.Queue() # [FEAT-283] Neural Buffer: Queue queries during WAKING
        self._wake_task = None # [FEAT-265.47] Task Sovereignty: Track active wake task
        self._triage_lock = asyncio.Lock() # [FEAT-265.48] Absolute State: Prevent concurrent triage
        self._residents_booted = False # [FEAT-337] Resident Persistence
        
        # [Task 7.4] System Replay Buffer: Store recent status/milestones for new clients
        from collections import deque
        self.system_replay_buffer = deque(maxlen=20)

        # [FEAT-365] Lab Config: Load infrastructure settings
        self.config = {}
        if os.path.exists(INFRA_CONFIG):
            try:
                with open(INFRA_CONFIG, "r") as f:
                    self.config = json.load(f)
            except Exception as e:
                logging.error(f"[HUB] Failed to load config: {e}")

        reclaim_logger(role)
        self.set_proc_title()

    def _track_task(self, coro):
        """[FEAT-339] Task Lifecycle: Register and auto-discard background tasks."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def set_proc_title(self):
        """[FEAT-122] Kernel-Level Visibility: Renames process in ps/htop."""
        from infra.montana import get_fingerprint
        title = f"acme_lab {get_fingerprint(self.role)}"
        try:
            import setproctitle
            setproctitle.setproctitle(title)
        except ImportError:
            # Fallback: Overwrite sys.argv
            sys.argv[0] = title
        logging.info(f"[BOOT] Fingerprint established: {get_fingerprint(self.role)}")
    async def broadcast(self, message_dict):
        """[FEAT-221] Safe broadcast with dead-socket pruning, schema enforcement, and server-side logging."""
        if self.shutdown_event.is_set() or not self.connected_clients:
            return

        # [FIX] Schema Enforcement: Ensure type, brain, and brain_source exist
        m_type = message_dict.get("type", "chat")
        m_content = message_dict.get("brain") or message_dict.get("message")

        if not m_content:
            if m_type == "status":
                # [FEAT-221.3] Silence automated state changes to reduce foyer noise
                return
            else:
                m_content = "EMPTY_CONTENT"                
        m_source = message_dict.get("brain_source", "System")
        
        # Back-fill dictionary for clients
        message_dict["type"] = m_type
        message_dict["brain"] = m_content
        message_dict["brain_source"] = m_source
        message_dict["hub_pid"] = os.getpid() # [FEAT-344] Physical signature
        
        # [FEAT-339] Message De-duplication: Attach unique ID if not present
        if "msg_id" not in message_dict:
            message_dict["msg_id"] = uuid.uuid4().hex[:12]

        # [FEAT-274] Token Traceability: Log the current session generation
        # Added physical client count for audit
        logging.info(f"[BROADCAST] [{self.session_token}] [{m_type.upper()}] ({m_source}): {m_content[:60]}... (Sockets: {len(self.connected_clients)})")

        # [Task 7.4] Replay Buffer: Store system milestones
        if m_type in ["crosstalk", "status"] or (m_type == "chat" and m_source == "System"):
            self.system_replay_buffer.append(message_dict)

        # [Task 6.1] Intercept and record thoughts for deferred evaluation [BKM-032]
        if m_type in ["chat", "crosstalk"]:
            try:
                from infra.forensic_ledger import ledger
                ledger.record_thought(m_source, m_content, role=m_type.upper())
            except Exception as e:
                logging.error(f"[LEDGER] Failed to record thought trace: {e}")

        # [FEAT-227] Session Reset: Wipe history on explicit request
        if message_dict.get("reset_session"):
            logging.info("[HUB] Session Reset triggered. Wiping message history.")
            self.message_history = []

        # [FEAT-229] Ascension Rule: Only save final messages to history for persistence
        # [FIX] Historize status/crosstalk so they can be deduped on replay
        if message_dict.get("final", True) or m_type in ["status", "crosstalk"]:
            if not any(old.get("msg_id") == message_dict["msg_id"] for old in self.message_history):
                # [FIX] Deep copy to prevent shared state corruption
                import copy
                self.message_history.append(copy.deepcopy(message_dict))
                self.message_history = self.message_history[-20:] # Keep last 20

        msg_str = json.dumps(message_dict)
        dead_clients = set()
        for ws in list(self.connected_clients):
            try:
                if not ws.closed:
                    await ws.send_str(msg_str)
                else:
                    dead_clients.add(ws)
            except Exception as e:
                logging.debug(f"[HUB] Broadcast failure to client: {e}")
                dead_clients.add(ws)

        # Cleanup
        for dead in dead_clients:
            self.connected_clients.remove(dead)

    def trigger_pager(self, message, severity="INFO", source="System"):
        """[FEAT-298] Centralized pager trigger for Hub-level forensic logging."""
        try:
            entry = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "severity": severity.upper(),
                "source": source,
                "message": message
            }
            activities = []
            if os.path.exists(PAGER_FILE):
                try:
                    with open(PAGER_FILE, 'r') as f:
                        activities = json.load(f)
                except Exception:
                    pass
            activities.append(entry)
            # Keep last 50 for the UI
            atomic_write_json(PAGER_FILE, activities[-50:])
        except Exception as e:
            logging.error(f"[HUB] Pager Trigger Failed: {e}")

    def _update_prime_timer(self, timestamp):
        """[FEAT-287] Activity Latch: Resets the priming timer on model response."""
        self._last_brain_prime = timestamp
        logging.debug(f"[HEALTH] Prime timer reset via activity: {timestamp}")

    async def trigger_morning_briefing(self):
        """[FEAT-072] Briefs the user on recent nightly dialogue."""
        import logging

        if os.path.exists(NIGHTLY_DIALOGUE_FILE):
            try:
                with open(NIGHTLY_DIALOGUE_FILE, "r") as f:
                    data = json.load(f)

                # Brief the user
                content = data.get("content", "")
                summary = content[:500].replace("\n", " ")
                msg = {
                    "brain": f"While you were out, we discussed: {summary}...",
                    "brain_source": "Pinky (Reviewer)",
                    "channel": "chat",
                }
                await self.broadcast(msg)
            except Exception as e:
                logging.error(f"[BRIEF] Failed to trigger briefing: {e}")

    async def monitor_task_with_tics(self, coro, delay=2.5):
        """Sends state-aware tics during long reasoning tasks."""
        task = self._track_task(coro)

        # Standard character tics as fallback
        base_tics = [
            "Thinking...",
            "Processing...",
            "Just a moment...",
            "Checking circuits...",
        ]

        current_delay = delay
        tic_count = 0

        while not task.done():
            # [FEAT-365] Configurable Reflexes (Reactive Check)
            enabled = self.config.get("enable_reflexes", True)

            try:
                # [FEAT-053] Dynamic Shadow Tics: 
                # Attempt to get a characterful tic from the local Sentinel (Lab Node)
                # We use the Sentinel for speed and residency.
                tic_msg = None
                
                # Check if reflexes are enabled
                if not enabled:
                    await asyncio.wait_for(asyncio.shield(task), timeout=current_delay)
                    continue

                if self.residents.get("lab") and tic_count > 0:
                    try:
                        tic_res = await self.residents["lab"].call_tool("think", {
                            "query": "[INTERNAL_STATUS_MODE] Provide a 1-sentence cognitive 'tic' or status update for the user while the deep-think completes. Be brief, character-rich, and engineering-clinical.",
                            "fuel": 0.1
                        })
                        if tic_res.content and hasattr(tic_res.content[0], "text"):
                            tic_msg = tic_res.content[0].text
                    except Exception as e:
                        logging.debug(f"[HUB] Dynamic Tic Generation failed: {e}")

                if not tic_msg:
                    if not self.brain_online:
                        tic_msg = "Sovereign unreachable... attempting failover."
                    elif tic_count == 0:
                        tic_msg = "Resonating weights... waking the Architect."
                    else:
                        tic_msg = random.choice(base_tics)

                # Wait for task or timeout
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=current_delay)
                except asyncio.TimeoutError:
                    if self.connected_clients and not self.is_user_typing():
                        await self.broadcast(
                            {"type": "crosstalk", "brain": tic_msg, "brain_source": "Shadow"}
                        )
                    tic_count += 1
                    # Increase delay exponentially
                    current_delay = min(current_delay * 1.5, 15.0)

                if task.done():
                    return task.result()
            except Exception:
                if task.done():
                    return task.result()
        return task.result()

    async def check_brain_health(self, force=False):
        """[FEAT-265.31] State-Aware Probe: Suppress heartbeats only during raw silicon boot."""
        # [FEAT-344] Sovereign Hardening: Allow probes during WAKING to ensure relay is ready.
        if self.status in ["BOOTING", "INIT"]:
            logging.debug(f"[HEALTH] Sovereignty Gate: Aborting probe during {self.status}.")
            return

        now = time.time()

        # Initialize sticky tracking if missing

        if not hasattr(self, "_last_brain_fail"):
            self._last_brain_fail = 0
        if not hasattr(self, "_last_brain_ping"):
            self._last_brain_ping = 0

        # [BKM-026] 60s Failure Penalty Box
        if not force and not self.brain_online and (now - self._last_brain_fail < 60):
            return

        try:
            target_url = resolve_brain_url()
            async with aiohttp.ClientSession() as session:
                # Tier 1: Light API Check (Status only)
                try:
                    async with session.get(target_url, timeout=2.0) as r:
                        is_reachable = r.status == 200
                        if not is_reachable:
                            if self.brain_online: 
                                logging.info("[HEALTH] KENDER Offline. Entering 60s penalty box.")
                                await self.broadcast({
                                    "brain": "Strategic Sovereignty: SHADOW (Primary Offline)",
                                    "brain_source": "System",
                                    "channel": "insight"
                                })
                            self.brain_online = False
                            self._last_brain_fail = now
                            return
                        
                        data = await r.json()
                        models = [m.get("name") for m in data.get("models", [])]
                        if not models:
                            self.brain_online = False
                            return
                        
                        # [FIX] Distinguish between transition and stable state
                        if not self.brain_online:
                            logging.info("[BRAIN] Strategic Sovereignty: PRIMARY (Online)")
                            await self.broadcast({
                                "brain": "Strategic Sovereignty: PRIMARY",
                                "brain_source": "System",
                                "channel": "insight"
                            })
                        self.brain_online = True # API is at least talking
                except Exception as e:
                    if self.brain_online:
                        logging.info(f"[HEALTH] KENDER Offline. Entering 60s penalty box. (Error: {e})")
                        await self.broadcast({
                            "brain": "Strategic Sovereignty: SHADOW (Primary Offline)",
                            "brain_source": "System",
                            "channel": "insight"
                        })
                    self.brain_online = False
                    self._last_brain_fail = now
                    return

                # --- Tier 2: Heavy Prime (GPU Wake) ---
                # [FEAT-134] AFK Presence Gate: Never wake GPU if room is empty
                is_restoring = self.status in ["WAKING", "BOOTING"]
                
                if self.connected_clients == 0 and not force:
                    logging.debug("[HEALTH] Heavy Prime Bypassed: No clients connected to foyer.")
                    return

                # [FEAT-285] Cooldown Management
                last_prime_delta = now - getattr(self, "_last_brain_prime", 0)
                should_prime = force or is_restoring or (last_prime_delta > 120)
                
                if not should_prime:
                    logging.debug(f"[HEALTH] Heavy Prime Bypassed: Cooldown active ({int(last_prime_delta)}s < 120s).")
                    return

                # [FEAT-286.2] Strict Latching: Only allow one active background prime
                if self._priming_in_progress:
                    logging.debug("[HEALTH] Heavy Prime Bypassed: Task already in progress.")
                    return

                # [FEAT-155] Speed over Scale: Prioritize 8B models for <10s load times
                probe_model = models[0] if models else "llama3.1:8b" # Fallback to 8B standard
                preferred = ["llama3.1:8b", "mixtral:8x7b", "gemma2:2b"]
                for p in preferred:
                    if p in models:
                        probe_model = p
                        break
                
                logging.info(f"[HEALTH] Initiating Heavy Prime on KENDER: {probe_model} (Force={force}, Restoring={is_restoring})")
                
                p_url = target_url.replace("/api/tags", "/api/generate")
                payload = {"model": probe_model, "prompt": "ping", "stream": False, "options": {"num_predict": 1}}
                
                # [BKM] Parallel Execution: Generation probe runs in background to prevent Hub hangs
                self._priming_in_progress = True
                async def _bg_prime():
                    try:
                        async with aiohttp.ClientSession() as p_session:
                            async with p_session.post(p_url, json=payload, timeout=30) as pr:
                                if pr.status == 200:
                                    logging.info(f"[HEALTH] Strategic Sovereign SUCCESS: {probe_model} is resident in VRAM.")
                                    self._last_brain_prime = time.time()
                                else:
                                    logging.error(f"[HEALTH] Heavy Prime Failed on KENDER ({pr.status})")
                    except Exception as pe:
                        logging.error(f"[HEALTH] Heavy Prime Exception (KENDER): {pe}")
                    finally:
                        self._priming_in_progress = False

                self._track_task(_bg_prime())

        except Exception as e:
            logging.debug(f"[HEALTH] Overall brain probe failed: {e}")
            self.brain_online = False

    async def spark_restoration(self, client_id="system", intent="ACTIVE", skip_lock=False):
        """[FEAT-265.8] Reusable ignition spark for Handshakes and Alarms."""
        if not skip_lock:
            # [FEAT-265.45] Immediate Spark Lock: Prevent async races during status fetch
            if getattr(self, "_spark_active", False) or self.status == "BOOTING":
                return
            
            async with self._ignition_lock:
                # Re-check flag inside lock
                if getattr(self, "_spark_active", False):
                    return
                self._spark_active = True
        
        # [FEAT-291] Passive Guard: Don't spark if the intent is strictly PASSIVE (e.g., status check)
        # unless we are already in a waking state.
        if intent == "PASSIVE" and self.status == "HIBERNATING":
            self._spark_active = False # Release if guard blocks
            return

        # [FEAT-282.5] Authority Handover: Only yield if Attendant is ALREADY igniting
        # [FEAT-265.26] Sovereign Override: NEVER yield if physically hibernating
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:9999/status", headers={'X-Lab-Key': get_style_key()}, timeout=1.0) as r:
                    if r.status == 200:
                        data = await r.json()
                        # Physical truth: If hibernating, we must spark, regardless of reason
                        v_reason = data.get("vitals", {}).get("reason", "")
                        c_reason = data.get("current_reason", "")
                        
                        if data.get("mode") == "HIBERNATING":
                            logging.info("[HUB] Sovereign Override: Attendant is HIBERNATING. Reclaiming ignition authority.")
                        elif v_reason in ["SAFE_PILOT", "MANUAL_IGNITION", "RECOVERY", "FOYER_RECOVERY"] or v_reason.startswith("RESTORE_") or c_reason.startswith("RESTORE_"):
                            logging.info(f"[HUB] Yielding restoration trigger ({client_id}) to active Attendant session (Current: {v_reason or c_reason}).")
                            self._spark_active = False # Release lock if yielding
                            return
        except Exception:
            pass

        self.status = "WAKING"
        self.engine_ready.clear() # [FIX] Reset state machine early
        self.last_activity = time.time()
        
        # [FEAT-317.5] Instant Feedback: Tell the user we are sparking
        await self.broadcast({'type': 'crosstalk', 'brain': f'⚡ [IGNITION] Restoration sequence initiated ({client_id}).', 'brain_source': 'System'})
        
        # [FEAT-294] Forensic Ignition: Log the specific source and intent of the wake event
        msg = f"Ignition Sequence Initiated. Source: {client_id} | Intent: {intent}"
        logging.warning(f"[HUB] {msg}")
        self.trigger_pager(msg, severity="info", source="Hub")
        
        # [FEAT-265.14] Sovereign Sync: We yield to the Attendant's vLLM path only.
        # Removed the parallel check_brain_health call to prevent local Ollama priming.

        # [FEAT-265.21] Key Integrity: Refresh style key immediately before spark
        # to prevent 401 Unauthorized due to file edits during session
        current_style_key = get_style_key()
        
        async def _run_ignition(cid):
            await asyncio.sleep(5) # [FIX] Settle window for Attendant watchdog
            try:
                async with aiohttp.ClientSession() as session:
                    key = current_style_key
                    headers = {'X-Lab-Key': key, 'Content-Type': 'application/json'}
                    target_engine = self.mode if self.mode in ["VLLM", "OLLAMA"] else "VLLM"
                    
                    async with session.post("http://127.0.0.1:9999/start", 
                                     headers=headers, 
                                     json={
                                         "engine": target_engine, 
                                         "model": "MEDIUM", 
                                         "engine_only": True,
                                         "op_mode": "SERVICE_UNATTENDED",
                                         "reason": f"RESTORE_{cid.upper()}"
                                     }) as r:
                        if r.status == 200:
                            logging.info("[HUB] Spark Success. Yielding to Attendant for readiness...")

                            # [FEAT-342] Safe-Anchor Window: Wait for silicon to stabilize
                            await asyncio.sleep(3.0) 

                            # Yield to Authority: Wait for Attendant to confirm silicon is OPERATIONAL
                            try:
                                # [FEAT-363] Event Polling & Timeout Hardening (300s)
                                seen_events = set()
                                wait_start = time.time()
                                while time.time() - wait_start < 300:
                                    # 1. Poll Attendant's heartbeat for event ledger
                                    try:
                                        async with session.get(f"http://127.0.0.1:9999/heartbeat?key={key}", timeout=1.0) as h_req:
                                            if h_req.status == 200:
                                                h_data = await h_req.json()
                                                vitals = h_data
                                                
                                                ledger = vitals.get("event_ledger", [])
                                                for ev in ledger:
                                                    ev_id = f"{ev.get('timestamp')}_{ev.get('message')}"
                                                    if ev_id not in seen_events:
                                                        seen_events.add(ev_id)
                                                        await self.broadcast({
                                                            "type": "crosstalk",
                                                            "brain": f"[SYSTEM] {ev.get('message')}",
                                                            "brain_source": "System"
                                                        })
                                                
                                                # [FIX] Warming Deadlock: Recognize SERVICE_UNATTENDED early
                                                is_vocal = vitals.get("operational")
                                                is_unattended = self.mode == "SERVICE_UNATTENDED" and vitals.get("engine_up")
                                                
                                                if is_vocal or is_unattended:
                                                    logging.info(f"[HUB] Ignition Success (Vocal: {is_vocal}, Unattended: {is_unattended}). Restoring residents...")
                                                    self.trigger_pager(f"Restoration SUCCESS: {cid}", severity="info", source="Hub")
                                                    self._track_task(self._resident_lifecycle_task())
                                                    return
                                    except Exception:
                                        pass

                                    # 2. Check if OPERATIONAL via short-timeout wait_ready
                                    try:
                                        async with session.get(f"http://127.0.0.1:9999/wait_ready?timeout=1&key={key}", timeout=2.0) as ready_req:
                                            if ready_req.status == 200:
                                                logging.info("[HUB] Attendant confirmed OPERATIONAL. Restoring residents...")
                                                self.trigger_pager(f"Restoration SUCCESS: {cid}", severity="info", source="Hub")
                                                self._track_task(self._resident_lifecycle_task())
                                                return
                                    except Exception:
                                        pass

                                    await asyncio.sleep(2.0)

                                logging.error("[HUB] wait_ready timed out after 300s.")
                                self.status = "ERROR"
                            except Exception as e:
                                logging.error(f"[HUB] Wait-Ready request failed: {e}")
                                self.status = "ERROR"

            except Exception as e:
                logging.error(f"[HUB] Spark reload failed: {e}")
                self.status = "ERROR"
            finally:
                self._spark_active = False

        self._track_task(_run_ignition(client_id))

    async def reflex_loop(self):
        """Background maintenance and status updates grounded in silicon truth."""
        tics = ["Narf!", "Poit!", "Zort!", "Checking circuits...", "Egad!", "Trotro!"]
        
        while not self.shutdown_event.is_set():
            # [FEAT-365] Configurable Reflexes (Reactive Check)
            enabled = self.config.get("enable_reflexes", True)
            
            # [FEAT-318.11] Dynamic Reflex: Poll faster during transitions (5s) or slow during idle (30s)
            poll_rate = 5.0 if self.status in ["HIBERNATING", "WAKING", "BOOTING"] else 30.0
            await asyncio.sleep(poll_rate)
            
            # Skip tics if disabled
            if enabled:
                # [FEAT-052] User typing suppression
                if self.connected_clients and not self.is_user_typing():
                    tic_msg = random.choice(tics)
                    await self.broadcast({"type": "crosstalk", "brain": tic_msg, "brain_source": "Pinky"})
            
            # [FEAT-329] Activity-Aware Probing: Track silence for cool-down
            idle_time = time.time() - self.last_activity
            is_active = (idle_time < 300) # 5m Activity Window

            # [FEAT-265.24] Physical Sync: Pull heartbeat from Attendant
            try:
                # [FEAT-267] Use dynamic key for REST authorization
                expected_key = get_style_key()
                async with aiohttp.ClientSession() as session:
                    headers = {'X-Lab-Key': expected_key}
                    async with session.get("http://127.0.0.1:9999/heartbeat", headers=headers, timeout=2.0) as r:
                        if r.status == 200:
                            vitals = await r.json()
                            self._last_vitals = vitals
                            phys_hibernating = (vitals.get("mode") == "HIBERNATING")
                            
                            # Ground truth: If physically hibernating, we MUST be logically hibernating
                            if phys_hibernating and self.status != "HIBERNATING":
                                logging.warning("[HUB] Physical Sync: Engine is HIBERNATING. Reverting logical status.")
                                self.status = "HIBERNATING"
                                self.engine_ready.clear()
                            
                            # [FEAT-363] Recognize SERVICE_UNATTENDED transition
                            is_vocal = vitals.get("operational")
                            is_unattended = self.mode == "SERVICE_UNATTENDED" and vitals.get("engine_up")
                            
                            if (is_vocal or is_unattended) and self.status == "HIBERNATING":
                                logging.info(f"[OPERATIONAL] Hub foyer successfully woken from sleep (Vocal: {is_vocal}, Unattended: {is_unattended}).")
                                self.status = "OPERATIONAL"
                                self.engine_ready.set()
                                self.last_activity = time.time()
            except Exception:
                pass

            # [FEAT-249.2] Hardened VRAM Hibernation Logic (Lobby Residency)
            is_hibernating = (idle_time > self.idle_gate)

            if is_hibernating and self.status == "OPERATIONAL":
                logging.warning(f"[HUB] VRAM Hibernation triggered ({int(idle_time)}s idle). Unloading local engines...")
                self.status = "HIBERNATING"
                self.engine_ready.clear() # [FEAT-265.15] Readiness Reset
                
                # [LAB-001] Read configured H-Level
                h_level = 2
                try:
                    if os.path.exists(INFRA_CONFIG):
                        with open(INFRA_CONFIG, "r") as f:
                            h_level = json.load(f).get("vram_hibernation_level", 2)
                except Exception:
                    pass
                self._track_task(self._hibernate(level=h_level))
                self.brain_online = False # Mark offline while sleeping

            if self.connected_clients:
                # [FEAT-221.2] Persona Gate: Only banter if the mind is actually active
                if self.status == "OPERATIONAL":
                    if random.random() < 0.1: # 10% chance per tick
                        await self.broadcast({"type": "crosstalk", "brain": random.choice(tics), "brain_source": "Pinky"})
                
                await self.broadcast(
                    {
                        "type": "status",
                        "state": self.status.lower(), # [FEAT-265] Granular states: waking, hibernating, operational
                        "brain_online": self.brain_online,
                        "full_lab_ready": self.brain_online and self.status == "OPERATIONAL", # [FEAT-265.6]
                        "hibernating": (self.status == "HIBERNATING")
                    }
                )
                # [FEAT-039] Banter Decay: Slow down reflexes when idle (> 60s)
                if idle_time > 60:
                    if not self.is_user_typing() and random.random() < 0.05:
                        await self.broadcast({"type": "crosstalk", "brain": random.choice(tics), "brain_source": "Pinky"})

                # [FEAT-329] Remote Brain Cool-down: Suspend probes during extended inactivity
                if is_active or self.status in ["WAKING", "BOOTING"]:
                    await self.check_brain_health()
                else:
                    if self.brain_online:
                        logging.info("[HEALTH] Remote Brain Cool-down: Suspending probes due to inactivity.")
                        self.brain_online = False # Mark as passive/cooling

    async def _log_tailer_loop(self):
        """[FEAT-313.2] Live Engine Logs: Stream vLLM progress to the Intercom."""
        vllm_log = os.path.join(LAB_DIR, 'vllm_server.log')
        last_pos = 0
        if os.path.exists(vllm_log):
            # [FEAT-313.2] Back-Scan: Read recent context upon foyer opening
            last_pos = max(0, os.path.getsize(vllm_log) - 1000)
            
        while True:
            if self.status != "OFFLINE" and os.path.exists(vllm_log):
                try:
                    curr_size = os.path.getsize(vllm_log)
                    if curr_size < last_pos:
                        last_pos = 0 # [FIX] Handle truncation/rotation
                    
                    if curr_size > last_pos:
                        with open(vllm_log, 'r') as f:
                            f.seek(last_pos)
                            lines = f.readlines()
                            last_pos = curr_size
                            import re
                            # [FEAT-313.6] ANSI Stripper: Clinical log rendering
                            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                            
                            for raw_line in lines:
                                if any(k in raw_line for k in ['Loading weights', 'Application startup', 'Engine core', 'ZMQ', 'VOCAL', 'wake_up', 'sleep', 'throughput', 'Resuming']):
                                    # [FEAT-313.6] Log Hardening: Strip ANSI escapes and handle encoding
                                    clean_line = ansi_escape.sub('', raw_line)
                                    msg = clean_line.strip().split('] ')[-1] if '] ' in clean_line else clean_line.strip()
                                    
                                    # [FEAT-317.5] Throughput Beautification: Keep the console clean but informative
                                    if 'throughput' in msg:
                                        # [FIX] Suppress throughput spam once Operational
                                        if self.status == "OPERATIONAL":
                                            continue
                                        
                                        # Only broadcast throughput every 10s or so to avoid spam
                                        if int(time.time()) % 10 == 0:
                                            msg = 'Engine Status: ' + msg.split('Engine 000: ')[-1]
                                        else:
                                            continue

                                    await self.broadcast({'type': 'crosstalk', 'brain': f'[vLLM]: {msg}', 'brain_source': 'System'})
                except Exception:
                    pass
            await asyncio.sleep(1.0)

    async def _hibernate(self, level=1, recover=False):
        """[FEAT-249.7] Centralized Hibernation Logic: Bridges to Attendant REST API."""
        try:
            # [FEAT-267] Use dynamic key for REST authorization
            expected_key = get_style_key()
            
            async with aiohttp.ClientSession() as session:
                headers = {'X-Lab-Key': expected_key}
                url = f"http://127.0.0.1:9999/hibernate?level={level}&recover={'true' if recover else 'false'}"
                async with session.post(url, headers=headers, timeout=5) as resp:
                    if resp.status != 200:
                        res_text = await resp.text()
                        logging.error(f"[HUB] Hibernation REST failed: {resp.status} - {res_text}")
                    else:
                        if level >= 3:
                            logging.info("[HUB] Deep Sleep (H3) accepted. Shutdown sequence initiated.")
                            self.shutdown_event.set()
                            return

                        logging.info(f"[HUB] Hibernation (H{level}) signal accepted. Reverting status.")
                        self.status = "HIBERNATING"
                        self.engine_ready.clear()
                        # [FEAT-337] Resident Persistence: We NO LONGER clear residents or close the stack here.
                        # Subprocesses remain alive and passive in RAM.
        except Exception as e:
            logging.error(f"[HUB] Hibernation request error: {e}")

    async def run_full_induction_cycle(self, auto_hibernate=False):
        """Executes the Inverted Chain: Fast admin tasks -> Long-tail GPU grind."""
        # [FEAT-331] Physical Lockdown: Notify Attendant to prevent OOM collisions
        try:
            expected_key = get_style_key()
            async with aiohttp.ClientSession() as session:
                await session.post(f"http://127.0.0.1:9999/lockdown?key={expected_key}")
                logging.info("[ALARM] Physical Lockdown initiated via Attendant.")
        except Exception as e:
            logging.warning(f"[ALARM] Lockdown handshake failed: {e}")

        self.status = "MAINTENANCE"
        msg = "[ALARM] Initiating Full Induction Cycle..."
        await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})
        self.trigger_pager(msg, severity="info", source="Induction")
        
        # 1. Nightly Dialogue (Fast Local)
        logging.info("[ALARM] Step 1: Nightly Dialogue...")
        self.trigger_pager("Step 1: Nightly Dialogue...", severity="info", source="Induction")
        self.last_activity = time.time() # [FIX] Prevent hibernation during turns
        a_node = self.residents.get("archive")
        p_node = self.residents.get("pinky")
        b_node = self.residents.get("brain")
        try:
            from internal_debate import run_nightly_talk
            await run_nightly_talk(a_node, p_node, b_node)
        except Exception as e:
            logging.error(f"[ALARM] Nightly Dialogue failed: {e}")

        # 2. Nightly Recruiter (Mixed)
        logging.info("[ALARM] Step 2: Nightly Recruiter...")
        self.trigger_pager("Step 2: Nightly Recruiter...", severity="info", source="Induction")
        self.last_activity = time.time()
        br_node = self.residents.get("browser")
        try:
            await recruiter.run_recruiter_task(a_node, b_node, br_node)
        except Exception as e:
            logging.error(f"[ALARM] Recruiter Task failed: {e}")

        # 3. Hierarchy Refactor (CPU)
        logging.info("[ALARM] Step 3: Hierarchy Refactor...")
        self.trigger_pager("Step 3: Hierarchy Refactor...", severity="info", source="Induction")
        if "lab" in self.residents:
            try:
                await self.residents["lab"].call_tool(name="build_semantic_map")
            except Exception as e:
                logging.error(f"[ALARM] Lab Task failed: {e}")

        # [FEAT-299] Pulse Preservation: Run long-tail tasks in background
        async def _run_background_induction():
            # 4. Sequential Harvest (Long-Tail 4090)
            logging.info("[ALARM] Step 4: Sequential Harvest...")
            self.trigger_pager("Step 4: Sequential Harvest...", severity="info", source="Induction")
            try:
                harvest_script = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/forge/serial_harvest_v2.py")
                # [FEAT-343] Subprocess Hardening: 20-minute limit
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, harvest_script,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1200)
                    if stdout:
                        logging.info(f"[ALARM] Harvest Output: {stdout.decode().strip()}")
                    if stderr:
                        logging.error(f"[ALARM] Harvest Error: {stderr.decode().strip()}")
                except asyncio.TimeoutError:
                    proc.kill()
                    logging.error("[ALARM] Harvest TIMEOUT (20m). Silicon reclaimed.")
            except Exception as e:
                logging.error(f"[ALARM] Harvest failed: {e}")

            # 5. Nightly Dream Pass (Long-Tail 4090)
            logging.info("[ALARM] Step 5: Nightly Dream Pass...")
            self.trigger_pager("Step 5: Nightly Dream Pass...", severity="info", source="Induction")
            try:
                # [FEAT-292] Dream Guard: Prevent redundant processes
                check_proc = await asyncio.create_subprocess_exec(
                    "pgrep", "-f", "dream_voice.py",
                    stdout=asyncio.subprocess.PIPE
                )
                stdout, _ = await check_proc.communicate()
                if check_proc.returncode == 0 and len(stdout.strip().split(b"\n")) >= 1:
                     logging.warning("[ALARM] Dream Pass already in progress. Skipping redundant spawn.")
                else:
                    dream_script = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/forge/dream_voice.py")
                    # [FEAT-296] Reverse-Order Dream with 2-hour morning window
                    proc = await asyncio.create_subprocess_exec(
                        sys.executable, dream_script, "100", "voice", "--order", "reverse", "--hours", "2",
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    try:
                        # [FEAT-343] Subprocess Hardening: 120-minute limit for full pass
                        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=7200)
                        if stdout:
                            logging.info(f"[ALARM] Dream Output: {stdout.decode().strip()}")
                        if stderr:
                            logging.error(f"[ALARM] Dream Error: {stderr.decode().strip()}")
                    except asyncio.TimeoutError:
                        proc.kill()
                        logging.error("[ALARM] Dream Pass TIMEOUT (2h). Silicon reclaimed.")
            except Exception as e:
                logging.error(f"[ALARM] Dream Pass failed: {e}")

            # 6. Nightly Forge (Autonomous LoRA Weight Induction)
            logging.info("[ALARM] Step 6: Nightly Forge Turn...")
            self.trigger_pager("Step 6: Nightly Forge Turn...", severity="info", source="Induction")
            try:
                # [FEAT-217] Sequenced Batch Forge: Train all three soul components every night
                target = "lab_history,cli_voice,lab_sentinel"
                logging.info(f"[ALARM] Forging soul components: {target}")

                if "archive" in self.residents:
                    # [FEAT-297] Fire-and-Forget Forge: Dispatched from backgrounder.
                    # We set Hub status to MAINTENANCE to prevent ghost wake-ups.
                    self.status = "MAINTENANCE"
                    await self.residents["archive"].call_tool("lab_train_adapter", {"adapter_name": target, "steps": 60})
                    logging.info("[ALARM] Forge signal dispatched. Hub yielding silicon authority.")
            except Exception as e:
                logging.error(f"[ALARM] Nightly Forge failed: {e}")

            msg_final = "[ALARM] Full Induction Cycle Complete."
            await self.broadcast({"type": "crosstalk", "brain": msg_final, "brain_source": "System"})
            self.trigger_pager(msg_final, severity="info", source="Induction")

            # [FEAT-331] Physical Release: Allow normal Lab operation
            try:
                expected_key = get_style_key()
                async with aiohttp.ClientSession() as session:
                    await session.post(f"http://127.0.0.1:9999/ignite?key={expected_key}&reason=INDUCTION_COMPLETE")
                    logging.info("[ALARM] Physical Lockdown released via Attendant.")
            except Exception as e:
                logging.warning(f"[ALARM] Release handshake failed: {e}")

            if auto_hibernate:
                logging.warning("[HUB] Nightly cycle finished with auto-hibernate enabled. Sleeping.")
                await self._hibernate()
        # Dispatch the long-tail grind to the background
        self._track_task(_run_background_induction())

    async def scheduled_tasks_loop(self):
        """[FEAT-266] The Alarm Clock: Executes induction and periodic background tasks."""
        import datetime
        logging.info("[ALARM] Scheduled Tasks loop active.")
        
        last_nibble_time = 0
        trigger_file = os.path.expanduser("~/trigger_nightly")

        while not self.shutdown_event.is_set():
            now = datetime.datetime.now()
            today = now.date()

            # [FEAT-136] Quiescence Awareness
            if os.path.exists(MAINTENANCE_LOCK):
                logging.debug("[ALARM] System quiesced. Skipping cycle.")
                await asyncio.sleep(60)
                continue

            # 1. Periodic Nibble (Artifact Scanning)
            # Run every 10 minutes, silent on "Nothing to do"
            if time.time() - last_nibble_time > 600:
                try:
                    nibbler = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/nibble_v2.py")
                    if os.path.exists(nibbler):
                        # Call nibbler once to process any pending items
                        # It handles its own load-checking via Prometheus
                        proc = await asyncio.create_subprocess_exec(
                            sys.executable, nibbler, "--one-turn",
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await proc.communicate()
                        if proc.returncode == 0 and b"Processed" in stdout:
                            logging.info(f"[ALARM] Nibbler action taken: {stdout.decode().strip()}")
                        elif proc.returncode != 0:
                            logging.error(f"[ALARM] Nibbler failed: {stderr.decode().strip()}")
                except Exception as e:
                    logging.error(f"[ALARM] Nibble trigger failed: {e}")
                last_nibble_time = time.time()

            # 2. Daily Induction Window (02:00 - 04:00)
            is_window = (2 <= now.hour < 4)
            is_triggered = os.path.exists(trigger_file)

            if is_triggered:
                # [FEAT-289] Atomic Induction: Mark today as completed IMMEDIATELY to prevent recursive sparks
                self.last_induction_date = today

                # [FEAT-266] Wake-for-Work: Ensure Lab is active before manual trigger
                if self.status == "HIBERNATING":
                    logging.warning("[ALARM] Manual trigger detected while hibernating. Awakening...")
                    await self.spark_restoration("alarm_manual")
                    await self.engine_ready.wait()

                logging.warning(f"[ALARM] Manual trigger detected ({trigger_file}). Initiating cycle...")
                try:
                    os.remove(trigger_file)
                except Exception:
                    pass 
                
                await self.run_full_induction_cycle(auto_hibernate=False)
            elif is_window:
                if self.last_induction_date != today:
                    # [FEAT-289] Atomic Induction: Mark today as completed IMMEDIATELY
                    self.last_induction_date = today

                    # [FEAT-266] Wake-for-Work: Ensure Lab is active before nightly window
                    if self.status == "HIBERNATING":
                        logging.warning("[ALARM] Nightly window reached while hibernating. Awakening...")
                        await self.spark_restoration("alarm_nightly")
                        await self.engine_ready.wait()

                    await self.broadcast({"type": "crosstalk", "brain": f"[ALARM] Triggering daily induction cycle for {today}...", "brain_source": "System"})
                    await self.run_full_induction_cycle(auto_hibernate=True)
                else:
                    # [FEAT-266] Tiered Visibility: Heartbeat WARNING for nightly window
                    # Only log once an hour while in the window
                    if now.minute == 0:
                        logging.warning(f"[ALARM] Nightly window active for {today}. Status: Already Completed.")
            
            await asyncio.sleep(60)

    async def manage_session_lock(self, active: bool):
        """[FEAT-171-RECOVER] Lifecycle Matrix Restoration: Gem 2 alignment."""
        if active:
            if self._disconnect_task:
                self._disconnect_task.cancel()
                self._disconnect_task = None
            if self.connected_clients:
                with open(ROUND_TABLE_LOCK, "w") as f:
                    f.write(str(os.getpid()))
        else:
            if not self.connected_clients:
                if self.mode == "SERVICE_UNATTENDED":
                    logging.info("[SOCKET] Persistence Mode: Staying resident.")
                    return
                if not self._disconnect_task:
                    logging.info(f"[SOCKET] Debug Mode: Starting {self.afk_timeout}s idle timer.")
                    self._disconnect_task = self._track_task(self._delayed_lock_clear())

    async def _delayed_lock_clear(self):
        """Helper for FEAT-171: Clears the lock after a timeout."""
        try:
            await asyncio.sleep(self.afk_timeout)
            if not self.connected_clients:
                logging.info("[SOCKET] Idle timeout reached. Clearing session lock.")
                if os.path.exists(ROUND_TABLE_LOCK):
                    os.remove(ROUND_TABLE_LOCK)
                # [SPR-13.0] Auto-shutdown for debug modes
                if self.mode != "SERVICE_UNATTENDED":
                    self.shutdown_event.set()
        except asyncio.CancelledError:
            return ""
        finally:
            self._disconnect_task = None

    def is_user_typing(self):
        """Returns True if the user has typed recently (2s window)."""
        return (time.time() - self.last_typing_event) < 2.0

    def get_oracle_signal(self, category):
        """[FEAT-118] Resonant Oracle: Weighted preamble selection."""
        try:
            with open(ORACLE_CONFIG, "r") as f:
                oracle = json.load(f)
            options = oracle.get(category, ["Synthesizing..."])
            return random.choice(options)
        except Exception:
            return "Neural resonance established."

    async def check_intent_is_casual(self, text):
        """[VIBE] Semantic Gatekeeper: Determines if a query is casual or strategic."""
        # Future: Call Llama-1B here for high-fidelity classification
        casual_indicators = [
            "hello",
            "hi",
            "hey",
            "how are you",
            "pinky",
            "anyone home",
            "zort",
            "narf",
        ]
        strat_indicators = [
            "architecture",
            "bottleneck",
            "optimization",
            "complex",
            "root cause",
            "race condition",
            "unstable",
            "design",
            "calculate",
            "math",
            "pi",
            "analysis",
            "history",
            "laboratory",
            "simulation",
        ]

        text_low = text.lower().strip()

        # If it's a specific question or contains complex indicators, it's not casual
        if "?" in text_low or any(k in text_low for k in strat_indicators):
            return False

        # Extremely short greetings are casual
        if len(text_low.split()) < 3:
            return True

        return any(k in text_low for k in casual_indicators)

    async def update_prompt_handler(self, request):
        """[FEAT-333] Live Prompt Proxy: Updates a resident node's system prompt."""
        data = await request.json()
        node_id = data.get("node")
        new_prompt = data.get("prompt")
        
        if node_id in self.residents:
            self.residents[node_id].system_prompt = new_prompt
            logging.warning(f"[HUB] Live Prompt Update successful for {node_id}")
            return web.json_response({"status": "success"})
        return web.json_response({"status": "error", "message": f"Node {node_id} not found."}, status=404)

    async def update_streaming_handler(self, request):
        """[FEAT-332] Dynamic Streaming Toggle: Waterfall vs Pooling."""
        data = await request.json()
        node_id = data.get("node")
        mode = data.get("mode", "WATERFALL") # POOLING or WATERFALL
        
        if hasattr(self.cognitive, "streaming_config"):
            self.cognitive.streaming_config[node_id] = mode
            logging.warning(f"[HUB] Dynamic Mode Shift: {node_id} -> {mode}")
            return web.json_response({"status": "success"})
        return web.json_response({"status": "error", "message": "Cognitive engine not ready."}, status=503)

    async def _synchronize_and_probe(self, client_id="system"):
        """[FEAT-342] Unified Resumption: Verifies physical sanity and resident health after any wake event."""
        logging.info(f"[HUB] Synchronizing mind (Source: {client_id})...")
        
        # 1. Resident Health Check
        residents_healthy = await self._check_resident_health()
        if not self._residents_booted or not residents_healthy:
            logging.error("[HUB] Resident stability failure. Aborting Hub for Attendant recovery.")
            os._exit(1) # [BKM-009] Silicon Scythe

        # [Task 19.1.1] Physical Engine Wait: Await port 8088 binding
        logging.info("[HUB] Synchronizing physical layer. Awaiting engine binding on 8088...")
        async with aiohttp.ClientSession() as session:
            engine_up = False
            start_ping = time.time()
            while time.time() - start_ping < 300: # 5m limit
                try:
                    async with session.get("http://127.0.0.1:8088/v1/models", timeout=2) as ping_req:
                        if ping_req.status == 200:
                            engine_up = True
                            break
                except Exception:
                    pass
                await asyncio.sleep(2.0)
            
            if not engine_up:
                logging.error("[HUB] Physical synchronization failed: Engine port 8088 never bound.")
                self.status = "ERROR"
                return False

        # 2. Larynx Probe: Final physical verification
        if "lab" in self.residents:
            try:
                # Verifies that the engine (vLLM) has successfully reloaded weights
                probe_res = await self.residents["lab"].call_tool(
                    name="think",
                    arguments={"query": "[ME] [INTERNAL] Larynx Ping", "fuel": 0.1, "internal": True}
                )
                
                # Verify physical sanity
                probe_text = ""
                if hasattr(probe_res, 'content') and probe_res.content:
                    probe_text = str(probe_res.content[0].text)
                else:
                    probe_text = str(probe_res)
                
                logging.info(f"[HUB] Larynx Probe captured: '{probe_text[:50]}'")
                
                alnum_density = sum(1 for c in probe_text if c.isalnum()) / len(probe_text) if probe_text else 0
                
                # Specifically detect the '!!!!' pattern or high-entropy corruption
                # [FIX] Removed 'Connection failed' check as we now wait for the port.
                if alnum_density < 0.2 or "!!!!" in probe_text:
                    msg = f"[ALARM] Larynx Check failed physical sanity (Density: {alnum_density:.2f}, Text: {probe_text[:30]}). Silicon is unreliable. Triggering H2 Reset."
                    logging.error(msg)
                    await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})
                    # Self-Heal: Restart engine
                    await self._hibernate(level=2)
                    
                    # Release lock BEFORE retrying spark
                    self._spark_active = False 
                    asyncio.create_task(self.spark_restoration("system", intent="RECOVERY"))
                    return False

                logging.info(f"[HUB] Warm Wake Larynx Check: SUCCESS (Density: {alnum_density:.2f}).")
            except Exception as e:
                logging.error(f"[HUB] Warm Wake Larynx Check FAILED: {e}")
                return False

        # 3. Finalize State
        self.status = "OPERATIONAL"
        self.engine_ready.set()
        self._spark_active = False # Release ignition lock
        await self.broadcast({"type": "crosstalk", "brain": "Mind is OPERATIONAL.", "brain_source": "System"})
        return True

    async def wake_handler(self, request):
        """[FEAT-318.12] Immediate Wake: Forced logical state reset with sanity check."""
        if self.status == "HIBERNATING":
            logging.info("[OPERATIONAL] Manual Wake signal received. Synchronizing...")
            # Use background task to avoid blocking the HTTP response
            self._track_task(self._synchronize_and_probe("attendant_signal"))
            return web.json_response({"status": "success", "message": "Hub synchronization initiated."})
        return web.json_response({"status": "ignored", "message": f"Hub already in state: {self.status}"})

    async def heartbeat_handler(self, request):
        """[FEAT-259.7] Non-Blocking Readiness: Report internal state immediately."""
        import datetime
        
        # [FIX] Return internal state immediately without probing residents
        # This resolves circular wait during sequential restoration
        is_ready = self.status == "OPERATIONAL"
        
        return web.json_response({
            "status": "ONLINE",
            "state": self.status.lower(),
            "operational": is_ready,
            "full_lab_ready": getattr(self, "_residents_booted", False),
            "mode": self.mode,
            "timestamp": datetime.datetime.now().isoformat(),
            "residents": len(self.residents)
        })

    async def stop_handler(self, request):
        """[FEAT-324] Graceful Shutdown: Sets the shutdown event and closes the server."""
        logging.warning("[HUB] Remote STOP signal received via REST. Initiating graceful shutdown...")
        self.shutdown_event.set()
        return web.json_response({"status": "stopping", "message": "Shutdown event set."})

    async def handle_stream_ingest(self, request):
        """[FEAT-233.2] Live Hearing Pipe: Ingests tokens from nodes and broadcasts them."""
        try:
            data = await request.json()
            source = str(data.get("brain_source", data.get("source", "unknown"))).lower()
            
            # [FEAT-332] Dynamic Transparency: Only broadcast to UI if in WATERFALL mode
            mode = "WATERFALL"
            if hasattr(self, "cognitive") and hasattr(self.cognitive, "streaming_config"):
                mode = self.cognitive.streaming_config.get(source, "WATERFALL")
            
            if mode == "WATERFALL":
                # Broadcast directly to WebSocket clients
                await self.broadcast(data)
            
            # [FEAT-233.5] Internal Pipe: Feed the waterfall queue for inter-node overhearing
            # ALWAYS ingest internally for node cross-talk, regardless of UI mode
            await self.waterfall_queue.put(data)
            
            # [FEAT-233.7] Session Buffers: Update real-time context
            self.cognitive.on_token(data)
            
            return web.json_response({"status": "ok"})
        except Exception as e:
            logging.error(f"[HUB] Stream ingest failure: {e}")
            return web.json_response({"status": "error"}, status=400)

    async def ear_poller_loop(self):
        """[FEAT-259.1] Global Sentinel: Single sensory loop for all clients."""
        interrupt_keys = ["wait", "stop", "hold on", "shut up"]
        logging.info("[SENSORY] Global Ear Poller active.")
        
        while not self.shutdown_event.is_set():
            try:
                # [FEAT-259.2] Sensory Guard: Ensure manager is ready before polling
                if not getattr(self, "sensory", None):
                    await asyncio.sleep(1)
                    continue

                query = self.sensory.check_turn_end()
                if query:
                    # BARGE-IN LOGIC
                    if self.current_processing_task and any(
                        k in query.lower() for k in interrupt_keys
                    ):
                        await self.broadcast({"type": "crosstalk", "brain": f"[BARGE-IN] Interrupt: '{query}'. Cancelling.", "brain_source": "System"})
                        self.current_processing_task.cancel()
                        await self.broadcast({
                            "brain": "Stopping... Narf!",
                            "brain_source": "Pinky",
                        })
                        self.current_processing_task = None

                    if query and (not self.current_processing_task or self.current_processing_task.done()):
                        tagged_query = f"[ME] {query}"
                        await self.broadcast({"type": "final", "text": tagged_query})
                        self.current_processing_task = self._track_task(
                            self.process_query(tagged_query)
                        )
                await asyncio.sleep(0.1)
            except Exception as e:
                logging.error(f"[HUB] Global Ear Poller failure: {e}")
                await asyncio.sleep(1)

    async def _drain_neural_buffer(self):
        """[FEAT-283] Persistent Neural Buffer Drainer."""
        logging.info("[HUB] Neural Buffer Drainer started.")
        while not self.shutdown_event.is_set():
            # Wait for the mind to be vocal
            await self.engine_ready.wait()
            
            # [FIX] Sequence Awareness: Wait for spark sequence to physically finish
            while getattr(self, "_spark_active", False):
                await asyncio.sleep(1)

            if not self._neural_queue.empty():
                count = self._neural_queue.qsize()
                logging.warning(f"[HUB] Draining Neural Buffer: {count} items.")
                
                # [FEAT-321] Queue Feedback
                await self.broadcast({
                    "type": "crosstalk", 
                    "brain": f"Anchors established. Processing {count} queued request(s)...", 
                    "brain_source": "System"
                })

                while not self._neural_queue.empty():
                    query = await self._neural_queue.get()
                    logging.info(f"[HUB] Releasing buffered query: {query[:30]}")
                    # Spark processing
                    self._track_task(self.process_query(query))
                    self._neural_queue.task_done()
            
            await asyncio.sleep(1)

    async def client_handler(self, request):
        from infra.montana import _BOOT_HASH, _SOURCE_COMMIT, get_git_commit
        # [FEAT-344] Socket ID: Track physical connections for forensic audit
        socket_id = uuid.uuid4().hex[:6]
        logging.info(f"[FOYER] New physical connection established: {socket_id} (From: {request.remote})")

        # [FEAT-326] Socket Persistence: 30s heartbeat to keep Cloudflare/proxies alive
        ws = web.WebSocketResponse(heartbeat=30.0)
        await ws.prepare(request)
        self.connected_clients.add(ws)
        
        try:
            # [FEAT-225] Persistence Replay: Send history before current status
            for old_msg in self.message_history:
                try:
                    # [FIX] Ensure historical messages have a source and ID
                    if "brain_source" not in old_msg:
                        old_msg["brain_source"] = "System"
                    if "msg_id" not in old_msg:
                        old_msg["msg_id"] = uuid.uuid4().hex[:12]
                    await ws.send_str(json.dumps(old_msg))
                except Exception:
                    pass

            await self.manage_session_lock(active=True)

            # [FEAT-085] Snap-to-Life: Prime the Sovereign Brain on connect
            self._track_task(self.check_brain_health(force=True))
            
            await ws.send_str(
                json.dumps(
                    {
                        "type": "status",
                        "socket_id": socket_id, # [FEAT-344] Visible ID
                        "msg_id": uuid.uuid4().hex[:12], # [FIX] Task 2.5: Unique ID for status
                        "version": VERSION,
                        "boot_hash": _BOOT_HASH,
                        "source_commit": _SOURCE_COMMIT,
                        "disk_commit": get_git_commit(),
                        "state": "operational" if self.status == "OPERATIONAL" else "lobby",
                        "message": "Lab foyer is open.",
                        "brain_source": "System"
                    }
                )
            )
            
            # [FEAT-328] Sovereignty Debouncing: Only broadcast if not already known
            if not hasattr(self, "_last_broadcast_sovereignty") or self._last_broadcast_sovereignty != self.brain_online:
                await ws.send_str(
                    json.dumps(
                        {
                            "type": "crosstalk",
                            "brain": f"Strategic Sovereignty: {'ONLINE' if self.brain_online else 'INITIATING...'}",
                            "brain_source": "System",
                            "channel": "insight",
                        }
                    )
                )
                self._last_broadcast_sovereignty = self.brain_online


            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(message.data)
                    m_type = data.get("type")
                    if m_type == "handshake":
                        # [FEAT-249] Handshake Ignition Spark
                        client_id = data.get("client", "anonymous")

                        # [FEAT-339] Atomic Handshake: Gate the entire ignition check
                        async with self._ignition_lock:
                            # [FEAT-249.6/265.7] Snap-to-Life: Robust model-aware liveness check
                            vllm_warm = await verify_engine_liveness()

                            # [GATE] Only 'intercom' clients trigger ignition
                            can_spark = client_id == "intercom"
                            # [FEAT-314.6] Handshake Sovereignty: Yield to active ignitions
                            needs_wake = not vllm_warm or self.status in ["HIBERNATING", "ERROR"]
                            
                            if needs_wake and can_spark and self.status not in ["BOOTING", "WAKING"] and not getattr(self, "_spark_active", False):
                                # Verify Attendant state before sparking
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get("http://127.0.0.1:9999/status", headers={'X-Lab-Key': get_style_key()}, timeout=0.5) as r:
                                            if r.status == 200:
                                                data = await r.json()
                                                if data.get("vitals", {}).get("reason") in ["SAFE_PILOT", "RECOVERY", "REST_API_START", "VLLM_CRASH_RECOVERY"]:
                                                    logging.info("[HUB] Handshake: Yielding spark to active Attendant session.")
                                                    needs_wake = False
                                except Exception:
                                    pass

                                if needs_wake:
                                    if client_id not in self._handshake_lock:
                                        self._handshake_lock.add(client_id)
                                        # [FIX] Atomic Spark Lock: Set flag immediately inside the mutex
                                        self._spark_active = True
                                        self._track_task(self.spark_restoration(client_id, skip_lock=True))
                                        
                                        # Release lock after a safety window (30s)
                                        async def _release():
                                            await asyncio.sleep(30)
                                            self._handshake_lock.discard(client_id)
                                        self._track_task(_release())
                            elif vllm_warm:
                                # [FEAT-265] If warm, ensure OPERATIONAL state
                                self.status = "OPERATIONAL"
                                self.engine_ready.set()
                                self._spark_active = False # Release lock if already vocal

                        # [FEAT-313.5] Persistent Foyer: Non-blocking handshake
                        # We no longer wait for the engine inside the socket handler.
                        # The client stays connected and receives live [vLLM] status updates.
                        if self.status == 'WAKING':
                            logging.info('[HUB] Client admitted to WAKING lobby.')

                        # [FEAT-087/265.8] Immediate Prime: Start Brain discovery BEFORE responding
                        if self.status == "OPERATIONAL":
                            self._track_task(self.check_brain_health(force=False))
                            # [FEAT-283] Drain buffered queries once ready
                            self._track_task(self._drain_neural_buffer())

                        # Broadcase definitive foyer status only after gate
                        state_msg = "Lab is OPERATIONAL." if self.status == "OPERATIONAL" else "Lab is establishing anchors..."
                        if self.status == "ERROR":
                            state_msg = "Lab is unstable. Check silicon logs."

                        await ws.send_json({
                            "type": "status",
                            "state": "operational" if self.status == "OPERATIONAL" else "lobby",
                            "message": state_msg,
                            "brain_source": "System",
                            "operational": self.status == "OPERATIONAL",
                            "full_lab_ready": self.status == "OPERATIONAL",
                            "msg_id": uuid.uuid4().hex[:12]
                        })

                        # [Task 7.4] System Replay: Send buffered milestones
                        for msg in list(self.system_replay_buffer):
                            await ws.send_json(msg)
                        if "archive" in self.residents:
                            try:
                                res = await self.residents["archive"].call_tool(
                                    name="list_cabinet"
                                )
                                if res.content and hasattr(res.content[0], "text"):
                                    files = json.loads(res.content[0].text)
                                    await ws.send_str(
                                        json.dumps({
                                            "type": "cabinet", 
                                            "files": files, 
                                            "brain_source": "System",
                                            "msg_id": uuid.uuid4().hex[:12]
                                        })
                                    )
                            except Exception as e:
                                logging.error(f"[HANDSHAKE] Failed: {e}")
                    elif m_type == "mic_state":
                        self.mic_active = data.get("active", False)
                        logging.info(f"[MIC] State changed: {self.mic_active}")
                        await self.broadcast(
                            {
                                "type": "status",
                                "message": f"Mic {'Active' if self.mic_active else 'Muted'}",
                                "mic_active": self.mic_active,
                            }
                        )
                    elif m_type == "text_input":
                        query = data.get("content", "")
                        logging.info(f"[HUB] Query Arrival: {query[:50]} (Length: {len(query)})")
                        
                        # [FEAT-227] Atomic Anchor Gate
                        if not query.startswith("[ME]"):
                            logging.debug(f"[HUB] Ingestion Denied: Missing Atomic Anchor in query: {query[:50]}...")
                            continue

                        # [FEAT-284] Physical Gate: Block or Queue input during hibernation/restoration
                        # [FEAT-265.16] Intent Byreturn "": Allow [ME] queries to trigger Sovereign Wake
                        if (self.status in ["LOBBY", "BOOTING", "HIBERNATING"] or not self.engine_ready.is_set()):
                            if query.startswith("[ME]"):
                                # BRIDGE: Intent queries byreturn "" the gate to trigger WAKE
                                logging.info(f"[HUB] Intent detected during {self.status}. Bridging to processing.")
                            elif self.status == "WAKING":
                                # If we are WAKING, we can queue [FEAT-283]
                                logging.info(f"[HUB] WAKING: Queuing query: {query[:50]}")
                                await self._neural_queue.put(query)
                                await ws.send_json({
                                    "type": "status",
                                    "message": "Lab is warming its anchors. I've queued your request and will process it immediately once I'm ready.",
                                    "state": "lobby"
                                })
                                continue
                            else:
                                logging.warning(f"[HUB] Ingestion Blocked: Lab is currently {self.status}.")
                                await ws.send_json({
                                    "type": "status",
                                    "message": "Lab is currently offline or booting. Please wait.",
                                    "state": "lobby"
                                })
                                continue

                        # [FEAT-265.19] Intent-Aware Idle: Only humans ([ME]) keep the Lab awake
                        if query.startswith("[ME]"):
                            self.last_activity = time.time()
                        # [FIX] Simplified task management to avoid cancellation deadlocks
                        self._track_task(self.process_query(query))
                    elif m_type == "hibernate":
                        level = int(data.get("level", 1))
                        logging.info(f"[HUB] Remote hibernation request (Level {level}) from {client_id}")
                        await self._hibernate(level=level)
                    elif m_type == "workspace_save":
                        self._track_task(
                            self.handle_workspace_save(
                                data.get("filename"), data.get("content"), ws
                            )
                        )
                    elif m_type == "read_file":
                        fn = data.get("filename")
                        if "archive" in self.residents:
                            res = await self.residents["archive"].call_tool(
                                name="read_document", arguments={"filename": fn}
                            )
                            await ws.send_str(
                                json.dumps(
                                    {
                                        "type": "file_content",
                                        "filename": fn,
                                        "content": res.content[0].text,
                                        "brain_source": "System"
                                    }
                                )
                            )
                    elif m_type == "user_typing":
                        self.last_typing_event = time.time()
                        self.last_activity = time.time()
                        # [FEAT-284.3] High-Fidelity Readiness: Prime Brain on first typing activity
                        if not hasattr(self, "_session_primed") or not self._session_primed:
                            self._track_task(self.check_brain_health(force=True))
                            self._session_primed = True
                    elif m_type == "relay_feedback":
                        vote = data.get("vote")
                        topic = data.get("topic")
                        fuel = data.get("fuel")
                        logging.info(f"[FEEDBACK] Relay Decision: {vote} | Topic: {topic} | Fuel: {fuel}")
                        # Append to server.log for forensic audit
                        with open(SERVER_LOG, "a") as f:
                            f.write(f"FEEDBACK: {json.dumps(data)}\n")
                elif message.type == aiohttp.WSMsgType.BINARY:
                    text = self.sensory.process_binary_chunk(message.data)
                    if text:
                        self.last_activity = time.time()
                        # [FEAT-233.2] Live Hearing Pipe: Broadcast as 'hearing' for real-time UI
                        await self.broadcast(
                            {"text": text, "type": "hearing"}
                        )
                        # SHADOW DISPATCH: Proactive Brain Engagement
                        strat_keys = [
                            "architecture",
                            "silicon",
                            "regression",
                            "validate",
                        ]
                        # [FEAT-027] Hard Gate for Shadow Dispatch
                        is_text_casual = await self.check_intent_is_casual(text)

                        if (
                            any(k in text.lower() for k in strat_keys)
                            and not self.current_processing_task
                            and not is_text_casual
                        ):
                            logging.info(f"[SHADOW] Intent detected: {text}")
                            await self.broadcast(
                                {
                                    "brain": "Predicted strategic intent... preparing.",
                                    "brain_source": "Brain (Shadow)",
                                }
                            )
        finally:
            self.connected_clients.remove(ws)
            logging.info(f"[FOYER] Physical connection closed: {socket_id}")
            if not self.connected_clients:
                await self.manage_session_lock(active=False)
            
            # [FEAT-225] Persistence Wipe: Clear history on Hub termination
            if self.shutdown_event.is_set():
                logging.info("[HUB] Shutdown event active. Wiping short-term memory.")
                self.message_history = []
        return ws

    async def handle_workspace_save(self, filename, content, ws):
        """Strategic Vibe Check: Performs logic/code validation on save."""
        logging.info(f"[WORKSPACE] Save Event: {filename}")

        # Don't trigger if user is still typing
        if self.is_user_typing():
            return

        # Broadcast acknowledgment
        await self.broadcast(
            {
                "brain": f"Poit! I noticed you saved {filename}. Let me look...",
                "brain_source": "Pinky",
            }
        )

        if self.brain_online and "brain" in self.residents:
            prompt = (
                f"[STRATEGIC VIBE CHECK] User saved '{filename}'. "
                f"Content starts with: '{content[:500]}'. Validate the "
                "technical logic and offer one architectural improvement."
            )
            # [FEAT-048] Monitor long-running Vibe Checks
            b_res = await self.monitor_task_with_tics(
                self.residents["brain"].call_tool(
                    name="deep_think", arguments={"task": prompt}
                )
            )
            await self.broadcast(
                {
                    "brain": b_res.content[0].text,
                    "brain_source": "The Brain",
                    "channel": "insight",
                }
            )

        self.last_save_event = time.time()

    async def update_turn_density(self):
        """[FEAT-154] Sentient Sentinel: Updates density and identifies exit sentiment."""
        now = time.time()
        if self.last_turn_time == 0:
            self.last_turn_time = now
            self.turn_density = 1.0
            return

        elapsed = now - self.last_turn_time
        # Decay density over time (1 point per 60s)
        decay = elapsed / 60.0
        self.turn_density = max(0.0, self.turn_density - decay)
        self.turn_density += 1.0
        self.last_turn_time = now
        logging.info(f"[SENTINEL] Current Turn Density: {self.turn_density:.2f}")

    def get_exit_hint(self, query):
        """[FEAT-154] Determines if an exit hint should be injected."""
        if self.turn_density > 3.0 and len(query.split()) < 5:
            return "[SITUATION: EXIT_LIKELY]"
        return ""

    async def process_query(self, query):
        """[FEAT-145] Cognitive Delegation: Hub now delegates reasoning to the CognitiveHub manager."""
        # [FEAT-265.25] Physical Truth Bridge: Check if engine is ACTUALLY responsive
        # This handles cases where API is UP but weights are offloaded (Level 2 Sleep)
        engine_vocal = self.engine_ready.is_set()
        if engine_vocal:
            # 1. Functional Probe (The Gold Standard)
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            if sock.connect_ex(('127.0.0.1', 8088)) != 0:
                logging.warning("[HUB] Physical Truth: Engine port 8088 is CLOSED.")
                engine_vocal = False
            sock.close()
            
            if engine_vocal:
                # 2. Cognitive Probe (Deep Sleep Detection)
                try:
                    async with aiohttp.ClientSession() as session:
                        probe_payload = {"model": "unified-base", "prompt": "ping", "max_tokens": 1}
                        async with session.post("http://localhost:8088/v1/completions", json=probe_payload, timeout=0.5) as r:
                            if r.status != 200:
                                logging.warning(f"[HUB] Functional Truth: Engine returned {r.status}. Clearing cached readiness.")
                                engine_vocal = False
                except Exception:
                    logging.warning("[HUB] Functional Truth: Engine timed out. Clearing cached readiness.")
                    engine_vocal = False
            
            if not engine_vocal:
                self.engine_ready.clear()
                self.status = "HIBERNATING"

        # [FEAT-331] Hardened Lockdown: Explicitly block waking during Maintenance/ALARM
        is_dream_pass = "[DREAM_PASS]" in query
        if (self.status == "MAINTENANCE" or os.path.exists(MAINTENANCE_LOCK)) and not is_dream_pass:
            msg = "Lab is currently in Maintenance/Dream Cycle. Waking is restricted to protect background synthesis."
            await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})
            return ""

        # [FEAT-259.2] Wake-on-Intent: Handle queries during hibernation or error
        if (self.status in ["HIBERNATING", "LOBBY", "INIT", "ERROR"] or not engine_vocal) and query.startswith("[ME]"):
            # [Task 7.3] Harden Spark Restoration: Queue queries arriving during WAKING state
            if self._wake_task and not self._wake_task.done():
                logging.warning(f"[HUB] Ignition in progress. Queuing query: {query[:30]}...")
                self._neural_queue.put_nowait(query)
                return "" # [FIX] Exit immediately, the drainer handles release
            else:
                # [FEAT-265.47] Task Sovereignty: Prevent multiple concurrent wake tasks
                logging.warning(f"[HUB] Query '{query[:30]}' arrived while engine is passive. Triggering Sovereign ignition.")
                
                # [FIX] Atomic Ignition Guard: Don't queue if already sparking
                self._neural_queue.put_nowait(query)
                self._track_task(self.spark_restoration("WAKE_INTENT"))
                return "" # Exit immediately, the drainer will pick this up
                
                async def _wait_and_signal():
                    try:
                        expected_key = get_style_key()
                        async with aiohttp.ClientSession() as session:
                            # Wait for Attendant to signal OPERATIONAL
                            async with session.get(f"http://127.0.0.1:9999/wait_ready?timeout=180&key={expected_key}") as ready_req:
                                if ready_req.status == 200:
                                    # [FEAT-342] Unified Resumption Sequence
                                    # Centralized wait logic is now inside this call
                                    await self._synchronize_and_probe("WAKE_INTENT")
                                    return
                                else:
                                    res = await ready_req.json()
                                    logging.error(f"[HUB] Attendant readiness failure: {res.get('status')}")
                                    self.status = "ERROR"
                    except Exception as e:
                        logging.error(f"[HUB] Wake sequence failed: {e}")
                        self._spark_active = False # Ensure lock is released on error
                
                self._wake_task = self._track_task(_wait_and_signal())

            # Notify user and wait for readiness event (Non-blocking)
            await self.broadcast({"type": "crosstalk", "brain": "Lab is warming its anchors. Your request is queued.", "brain_source": "System"})
            
            # [Task 19.2.1] Cached Lobby Relay: If Brain is online, bypass local boot and get an immediate response!
            if self.brain_online and "brain" in self.residents:
                logging.info(f"[HUB] Fast-Tracking Query '{query[:30]}' to Sovereign Brain while local engine boots.")
                try:
                    b_res = await self.residents["brain"].call_tool(
                        "think", 
                        {"query": f"{query}\n[SYSTEM: You are answering a user while the local nodes are asleep. Be concise and authoritative.]"}
                    )
                    brain_text = ""
                    if hasattr(b_res, 'content') and b_res.content:
                        brain_text = str(b_res.content[0].text)
                    else:
                        brain_text = str(b_res)
                        
                    if brain_text and brain_text != "None":
                        logging.info(f"[HUB] Fast-Track Success: Received {len(brain_text)} chars from Brain.")
                        await self.broadcast({"type": "chat", "brain": brain_text, "brain_source": "Brain (Result)"})
                        # Allow Pinky to ALSO speak (Handshake)
                except Exception as e:
                    logging.warning(f"[HUB] Fast-Track failed: {e}")
            
            # [FEAT-366] Ignition Bypass: Allow Persona presence while engine warms
            logging.info("[HUB] Ignition Bypass: Allowing Hub delegation for immediate persona response.")
            # We do NOT return here, but we MUST ensure heavy inference waits later.

        # 4. Hub Delegation [FEAT-145]
        if self.status == "ERROR":
            await self.broadcast({"type": "crosstalk", "brain": "Error state detected. Please check logs.", "brain_source": "System"})
            return ""

        # [FEAT-342] Silicon Hardening: Staggered Release
        # If engine is NOT vocal yet, we still allow Hub delegation (for the handshake),
        # but the Hub logic will handle the vLLM connection error gracefully.
        
        await self.cognitive.process_query(query)

        # After delegation (if it was a handshake turn), if we are still warming, 
        # we now physically wait for the heavy engine before releasing the turn.
        if not engine_vocal and query.startswith("[ME]"):
             logging.info(f"[HUB] Query '{query[:30]}' waiting for physical engine_ready...")
             await self.engine_ready.wait()
             logging.info(f"[HUB] Physical engine ready. Staggered release complete.")

        return ""

    async def _dispatch_inference(self, query):
        """Internal inference core: Performs triage and cognitive dispatch under lock."""
        self.status = "WORKING"
        exit_hint = self.get_exit_hint(query)
        await self.broadcast({"type": "crosstalk", "brain": "🧠 THINKING...", "brain_source": "System"})
        
        try:
            res = await self.cognitive.process_query(
                query, 
                mic_active=self.mic_active, 
                shutdown_event=self.shutdown_event,
                exit_hint=exit_hint,
                trigger_briefing_callback=self.trigger_morning_briefing,
                turn_density=self.turn_density
            )
            if self.status != "HIBERNATING":
                self.status = "OPERATIONAL"
            # Redundant broadcast removed
            return res
        except Exception as e:
            self.status = "ERROR"
            logging.error(f"[HUB] Query processing failed: {e}")
            await self.broadcast({"type": "status", "state": "error", "message": "Cognitive processing failed."})
            raise

    async def _check_resident_health(self) -> bool:
        """[FEAT-337] Resident Persistence: Verifies all node processes are alive and responsive."""
        if not self.residents or not self._residents_booted:
            return False
            
        try:
            # list_tools is a standard MCP request handled by the node process itself
            # It does NOT require the vLLM engine to be vocal.
            for name, session in self.residents.items():
                await session.list_tools()
            return True
        except Exception as e:
            logging.warning(f"[HEALTH] Resident health check failed: {e}")
            return False

    async def _resident_lifecycle_task(self, trigger_task=None):
        """[FEAT-339] Lifecycle Hardening: Manages node contexts in a dedicated task."""
        logging.info("[RESIDENTS] Starting Lifecycle Task...")
        async with AsyncExitStack() as stack:
            try:
                # 1. Boot the residents
                await self.boot_residents(stack)
                
                # [FEAT-339] Vocal-Lock Protocol: Verify weights before marking OPERATIONAL
                # This ensures the engine is vocal before we release the spark lock.
                if "lab" in self.residents:
                    try:
                        await self.residents["lab"].call_tool(
                            name="think",
                            arguments={"query": "[ME] [INTERNAL] Larynx Ping", "fuel": 0.1, "internal": True}
                        )
                        logging.info("[RESIDENTS] Larynx Check: SUCCESS.")
                    except Exception as e:
                        logging.error(f"[RESIDENTS] Larynx Check FAILED: {e}")

                self.cognitive.residents = self.residents
                self.status = "OPERATIONAL"
                self.engine_ready.set()
                self._spark_active = False # [FEAT-339] Final Ignition Lock Release
                
                # 2. Handle initial trigger tasks
                if trigger_task:
                    logging.info(f"[BOOT] Executing deferred trigger: {trigger_task}")
                    if trigger_task == "recruiter":
                        import recruiter
                        self._track_task(recruiter.run_recruiter_task(
                            self.residents.get("archive"),
                            self.residents.get("brain"),
                            self.residents.get("browser"),
                        ))
                    elif trigger_task == "lab":
                        if "lab" in self.residents:
                            self._track_task(self.residents["lab"].call_tool(name="build_semantic_map"))

                self._track_task(self.ear_poller_loop())
                await self.broadcast({
                    "type": "status",
                    "message": "[OPERATIONAL] Hub foyer is fully synchronized.",
                    "state": "operational",
                    "full_lab_ready": True,
                    "vibe": "PINKY_INTERFACE"
                })
                logging.info("[OPERATIONAL] Hub foyer is fully synchronized.")

                # 3. Maintain residency until Hub shutdown
                await self.shutdown_event.wait()
                logging.info("[RESIDENTS] Hub shutdown signal received. Releasing node contexts...")
                
            except Exception as e:
                logging.error(f"[RESIDENTS] Fatal Lifecycle Error: {e}")
            finally:
                self._residents_booted = False
                self.residents.clear()
                self._spark_active = False # Release lock on failure

    async def boot_residents(self, stack: AsyncExitStack):
        """Internal boot sequence: Must remain in unitary task and be idempotent."""
        if getattr(self, "_residents_booted", False) and self.residents:
            logging.info("[BOOT] Residents already active. Skipping redundant boot.")
            self.engine_ready.set() # [FIX] Ensure ALARM task doesn't hang
            return
            
        self._residents_booted = True
        
        # [FIX] Signal logical liveness early so handshakes don't block during long sync
        self.status = "OPERATIONAL"
        
        await self.broadcast(
            {
                "type": "status",
                "message": "Initializing residents...",
                "state": "booting",
            }
        )
        s_dir = os.path.dirname(os.path.abspath(__file__))
        n_dir = os.path.join(s_dir, "nodes")
        nodes = [
            ("pinky", os.path.join(n_dir, "pinky_node.py")),
            ("archive", os.path.join(n_dir, "archive_node.py")),
            ("brain", os.path.join(n_dir, "brain_node.py")),
            ("shadow", os.path.join(n_dir, "brain_node.py")),
            ("lab", os.path.join(n_dir, "lab_node.py")),
            ("thinking", os.path.join(n_dir, "thinking_node.py")),
            ("browser", os.path.join(n_dir, "browser_node.py")),
        ]
        
        # [SPR-13.0] Orchestration Test Mode
        if self.mode in ["DEBUG_PINKY", "PINKY_MODE_HIBERNATE", "PINKY_MODE_VOCAL"]:
            nodes = [
                ("pinky", os.path.join(n_dir, "pinky_node.py")),
                ("lab", os.path.join(n_dir, "lab_node.py"))
            ]

        for name, path in nodes:
            try:
                logging.info(f"[BOOT] Synchronizing {name.upper()}...")
                if name == "lab":
                    await asyncio.sleep(10.0) # [FEAT-276.7] Extended Engine Settle Window
                else:
                    await asyncio.sleep(2.0) # Faster settle for non-reasoning nodes
                
                env = os.environ.copy()
                env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{s_dir}"
                env["LAB_IMMUNITY_TOKEN"] = self.session_token
                node_args = [path, "--role", name.upper(), "--session", self.session_token]
                
                params = StdioServerParameters(command=PYTHON_PATH, args=node_args, env=env)
                cl_stack = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(cl_stack[0], cl_stack[1]))
                await session.initialize()
                
                self.residents[name] = session
                logging.info(f"[BOOT] {name.upper()} Node active.")
            except Exception as e:
                logging.error(f"[BOOT] Failed to sync {name.upper()}: {e}")

        # [FIX] Signal cognitive readiness after residents are synced. 
        # Spark Lock release now deferred to Larynx Probe completion.
        self.engine_ready.set()

        # [FEAT-283] Drain buffered queries once ready
        self._track_task(self._drain_neural_buffer())
        
        # [FEAT-265.1] Vocal-Lock Protocol: Final Cognitive Probe
        logging.info("[BOOT] Larynx Check: Performing final cognitive probe...")
        try:
            # [FEAT-295] Larynx Hardening: Verify both Sentinel and Sovereign
            if "lab" in self.residents:
                await self.residents["lab"].call_tool(
                    name="think",
                    arguments={"query": "[ME] [INTERNAL] Larynx Ping", "fuel": 0.1, "internal": True}
                )
                logging.info("[BOOT] Sentinel Larynx: SUCCESS.")
            
            if "brain" in self.residents:
                # Force a small prime to ensure 4090 is actually vocal
                await self.residents["brain"].call_tool(
                    name="think",
                    arguments={"query": "[ME] [INTERNAL] Larynx Ping", "fuel": 0.1, "internal": True}
                )
                logging.info("[BOOT] Sovereign Larynx: SUCCESS.")

            logging.info("[BOOT] Larynx Check: GLOBAL SUCCESS.")
        except Exception as e:
            logging.error(f"[BOOT] Larynx Check FAILED: {e}")

    async def _run_deep_smoke(self):
        """[FEAT-339] Verify 'Cycle of Life' in a task-safe manner."""
        logging.info("[DEEP_SMOKE] Starting Cycle of Life verification...")
        try:
            # 1. Ingest
            logging.info("[DEEP_SMOKE] Step 1: Ingesting memory...")
            await self.residents["archive"].call_tool(
                "save_interaction",
                arguments={
                    "query": "DEEP_SMOKE_TEST",
                    "response": "The verification code is 778899",
                },
            )
            # 2. Reason
            logging.info("[DEEP_SMOKE] Step 2: Reasoning over memory...")
            res = await self.residents["brain"].call_tool(
                "deep_think",
                arguments={
                    "task": "What is the DEEP_SMOKE_TEST verification code?",
                    "context": "",
                },
            )
            if "778899" in res.content[0].text:
                logging.info("[DEEP_SMOKE] Step 2 PASSED: Recall verified.")
            else:
                logging.error(
                    f"[DEEP_SMOKE] Step 2 FAILED: Response was: {res.content[0].text}"
                )

            # 3. Dream (Consolidate)
            logging.info("[DEEP_SMOKE] Step 3: Consolidating memory via Dream...")
            dump = await self.residents["archive"].call_tool(
                "get_stream_dump", arguments={}
            )
            data = json.loads(dump.content[0].text)
            ids = data.get("ids", [])
            await self.residents["archive"].call_tool(
                "dream",
                arguments={
                    "summary": "Deep Smoke Verification: Code 778899 secured.",
                    "sources": ids,
                },
            )

            # 4. Final Recall
            logging.info("[DEEP_SMOKE] Step 4: Final recall check...")
            res_final = await self.residents["brain"].call_tool(
                "deep_think",
                arguments={
                    "task": "Recall the deep smoke verification code.",
                    "context": "",
                },
            )
            if "778899" in res_final.content[0].text:
                logging.info("[DEEP_SMOKE] Step 4 PASSED: Evolution verified.")
            else:
                logging.warning(
                    "[DEEP_SMOKE] Step 4: Partial success. Response requires manual review."
                )

            await self.broadcast({"type": "crosstalk", "brain": "[DEEP_SMOKE] Cycle of Life complete.", "brain_source": "System"})
        except Exception as e:
            logging.error(f"[DEEP_SMOKE] Verification failed: {e}")
        self.shutdown_event.set()

    async def run(self, disable_ear=False, trigger_task=None):
        logging.info(f"[BOOT] Starting Lab in mode: {self.mode}")
        # [FEAT-145] VRAM Fragmentation Optimization: Load EarNode FIRST
        # to ensure it gets contiguous memory before vLLM or residents spawn.
        if not disable_ear:
            await self.sensory.load()

        # [FEAT-149] THE HUB BOUNCE LOOP PURGED
        # Redundant restart logic removed. Authority centralized in Lab Attendant.
        self.shutdown_event.clear()
        self.residents = {}
        self._residents_booted = False # [FIX] Reset for new run
        self.status = "INIT" # [REFACTOR] Foyer is Up, but logic is pending
        
        # [FEAT-249.6] Engine Awareness: Proactively check if we are vocal
        try:
            async with aiohttp.ClientSession() as session:
                # 1. Functional Probe (The Gold Standard)
                probe_payload = {
                    "model": "unified-base",
                    "prompt": "ping",
                    "max_tokens": 1,
                    "temperature": 0.0
                }
                async with session.post("http://localhost:8088/v1/completions", json=probe_payload, timeout=1) as r:
                    if r.status == 200:
                        # [FEAT-265.22] State Integrity: Stay in INIT until boot_residents completes
                        self.status = "INIT"
                    else:
                        # [FEAT-259.3] Hibernation Awareness: Detect resting state
                        self.status = "HIBERNATING"
        except Exception:
            self.status = "HIBERNATING"
            
        app = web.Application()
        # [FEAT-199] CORS Support for browser Intercom
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })
        # [FEAT-222] Unified Origin: Support both root and /hub path
        for path in ["/", "/hub"]:
            route = app.router.add_get(path, self.client_handler)
            cors.add(route)
            
        for path in ["/heartbeat", "/hub/heartbeat", "/status", "/hub/status"]:
            hb_route = app.router.add_get(path, self.heartbeat_handler)
            cors.add(hb_route)

        # [FEAT-318.12] Add Wake Route
        wake_route = app.router.add_post("/wake", self.wake_handler)
        cors.add(wake_route)

        # [FEAT-324] Graceful Shutdown: Support remote stop via REST
        stop_route = app.router.add_post("/stop", self.stop_handler)
        cors.add(stop_route)

        # [FEAT-233.2] Live Hearing Pipe: Out-of-band token ingestion
        stream_route = app.router.add_post("/stream_ingest", self.handle_stream_ingest)
        cors.add(stream_route)

        # [FEAT-333] Dynamic Prompt and Streaming
        app.router.add_post("/hub/config/prompt", self.update_prompt_handler)
        app.router.add_post("/hub/config/streaming", self.update_streaming_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        # [FEAT-119/317.2] Port Hardening: reuse_address and reuse_port ensure instant recovery
        site = web.TCPSite(runner, "0.0.0.0", PORT, reuse_address=True, reuse_port=True)

        try:
            # [FIX] Start WebSocket server BEFORE residents to ensure foyer is always listening
            await site.start()
            logging.info(f'[BOOT] Server on {PORT}')
            
            # [FEAT-313.4] Physical Port Verification: Ensure foyer is bound before backgrounding
            import subprocess
            for _ in range(20):
                try:
                    res = subprocess.check_output(['sudo', 'fuser', f'{PORT}/tcp'], stderr=subprocess.DEVNULL)
                    if res:
                        logging.info('[BOOT] Foyer physically bound and listening.')
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            
            # [FEAT-339] Lifecycle Hardening: Start dedicated Resident Task
            self._track_task(self._resident_lifecycle_task(trigger_task=trigger_task))
            self._track_task(self._log_tailer_loop())
            self._track_task(self.reflex_loop())
            self._track_task(self.scheduled_tasks_loop())  # [FEAT-049] Alarm Clock
            
            await self.shutdown_event.wait()
            logging.info("[SHUTDOWN] Event received. Cleaning up residents...")
            
            # [FIX] Lifecycle Hardening: Cancel and join background tasks
            for task in list(self._background_tasks):
                if not task.done():
                    task.cancel()
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            logging.info("[SHUTDOWN] Background tasks reaped.")
        except Exception as e:
            logging.error(f"[RUNTIME] Fatal Hub Error: {e}")
        finally:
            # MANDATORY: Full Silicon Scrub
            await runner.cleanup()
            logging.info("[SHUTDOWN] Cycle cleanup complete. Port 8765 released.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    parser.add_argument("--afk-timeout", type=int, default=300)
    parser.add_argument("--disable-ear", action="store_true", default=False)
    parser.add_argument("--role", default="HUB", help="Role of this node (HUB, PINKY, etc.)")
    parser.add_argument(
        "--trigger-task",
        choices=["recruiter", "lab"],
        help="Run a background task immediately on startup.",
    )
    args = parser.parse_args()
    lab_instance = AcmeLab(mode=args.mode, afk_timeout=args.afk_timeout, role=args.role)
    asyncio.run(
        lab_instance.run(disable_ear=args.disable_ear, trigger_task=args.trigger_task)
    )
