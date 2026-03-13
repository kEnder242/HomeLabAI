import asyncio
import json
import logging
import os
import random
import socket
import sys
import time
from typing import Dict, Set

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
VERSION = "3.8.1"  # Force-priming and Witty Preamble
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
            except Exception:
                ip = ip_hint

            return f"http://{ip}:{port}/api/tags"
    except Exception:
        pass
    return "http://localhost:11434/api/tags"


class AcmeLab:
    def __init__(self, mode="SERVICE_UNATTENDED", afk_timeout=300, role="HUB"):
        self.mode = mode
        self.afk_timeout = afk_timeout
        self.role = role
        self.status = "INIT"
        self.connected_clients: Set[web.WebSocketResponse] = set()
        self.residents: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.shutdown_event = asyncio.Event()
        self.last_activity = time.time()
        self.last_save_event = 0.0
        self.last_typing_event = 0.0  # [FEAT-052] Typing Awareness
        self.reflex_ttl = 1.0
        self.banter_backoff = 0
        self.brain_online = False
        self._last_brain_prime = 0  # [FEAT-085] Keep-alive tracking
        self.mic_active = False  # [FEAT-025] Amygdala Switch State
        self.sensory = SensoryManager(self.broadcast)
        self.cognitive = CognitiveHub(
            self.residents, 
            self.broadcast, 
            self.sensory, 
            lambda: self.brain_online,
            self.get_oracle_signal,
            self.monitor_task_with_tics
        )
        self.recent_interactions = []
        self.turn_density = 0.0  # [FEAT-154] Sentient Sentinel
        self.last_turn_time = 0.0
        self._disconnect_task = None # [FEAT-171] Idle timer task
        reclaim_logger(role)
        self.set_proc_title()

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
        if self.shutdown_event.is_set():
            return

        if message_dict.get("type") == "status":
            message_dict["version"] = VERSION

        for ws in list(self.connected_clients):
            try:
                await ws.send_str(json.dumps(message_dict))
            except Exception:
                self.connected_clients.remove(ws)

    async def trigger_morning_briefing(self, ws=None):
        """[FEAT-072] Briefs the user on recent nightly dialogue."""
        import datetime
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
                if ws:
                    await ws.send_str(json.dumps(msg))
                else:
                    await self.broadcast(msg)
            except Exception as e:
                logging.error(f"[BRIEF] Failed to trigger briefing: {e}")

    async def monitor_task_with_tics(self, coro, delay=2.5):
        """Sends state-aware tics during long reasoning tasks."""
        task = asyncio.create_task(coro)

        # Standard character tics
        base_tics = [
            "Thinking...",
            "Processing...",
            "Just a moment...",
            "Checking circuits...",
        ]

        current_delay = delay
        tic_count = 0

        while not task.done():
            try:
                done, pending = await asyncio.wait([task], timeout=current_delay)
                if task in done:
                    return task.result()

                if self.connected_clients and not self.is_user_typing():
                    # [FEAT-053] Contextual Insight: Check Brain status during wait
                    await self.check_brain_health()

                    if not self.brain_online:
                        tic_msg = "Sovereign unreachable... attempting failover."
                    elif tic_count == 0:
                        tic_msg = "Resonating weights... waking the Architect."
                    else:
                        tic_msg = random.choice(base_tics)

                    await self.broadcast(
                        {"brain": tic_msg, "brain_source": "Pinky (Lag Shield)", "is_internal": True}
                    )
                    tic_count += 1

                # Increase delay exponentially
                current_delay = min(current_delay * 1.5, 12.0)
            except Exception:
                if task.done():
                    return task.result()
        return task.result()

    async def check_brain_health(self, force=False):
        """Hardened Health Check: Perform a single-token generation probe."""
        try:
            # [FEAT-087] Dynamic Resolution: Re-check URL on every health probe
            target_url = resolve_brain_url()

            async with aiohttp.ClientSession() as session:
                # 1. First check if endpoint is reachable and get available models
                async with session.get(target_url, timeout=1.5) as r:
                    if r.status != 200:
                        self.brain_online = False
                        return
                    data = await r.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    if not models:
                        self.brain_online = False
                        return

                    # [STABILITY] Prioritize 8B class models for speed
                    preferred = [
                        "llama3.1:8b",
                        "llama3:latest",
                        "llama3:8b",
                        "dolphin-llama3:8b",
                    ]
                    probe_model = models[0]  # Default
                    for p in preferred:
                        if p in models:
                            probe_model = p
                            break

                # 2. PROBE: Single-token generation to verify availability
                # [FEAT-085] Intelligent Keep-Alive: Only perform heavy priming if connected
                # or if the Brain was previously offline, OR IF FORCED (Handshake).
                should_prime = (
                    force
                    or not self.brain_online
                    or (
                        time.time() - self._last_brain_prime > 120
                        and self.connected_clients
                    )
                )

                if should_prime:
                    p_url = target_url.replace("/api/tags", "/api/generate")
                    payload = {
                        "model": probe_model,
                        "prompt": "ping",
                        "stream": False,
                        "options": {"num_predict": 1},
                    }
                    timeout = 15 if not self.brain_online or force else 5
                    async with session.post(p_url, json=payload, timeout=timeout) as r:
                        is_ok = r.status == 200
                        if is_ok:
                            if not self.brain_online or force:
                                logging.info(
                                    f"[HEALTH] Strategic Sovereign PRIMED: {probe_model} (Force={force})"
                                )
                            self._last_brain_prime = time.time()
                        self.brain_online = is_ok
                else:
                    # Light heartbeat only
                    self.brain_online = True
        except Exception as e:
            logging.debug(f"[HEALTH] Brain probe failed: {e}")
            self.brain_online = False

    async def reflex_loop(self):
        """Background maintenance and status updates."""
        tics = ["Narf!", "Poit!", "Zort!", "Checking circuits...", "Egad!", "Trotro!"]
        while not self.shutdown_event.is_set():
            await asyncio.sleep(self.reflex_ttl)
            if self.connected_clients:
                await self.broadcast(
                    {
                        "type": "status",
                        "state": "ready" if self.status == "READY" else "booting",
                        "brain_online": self.brain_online,
                    }
                )
                # [FEAT-039] Banter Decay: Slow down reflexes when idle (> 60s)
                idle_time = time.time() - self.last_activity
                if idle_time > 60:
                    if self.banter_backoff < 10:  # Cap at 6s interval (1.0 + 10*0.5)
                        self.banter_backoff += 1

                    # [FEAT-047] Reflex Tics: Occasionally bubble up a character tic
                    # Only if idle for > 60s, not typing, and low probability (approx every 2 mins @ 6s interval)
                    if not self.is_user_typing() and random.random() < 0.05:
                        await self.broadcast(
                            {
                                "brain": random.choice(tics),
                                "brain_source": "Pinky (Reflex)",
                            }
                        )
                else:
                    self.banter_backoff = 0

                self.reflex_ttl = 1.0 + (self.banter_backoff * 0.5)
                # Ensure we check health at least every 5s if active
                if self.reflex_ttl > 5.0:
                    self.reflex_ttl = 5.0

                # [FEAT-085] Check health inside reflex ONLY if clients are active
                await self.check_brain_health()
            else:
                # If no clients, reset TTL and wait patiently
                self.reflex_ttl = 10.0
                # Still check health occasionally to keep status.json accurate
                await self.check_brain_health()

    async def scheduled_tasks_loop(self):
        """The Alarm Clock: Runs scheduled jobs like the Nightly Recruiter."""
        import datetime

        logging.info("[ALARM] Scheduled Tasks loop active.")
        while not self.shutdown_event.is_set():
            now = datetime.datetime.now()
            # 02:00 AM: Nightly Recruiter
            if now.hour == 2 and now.minute == 0:
                logging.info("[ALARM] Triggering Nightly Recruiter...")
                a_node = self.residents.get("archive")
                b_node = self.residents.get("brain")
                br_node = self.residents.get("browser")
                try:
                    await recruiter.run_recruiter_task(a_node, b_node, br_node)
                except Exception as e:
                    logging.error(f"[ALARM] Recruiter Task failed: {e}")
                await asyncio.sleep(61)

            # 03:00 AM: Hierarchy Refactor (The Architect)
            if now.hour == 3 and now.minute == 0:
                if "architect" in self.residents:
                    logging.info("[ALARM] Triggering Hierarchy Refactor...")
                    try:
                        await self.residents["architect"].call_tool(
                            name="build_semantic_map"
                        )
                    except Exception as e:
                        logging.error(f"[ALARM] Architect Task failed: {e}")
                await asyncio.sleep(61)

            # 04:00 AM: Nightly Dialogue [FEAT-071]
            if now.hour == 4 and now.minute == 0:
                logging.info("[ALARM] Triggering Nightly Dialogue...")
                a_node = self.residents.get("archive")
                p_node = self.residents.get("pinky")
                b_node = self.residents.get("brain")
                try:
                    from internal_debate import run_nightly_talk

                    await run_nightly_talk(a_node, p_node, b_node)
                except Exception as e:
                    logging.error(f"[ALARM] Nightly Dialogue failed: {e}")
                await asyncio.sleep(61)

            await asyncio.sleep(30)

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
                    self._disconnect_task = asyncio.create_task(self._delayed_lock_clear())

    async def _delayed_lock_clear(self):
        """Helper for FEAT-171: Clears the lock after a timeout."""
        try:
            await asyncio.sleep(self.afk_timeout)
            if not self.connected_clients:
                logging.info("[SOCKET] Idle timeout reached. Clearing session lock.")
                if os.path.exists(ROUND_TABLE_LOCK):
                    os.remove(ROUND_TABLE_LOCK)
        except asyncio.CancelledError:
            pass
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

    async def client_handler(self, request):
        from infra.montana import _BOOT_HASH, _SOURCE_COMMIT, get_git_commit
        logging.info(f"[SOCKET] New client connection request from {request.remote}")
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connected_clients.add(ws)
        await self.manage_session_lock(active=True)
        current_processing_task = None

        try:
            await ws.send_str(
                json.dumps(
                    {
                        "type": "status",
                        "version": VERSION,
                        "boot_hash": _BOOT_HASH,
                        "source_commit": _SOURCE_COMMIT,
                        "disk_commit": get_git_commit(),
                        "state": "ready" if self.status == "READY" else "lobby",
                        "message": "Lab foyer is open.",
                    }
                )
            )
            
            # [FEAT-026] Initial Brain Status Feedback
            await ws.send_str(
                json.dumps(
                    {
                        "brain": f"Strategic Sovereignty: {'ONLINE' if self.brain_online else 'INITIATING...'}",
                        "brain_source": "System",
                        "channel": "insight",
                    }
                )
            )

            async def ear_poller():
                nonlocal current_processing_task
                while not ws.closed:
                    query = self.sensory.check_turn_end()
                    if query:
                        # BARGE-IN LOGIC
                        interrupt_keys = ["wait", "stop", "hold on", "shut up"]
                        if current_processing_task and any(
                            k in query.lower() for k in interrupt_keys
                        ):
                            logging.info(
                                f"[BARGE-IN] Interrupt: '{query}'. Cancelling."
                            )
                            current_processing_task.cancel()
                            await self.broadcast(
                                {
                                    "brain": "Stopping... Narf!",
                                    "brain_source": "Pinky",
                                }
                            )
                            current_processing_task = None

                        if (
                            not current_processing_task
                            or current_processing_task.done()
                        ):
                            await self.broadcast({"type": "final", "text": query})
                            current_processing_task = asyncio.create_task(
                                self.process_query(query, ws)
                            )
                    await asyncio.sleep(0.1)

            asyncio.create_task(ear_poller())
            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(message.data)
                    m_type = data.get("type")
                    if m_type == "handshake":
                        # [FEAT-087] Intelligent Handshake Priming: FORCE model loading
                        await ws.send_str(
                            json.dumps(
                                {
                                    "brain": "Priming Brain...",
                                    "brain_source": "System",
                                    "channel": "insight",
                                }
                            )
                        )
                        asyncio.create_task(self.check_brain_health(force=True))

                        if "archive" in self.residents:
                            try:
                                res = await self.residents["archive"].call_tool(
                                    name="list_cabinet"
                                )
                                if res.content and hasattr(res.content[0], "text"):
                                    files = json.loads(res.content[0].text)
                                    await ws.send_str(
                                        json.dumps({"type": "cabinet", "files": files})
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
                        self.last_activity = time.time()
                        if (
                            current_processing_task
                            and not current_processing_task.done()
                        ):
                            current_processing_task.cancel()
                        current_processing_task = asyncio.create_task(
                            self.process_query(query, ws)
                        )
                    elif m_type == "workspace_save":
                        asyncio.create_task(
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
                                    }
                                )
                            )
                    elif m_type == "user_typing":
                        self.last_typing_event = time.time()
                        self.last_activity = time.time()
                elif message.type == aiohttp.WSMsgType.BINARY:
                    text = self.sensory.process_binary_chunk(message.data)
                    if text:
                        self.last_activity = time.time()
                        await self.broadcast(
                            {"text": text, "type": "transcription"}
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
                            and not current_processing_task
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
            if not self.connected_clients:
                await self.manage_session_lock(active=False)
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
        self.last_activity = time.time()

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

    async def process_query(self, query, websocket):
        """[FEAT-145] Cognitive Delegation: Hub now delegates reasoning to the CognitiveHub manager."""
        await self.update_turn_density()
        exit_hint = self.get_exit_hint(query)

        return await self.cognitive.process_query(
            query, 
            mic_active=self.mic_active, 
            shutdown_event=self.shutdown_event,
            exit_hint=exit_hint,
            trigger_briefing_callback=lambda: self.trigger_morning_briefing(websocket),
            turn_density=self.turn_density
        )

    async def boot_residents(self, stack: AsyncExitStack):
        """Internal boot sequence: Must remain in unitary task."""
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
            ("archive", os.path.join(n_dir, "archive_node.py")),
            ("brain", os.path.join(n_dir, "brain_node.py")),
            ("pinky", os.path.join(n_dir, "pinky_node.py")),
            ("architect", os.path.join(n_dir, "architect_node.py")),
            ("browser", os.path.join(n_dir, "browser_node.py")),
        ]

        for name, path in nodes:
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{s_dir}"

                # [FIX] vLLM legacy removed to allow clean Ollama/Generic fallback
                env["USE_BRAIN_VLLM"] = "0"
                env["BRAIN_MODEL"] = os.environ.get("BRAIN_MODEL", "MEDIUM")
                env["PINKY_MODEL"] = os.environ.get("PINKY_MODEL", "MEDIUM")

                params = StdioServerParameters(
                    command=PYTHON_PATH, args=[path, "--role", name.upper()], env=env
                )
                cl_stack = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(
                    ClientSession(cl_stack[0], cl_stack[1])
                )
                await session.initialize()
                
                # [FEAT-165] Resident Handshake Gate: Verify engine link before proceeding
                try:
                    # Probe the node's internal engine cache/connection
                    # Most nodes have a way to check this or we can fire a dummy tool call
                    await asyncio.wait_for(session.list_tools(), timeout=10.0)
                    self.residents[name] = session
                    logging.info(f"[BOOT] {name.upper()} online and verified.")
                except Exception as e:
                    logging.error(f"[BOOT] {name.upper()} failed engine handshake: {e}")
                    # We don't block boot, but we log the failure clearly
                    self.residents[name] = session

            except Exception as e:
                logging.error(f"[BOOT] Failed to load {name}: {e}")

        self.status = "READY"
        logging.info("[READY] Lab is Open.")
        sys.stderr.flush()  # Ensure signal is written to the log file
        await self.broadcast(
            {
                "type": "status",
                "message": "Mind is ONLINE. Lab is Open.",
                "state": "ready",
            }
        )
        if self.mode == "DEBUG_SMOKE":
            logging.info("[SMOKE] Successful load. Self-terminating.")
            self.shutdown_event.set()
        elif self.mode == "DEEP_SMOKE":
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

                logging.info("[DEEP_SMOKE] Cycle of Life complete.")
            except Exception as e:
                logging.error(f"[DEEP_SMOKE] Verification failed: {e}")
            self.shutdown_event.set()

    async def run(self, disable_ear=False, trigger_task=None):
        # [FEAT-145] VRAM Fragmentation Optimization: Load EarNode FIRST
        # to ensure it gets contiguous memory before vLLM or residents spawn.
        if not disable_ear:
            await self.sensory.load()

        while True:
            # [FEAT-149] The SML/Unity Persistence Loop
            # Allows the Lab to "Bounce" (re-initialize residents) on shutdown signals.
            self.shutdown_event.clear()
            self.residents = {}
            self.status = "BOOTING"

            app = web.Application()
            
            # [FEAT-199] CORS Support for browser Intercom
            cors = aiohttp_cors.setup(app, defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                )
            })
            
            route = app.router.add_get("/", self.client_handler)
            cors.add(route)
            
            runner = web.AppRunner(app)
            await runner.setup()
            # [FEAT-119] reuse_address=True allows reclaiming port from sockets in TIME_WAIT
            site = web.TCPSite(runner, "0.0.0.0", PORT, reuse_address=True)

            try:
                async with AsyncExitStack() as stack:
                    await site.start()
                    logging.info(f"[BOOT] Server on {PORT}")
                    await self.boot_residents(stack)

                    # [FEAT-145] Cognitive Delegation: Update hub with live residents
                    self.cognitive.residents = self.residents

                    # [FEAT-055] Manual Task Trigger for 'Fast Alarm' testing
                    if trigger_task:
                        logging.info(f"[BOOT] Manual Task Trigger: {trigger_task}")
                        if trigger_task == "recruiter":
                            import recruiter

                            asyncio.create_task(
                                recruiter.run_recruiter_task(
                                    self.residents.get("archive"),
                                    self.residents.get("brain"),
                                    self.residents.get("browser"),
                                )
                            )
                        elif trigger_task == "architect":
                            if "architect" in self.residents:
                                asyncio.create_task(
                                    self.residents["architect"].call_tool(
                                        name="build_semantic_map"
                                    )
                                )

                    asyncio.create_task(self.reflex_loop())
                    asyncio.create_task(
                        self.scheduled_tasks_loop()
                    )  # [FEAT-049] Alarm Clock
                    
                    await self.shutdown_event.wait()
                    logging.info("[SHUTDOWN] Event received. Cleaning up residents...")
            except Exception as e:
                logging.error(f"[RUNTIME] Fatal Hub Error: {e}")
                if self.mode != "SERVICE_UNATTENDED":
                    break
                await asyncio.sleep(5.0) # Backoff before retry
            finally:
                # MANDATORY: Full Silicon Scrub
                # AsyncExitStack handles the closing of residents automatically here
                await runner.cleanup()
                logging.info("[SHUTDOWN] Cycle cleanup complete. Port 8765 released.")

            # Exit logic for co-pilot/debug modes
            if self.mode != "SERVICE_UNATTENDED":
                logging.info(f"[SHUTDOWN] Mode '{self.mode}' is terminal. Exiting.")
                break
            
            logging.info(f"[BOUNCE] Mode '{self.mode}' active. Restarting Lab in 2 seconds...")
            await asyncio.sleep(2.0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    parser.add_argument("--afk-timeout", type=int, default=300)
    parser.add_argument("--disable-ear", action="store_true", default=False)
    parser.add_argument("--role", default="HUB", help="Role of this node (HUB, PINKY, etc.)")
    parser.add_argument(
        "--trigger-task",
        choices=["recruiter", "architect"],
        help="Run a background task immediately on startup.",
    )
    args = parser.parse_args()
    lab_instance = AcmeLab(mode=args.mode, afk_timeout=args.afk_timeout, role=args.role)
    asyncio.run(
        lab_instance.run(disable_ear=args.disable_ear, trigger_task=args.trigger_task)
    )
