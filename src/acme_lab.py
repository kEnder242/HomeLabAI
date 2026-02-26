import asyncio
import json
import logging
import os
import random
import re
import socket
import sys
import time
import uuid
import subprocess
from typing import Dict, Set

import aiohttp
import numpy as np
from aiohttp import web
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# Internal Task Imports
import recruiter
import internal_debate

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


_logger_initialized = False


# --- THE MONTANA PROTOCOL ---
_BOOT_HASH = uuid.uuid4().hex[:4].upper()

def get_git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], 
                                        cwd=LAB_DIR, text=True).strip()
    except Exception:
        return "unknown"

_SOURCE_COMMIT = get_git_commit()

def get_fingerprint(role="HUB"):
    return f"[{_BOOT_HASH}:{get_git_commit()}:{role}]"

def reclaim_logger(role="HUB"):
    global _logger_initialized
    if _logger_initialized:
        return

    root = logging.getLogger()
    # Aggressively clear all existing handlers to prevent double-logging
    # and ensure only OUR formatted handlers remain.
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # [FEAT-121] Lab Fingerprint Injection
    fmt = logging.Formatter(f"%(asctime)s - {get_fingerprint(role)} %(levelname)s - %(message)s")

    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    fh = logging.FileHandler(SERVER_LOG, mode="a", delay=False)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    root.setLevel(logging.INFO)
    logging.getLogger("nemo").setLevel(logging.ERROR)
    logging.getLogger("chromadb").setLevel(logging.ERROR)
    logging.getLogger("onelogger").setLevel(logging.ERROR)

    _logger_initialized = True


class EarNode:
    """Stub for sensory input. NeMo imported via equipment/ear_node.py."""

    def __init__(self):
        self.is_listening = True

    def check_turn_end(self):
        return None

    def process_audio(self, chunk):
        return None


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
        self.ear = None
        self.recent_interactions = []
        reclaim_logger(role)
        self.set_proc_title()

    def set_proc_title(self):
        """[FEAT-122] Kernel-Level Visibility: Renames process in ps/htop."""
        title = f"acme_lab [{_BOOT_HASH}:{get_git_commit()}:{self.role}]"
        try:
            import setproctitle
            setproctitle.setproctitle(title)
        except ImportError:
            # Fallback: Overwrite sys.argv
            sys.argv[0] = title
        logging.info(f"[BOOT] Fingerprint established: {get_fingerprint(self.role)}")

    def load_ear(self):
        """Lazy load real EarNode logic."""
        try:
            s_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.append(os.path.join(s_dir, "equipment"))
            from ear_node import EarNode

            self.ear = EarNode()
            logging.info("[BOOT] EarNode initialized (NeMo).")
        except Exception as e:
            logging.error(f"[BOOT] Failed to load EarNode: {e}")

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

    async def trigger_morning_briefing(self, ws):
        """[FEAT-072] Checks for recent nightly dialogue and briefs the user."""
        import datetime

        if os.path.exists(NIGHTLY_DIALOGUE_FILE):
            try:
                with open(NIGHTLY_DIALOGUE_FILE, "r") as f:
                    data = json.load(f)

                # Only brief if it's from 'today'
                diag_date = data.get("timestamp", "").split(" ")[0]
                today = datetime.datetime.now().strftime("%Y-%m-%d")

                if diag_date == today:
                    content = data.get("content", "")
                    # Clean up formatting for briefing
                    summary = content[:250].replace("\n", " ")
                    await ws.send_str(
                        json.dumps(
                            {
                                "brain": f"While you were out, we discussed: {summary}...",
                                "brain_source": "Pinky",
                                "channel": "chat",
                            }
                        )
                    )
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
                        {"brain": tic_msg, "brain_source": "Pinky (Reflex)"}
                    )
                    tic_count += 1

                # Increase delay exponentially
                current_delay = min(current_delay * 1.5, 8.0)
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
                try:
                    await recruiter.run_recruiter_task(a_node, b_node)
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
        try:
            if active:
                with open(ROUND_TABLE_LOCK, "w") as f:
                    f.write(str(os.getpid()))
            else:
                if os.path.exists(ROUND_TABLE_LOCK):
                    os.remove(ROUND_TABLE_LOCK)
        except Exception:
            pass

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
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connected_clients.add(ws)
        await self.manage_session_lock(active=True)
        audio_buffer = np.zeros(0, dtype=np.int16)
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

            # [FEAT-072] Morning Briefing
            asyncio.create_task(self.trigger_morning_briefing(ws))

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
                    if self.ear:
                        query = self.ear.check_turn_end()
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
                elif message.type == aiohttp.WSMsgType.BINARY and self.ear:
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    if np.abs(chunk).max() > 500 and random.random() < 0.05:
                        logging.info("[AUDIO] Signal detected.")
                    if len(audio_buffer) >= 24000:
                        text = self.ear.process_audio(audio_buffer[:24000])
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
                        audio_buffer = audio_buffer[16000:]
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

    async def process_query(self, query, websocket):
        # [FEAT-018] Interaction Logging: Ensuring user inputs are permanently captured
        logging.info(f"[USER] Intercom Query: {query}")
        logging.info(f"[DEBUG] Processing query for year-scanner: '{query}'")

        # [VIBE] Intent State
        is_strategic = False
        historical_context = ""
        historical_sources = []

        # [FEAT-088/123/124] The Local Truth Sentry
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        silence_mode = False
        if year_match and "archive" in self.residents:
            is_strategic = True
            year = year_match.group(1)
            logging.info(f"[AMYGDALA] detected {year}. Priming archive recall.")
            try:
                res_context = await self.residents["archive"].call_tool(
                    name="get_context",
                    arguments={"query": f"Validation events from {year}"},
                )
                rag_data = json.loads(res_context.content[0].text)
                raw_history = rag_data.get("text", "")
                historical_sources = rag_data.get("sources", [])

                if not raw_history:
                    logging.info(f"[SENTRY] Total Archive Silence for {year}. Engaging Local Shadow.")
                    silence_mode = True
                    historical_context = (
                        f"TOTAL ARCHIVE SILENCE: There are NO verified technical records for the year {year}. "
                        "MANDATE: As the Systems Architect, report that the archives for this period are empty "
                        "and that no specific projects or telemetry can be verified without manual artifacts."
                    )
                else:
                    historical_context = (
                        f"STRICT GROUNDING MANDATE: Use ONLY the following verified technical truth for the year {year}. "
                        "STRICT: DO NOT invent scenarios, drone swarms, or projects not listed below.\n"
                        f"--- VERIFIED LOGS [{year}] ---\n{raw_history}"
                    )
                
                if historical_sources:
                    logging.info(f"[HISTORY] Found truth anchors for {year}: {historical_sources}")
            except Exception as e:
                logging.error(f"[AMYGDALA] Recall failed: {e}")

        # [FEAT-056] MIB Memory Wipe Mechanic
        # Allows user to manually clear the interaction context (The "Neuralyzer")
        wipe_keys = ["look at the light", "wipe memory", "neuralyzer", "clear context"]
        if any(k in query.lower() for k in wipe_keys):
            self.recent_interactions = []
            logging.info("[MEMORY] MIB Wipe triggered. Context cleared.")
            await self.broadcast(
                {
                    "brain": "Look at the light... *FLASH* ... Narf! What were we talking about?",
                    "brain_source": "Pinky",
                    "type": "memory_clear",
                }
            )
            return

        is_casual = await self.check_intent_is_casual(query)

        # [DEBUG] Persona Bleed Investigation
        logging.info(f"[DEBUG] query='{query}' is_casual={is_casual}")

        # 0. HEURISTIC SENTINEL
        shutdown_keys = ["close the lab", "goodnight", "shutdown", "exit lab"]
        if any(k in query.lower() for k in shutdown_keys):
            logging.info("[SHUTDOWN] Heuristic Triggered.")
            await self.broadcast(
                {
                    "brain": "Goodnight. Closing Lab.",
                    "brain_source": "System",
                    "type": "shutdown",
                }
            )
            self.shutdown_event.set()
            return

        # 1. Strategic Sentinel Logic
        strat_keys = [
            "bottleneck",
            "optimization",
            "complex",
            "root cause",
            "race condition",
            "unstable",
            "design",
            "calculate",
        ]

        # [FEAT-032] Amygdala Logic: Use 1B model as smart filter when typing
        # If not already elevated by Amygdala, check sentinels
        if not is_strategic:
            if self.mic_active:
                # Voice Mode: Use keyword-based sentinel for speed
                is_strategic = (
                    any(k in query.lower() for k in strat_keys) and not is_casual
                )
        else:
            # Typing Mode: Use Amygdala (1B) to filter
            if not is_casual:
                logging.info("[AMYGDALA] Filtering query...")
                is_strategic = True  # Future: Call Llama-1B to decide

        addressed_brain = "brain" in query.lower()

        async def execute_dispatch(
            raw_text, source, context_flags=None, oracle_category=None, sources=None
        ):
            """Hardened Priority Dispatcher with Hallucination Shunt and [FEAT-110] Banter Sanitizer."""
            nonlocal historical_context, historical_sources
            logging.info(
                f"[DEBUG] Dispatch: source='{source}' text='{raw_text[:30]}...'"
            )

            # [FEAT-110] Shadow Moat: Strip Pinky-isms from Brain sources
            if "Brain" in source:
                # Case-insensitive removal of common interjections and roleplay banter
                banter_pattern = r"\b(narf|poit|zort|egad|trotro)\b"
                raw_text = re.sub(
                    banter_pattern, "", raw_text, flags=re.IGNORECASE
                ).strip()
                # Strip leading commas/periods/quotes/spaces left behind by sanitization
                raw_text = re.sub(r"^[,\.\!\?\s\"\'\d]+", "", raw_text).strip()
                # Also strip any roleplay actions like *adjusts goggles*
                raw_text = re.sub(r"\*[^*]+\*", "", raw_text).strip()

            # [FEAT-026] Brain Voice Restoration: Force raw text for Architect
            if source == "Brain" and "{" not in raw_text:
                # [FEAT-120] Ensure metadata is included even in direct raw text dispatch
                await self.broadcast(
                    {
                        "brain": raw_text,
                        "brain_source": "Brain",
                        "oracle_category": oracle_category,
                        "sources": sources or historical_sources,
                    }
                )
                return True

            try:
                # Recursive JSON extraction
                data = json.loads(raw_text) if "{" in raw_text else raw_text
                tool = data.get("tool") if isinstance(data, dict) else None
                params = data.get("parameters", {}) if isinstance(data, dict) else {}

                is_shutdown = (
                    tool == "close_lab"
                    or "close_lab()" in raw_text
                    or "goodnight" in raw_text.lower()
                )
                if is_shutdown:
                    await self.broadcast(
                        {
                            "brain": "Goodnight. Closing Lab.",
                            "brain_source": "System",
                            "type": "shutdown",
                        }
                    )
                    self.shutdown_event.set()
                    return True

                # Validation: Shunt hallucinations to Pinky
                known_tools = [
                    "reply_to_user",
                    "ask_brain",
                    "deep_think",
                    "list_cabinet",
                    "read_document",
                    "peek_related_notes",
                    "write_draft",
                    "generate_bkm",
                    "build_semantic_map",
                    "peek_strategic_map",
                    "discuss_offline",
                    "select_file",
                    "notify_file_open",
                ]

                # [FEAT-074] Workbench Routing
                if tool == "select_file":
                    fname = params.get("filename")
                    await self.broadcast(
                        {"type": "file_content_request", "filename": fname}
                    )
                    return True

                if tool == "discuss_offline":
                    topic = params.get("topic") or query
                    logging.info(f"[DEBATE] User requested offline discussion: {topic}")
                    await self.broadcast(
                        {
                            "brain": f"Narf! We'll chew on '{topic}' while you're out!",
                            "brain_source": "Pinky",
                        }
                    )
                    # Run in background without blocking interaction
                    asyncio.create_task(
                        internal_debate.run_nightly_talk(
                            self.residents.get("archive"),
                            self.residents.get("pinky"),
                            self.residents.get("brain"),
                            topic=topic,
                        )
                    )
                    return True

                if tool and tool not in known_tools:
                    logging.warning(f"[SHUNT] Hallucinated tool '{tool}'.")
                    if "pinky" in self.residents:
                        res = await self.residents["pinky"].call_tool(
                            name="facilitate",
                            arguments={
                                "query": f"I tried to use '{tool}' but it failed.",
                                "context": "",
                            },
                        )
                        return await execute_dispatch(
                            res.content[0].text, "Pinky (Shunt)"
                        )

                if tool == "reply_to_user" or (
                    isinstance(data, dict) and "reply_to_user" in data
                ):
                    reply = params.get("text") or data.get("reply_to_user") or raw_text
                    if isinstance(reply, dict):
                        reply = reply.get("text", str(reply))
                    if isinstance(reply, list) and len(reply) == 1:
                        reply = reply[0]

                    # [FEAT-058] Redundant Routing: Force insight channel for all Brain sources
                    target_channel = (
                        context_flags.get("channel", "chat")
                        if context_flags
                        else "chat"
                    )
                    if "Brain" in source:
                        target_channel = "insight"

                    await self.broadcast(
                        {
                            "brain": str(reply),
                            "brain_source": source,
                            "channel": target_channel,
                            "oracle_category": oracle_category,
                            "sources": sources or historical_sources,
                        }
                    )
                    return True

                if tool == "ask_brain" or tool == "deep_think":
                    task = params.get("task") or params.get("query") or query

                    # [FEAT-027] Iron Gate: Double-check for casualness in both original and delegated task
                    is_task_casual = await self.check_intent_is_casual(task)
                    if is_casual or is_task_casual:
                        logging.warning(
                            f"[GATE] Blocking casual delegation. Task: '{task}'"
                        )
                        # Fallback: Just let Pinky answer naturally
                        return False

                    # Scrub 'Pinky' from Brain's task to prevent persona bleed
                    task = task.replace("Pinky", "the Gateway")
                    task = f"[DELEGATED]: {task}"

                    if context_flags and context_flags.get("direct"):
                        task = f"[DIRECT ADDRESS] {task}"

                    # Bicameral Failover: Reroute to local if Sovereign is offline
                    target_node = "brain" if self.brain_online else "pinky"
                    if not self.brain_online:
                        logging.warning(
                            "[FAILOVER] Sovereign offline. Rerouting to Shadow Hemisphere."
                        )
                        task = f"[FAILOVER ARCHITECT]: {task}"

                    # [FEAT-088] Ground task in historical truth
                    logging.info(
                        f"[DEBUG] Injection path: historical_context len={len(historical_context)}"
                    )
                    if historical_context:
                        task = f"[HISTORICAL CONTEXT]: {historical_context}\n[TASK]: {task}"

                    # [FEAT-057] Deep Context: Send full interaction history instead of sliced window
                    if target_node in self.residents:
                        ctx = "\n".join(self.recent_interactions)
                        t_name = (
                            "deep_think" if target_node == "brain" else "facilitate"
                        )
                        t_args = (
                            {"task": task, "context": ctx}
                            if target_node == "brain"
                            else {"query": task, "context": ctx}
                        )

                        # [FEAT-048] Monitor long-running Brain tasks
                        # [FEAT-120] Pass metadata for Trace auditability
                        if "metadata" not in t_args:
                            t_args["metadata"] = {
                                "sources": sources or historical_sources,
                                "oracle_category": oracle_category,
                            }
                        res = await self.monitor_task_with_tics(
                            self.residents[target_node].call_tool(
                                name=t_name, arguments=t_args
                            )
                        )
                        raw_out = res.content[0].text

                        # [FEAT-077] Quality-Gate Failover: Handle empty/dotted remote responses
                        if (
                            raw_out == "INTERNAL_QUALITY_FALLBACK"
                            and target_node == "brain"
                        ):
                            logging.warning(
                                "[FAILOVER] Sovereign returned low-quality response. Engaging Shadow."
                            )
                            task = f"[QUALITY FAILOVER]: {task}"
                            res = await self.monitor_task_with_tics(
                                self.residents["pinky"].call_tool(
                                    name="facilitate",
                                    arguments={"query": task, "context": ctx},
                                )
                            )
                            return await execute_dispatch(
                                res.content[0].text,
                                "Brain (Shadow)",
                                {"direct": addressed_brain, "channel": "insight"},
                            )

                        return await execute_dispatch(
                            raw_out,
                            "Brain" if self.brain_online else "Brain (Shadow)",
                            {"direct": addressed_brain, "channel": "insight"},
                            sources=historical_sources,
                        )
                    else:
                        await self.broadcast(
                            {
                                "brain": "Analytical primary is OFFLINE.",
                                "brain_source": "System",
                                "channel": "insight",
                            }
                        )
                        return False

                t_node = "pinky"
                a_tools = [
                    "list_cabinet",
                    "read_document",
                    "peek_related_notes",
                    "write_draft",
                ]
                if tool in a_tools:
                    t_node = "archive"
                elif tool in ["generate_bkm", "build_semantic_map"]:
                    t_node = "architect"

                if tool and t_node in self.residents:
                    logging.info(f"[DISPATCH] {t_node}.{tool}")
                    res = await self.residents[t_node].call_tool(
                        name=tool, arguments=params
                    )
                    return await execute_dispatch(res.content[0].text, source)

                # Extraction Fallback
                def extract_val(obj):
                    if isinstance(obj, str):
                        return [obj]
                    if isinstance(obj, dict):
                        return [str(v) for v in obj.values()]
                    if isinstance(obj, list):
                        r = []
                        for v in obj:
                            r.extend(extract_val(v))
                        return r
                    return [str(obj)]

                vals = extract_val(data)
                reply = vals[0] if len(vals) == 1 else " ".join(vals)
                await self.broadcast({"brain": reply, "brain_source": source})
                return True

            except Exception as e:
                logging.error(f"[DISPATCH] Error: {e}")
                await self.broadcast({"brain": raw_text, "brain_source": source})
                return False

        # 2. Parallel Dispatch
        # Use a dict to map tasks back to their source node reliably
        dispatch_map = {}

        # [FEAT-108] Dynamic Shunt Hint
        pinky_context = ""
        if is_strategic and self.brain_online:
            pinky_context = "[STRATEGIC_SHUNT] Reasoning delegated to Sovereign. Action: Provide high-fidelity coordination filler and technical acknowledgment. Do NOT attempt derivation."

        if "pinky" in self.residents:
            t_pinky = asyncio.create_task(
                self.residents["pinky"].call_tool(
                    name="facilitate",
                    arguments={"query": query, "context": pinky_context},
                )
            )
            dispatch_map[t_pinky] = "Pinky"

        # [FEAT-086/124] Tiered Thinking: Engage Brain based on strategy vs. casual address
        should_engage_brain = "brain" in self.residents and (
            is_strategic or addressed_brain
        )

        if should_engage_brain:
            # [FEAT-124] Local Redirect for Silence Mode
            if silence_mode:
                logging.info("[SENTRY] Bypassing Remote Sovereign for Archive Silence.")
                await self.broadcast(
                    {
                        "brain": f"Consulting local Architect regarding {year}...",
                        "brain_source": "Pinky",
                    }
                )
                failover_prompt = (
                    "### SYSTEM MANDATE: ARCHIVE SILENCE ###\n"
                    f"There are NO verified records for the year {year}. "
                    "You are currently the 'Failover Architect'. "
                    "STRICT IDENTITY: Laconic, technical, and grounded. "
                    "CORE RULE: Do NOT invent projects, names (e.g., Chimera, Zenith), or scenarios. "
                    f"MANDATE: State clearly that the technical archives for {year} are empty. "
                    "Admit the gap in verified truth."
                )
                t_shadow = asyncio.create_task(
                    self.residents["pinky"].call_tool(
                        name="facilitate",
                        arguments={
                            "query": f"{failover_prompt} Query: {query}",
                            "context": "",
                        },
                    )
                )
                dispatch_map[t_shadow] = "Brain (Shadow)"
            elif self.brain_online:
                # Strategic Sovereign Tier Engagement (Normal path)
                brain_task = query
                if addressed_brain:
                    brain_task = f"[DIRECT ADDRESS] {query}"
                    if not is_strategic:
                        # Characterful wake-up call for casual addresses
                        await self.broadcast(
                            {
                                "brain": "Wake up the Architect! Narf!",
                                "brain_source": "Pinky",
                            }
                        )

                # [FEAT-108] Agentic Reflection Sequence
                if is_strategic:

                    async def brain_strategy_chain():
                        nonlocal historical_context, historical_sources
                        # [FEAT-118] Resonant Oracle: picking a state-aware preamble
                        category = "RETRIEVING" if historical_context else "HANDSHAKE"
                        try:
                            # Step 1: Immediate Perk-up Quip (Parallel with Pinky's filler)
                            # [FEAT-118] Resonant Oracle: picking a state-aware preamble
                            category = (
                                "RETRIEVING" if historical_context else "HANDSHAKE"
                            )
                            oracle_signal = self.get_oracle_signal(category)
                            await execute_dispatch(
                                oracle_signal,
                                "Brain (Signal)",
                                oracle_category=category,
                            )

                            # Step 2: Deep Technical Derivation
                            ctx = "\n".join(self.recent_interactions)
                            # [FEAT-114/088] Cognitive Bridge
                            handover_ctx = (
                                f"{ctx}\n"
                                f"Assistant (Oracle Signal): {oracle_signal}\n"
                                f"Historical Truth: {historical_context}"
                            )

                            res_deep = await self.monitor_task_with_tics(
                                self.residents["brain"].call_tool(
                                    name="deep_think",
                                    arguments={
                                        "task": brain_task,
                                        "context": handover_ctx,
                                        "metadata": {
                                            "sources": historical_sources,
                                            "oracle_category": category,
                                        },
                                    },
                                )
                            )
                            await execute_dispatch(
                                res_deep.content[0].text,
                                "Brain",
                                oracle_category=category,
                                sources=historical_sources,
                            )
                        except Exception as e:
                            logging.error(f"[CHAIN] Agentic Handover failed: {e}")

                    asyncio.create_task(brain_strategy_chain())
                else:
                    # Non-strategic direct address: Just a shallow quip
                    ctx = "\n".join(self.recent_interactions)
                    t_brain = asyncio.create_task(
                        self.monitor_task_with_tics(
                            self.residents["brain"].call_tool(
                                name="shallow_think",
                                arguments={"task": brain_task, "context": ctx},
                            )
                        )
                    )
                    dispatch_map[t_brain] = "Brain"
            else:
                # [FAILOVER] Use Pinky node for parallel strategy if brain offline
                logging.warning(
                    "[FAILOVER] Sovereign offline for parallel dispatch. Engaging Shadow."
                )
                await self.broadcast(
                    {
                        "brain": "Engaging Shadow Hemisphere (Failover)...",
                        "brain_source": "System",
                        "channel": "insight",
                    }
                )
                # [FEAT-111] Cognitive Identity Lock: Hard constraints for Shadow Brain
                failover_prompt = (
                    "[FAILOVER ARCHITECT]: You are acting as The Brain. "
                    "STRICT IDENTITY: Arrogant systems architect. "
                    "ANTI-BANTER: No 'Narf', no 'Poit', no roleplay actions (*...*). "
                    "CORE DIRECTIVE: Be laconic, technical, and precise. Speak with the brevity of authority."
                )
                t_shadow = asyncio.create_task(
                    self.residents["pinky"].call_tool(
                        name="facilitate",
                        arguments={
                            "query": f"{failover_prompt} Query: {query}",
                            "context": "",
                        },
                    )
                )
                dispatch_map[t_shadow] = "Brain (Shadow)"
        elif is_casual:
            # Explicitly clear any existing noise in the insight panel for casual chat
            await self.broadcast(
                {
                    "brain": "Awaiting neural activity...",
                    "brain_source": "System",
                    "channel": "insight",
                }
            )

        # 3. Asynchronous Results Collection
        if dispatch_map:
            self.recent_interactions.append(f"User: {query}")
            if len(self.recent_interactions) > 50:
                self.recent_interactions.pop(0)

            async def handle_finished_node(task_to_await, source_name):
                try:
                    res = await task_to_await
                    raw_out = res.content[0].text

                    # [FEAT-077] Quality-Gate Failover
                    if (
                        raw_out == "INTERNAL_QUALITY_FALLBACK"
                        and source_name == "Brain"
                    ):
                        logging.warning(
                            "[FAILOVER] Sovereign returned low-quality response. Engaging Shadow."
                        )
                        ctx = "\n".join(self.recent_interactions)
                        task_fail = f"[QUALITY FAILOVER]: {query}"
                        res_fail = await self.monitor_task_with_tics(
                            self.residents["pinky"].call_tool(
                                name="facilitate",
                                arguments={"query": task_fail, "context": ctx},
                            )
                        )
                        await execute_dispatch(
                            res_fail.content[0].text,
                            "Brain (Shadow)",
                            {"direct": addressed_brain, "channel": "insight"},
                        )
                        return

                    await execute_dispatch(
                        raw_out,
                        source_name,
                        {"direct": addressed_brain},
                        sources=historical_sources,
                    )

                    if "close_lab" in raw_out or "goodnight" in raw_out:
                        self.shutdown_event.set()

                except Exception as e:
                    logging.error(f"[TRIAGE] Node {source_name} failed: {e}")

            # Launch all handlers in parallel
            handlers = []
            for task, source in dispatch_map.items():
                handlers.append(handle_finished_node(task, source))

            await asyncio.gather(*handlers)
        else:
            await self.broadcast(
                {"brain": f"Hearing: {query}", "brain_source": "Pinky (Fallback)"}
            )
        return False

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
                self.residents[name] = session
                logging.info(f"[BOOT] {name.upper()} online.")
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
        if not disable_ear:
            self.load_ear()
        app = web.Application()
        app.router.add_get("/", self.client_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        # [FEAT-119] reuse_address=True allows reclaiming port from sockets in TIME_WAIT
        site = web.TCPSite(runner, "0.0.0.0", PORT, reuse_address=True)

        async with AsyncExitStack() as stack:
            try:
                await site.start()
                logging.info(f"[BOOT] Server on {PORT}")
                await self.boot_residents(stack)

                # [FEAT-055] Manual Task Trigger for 'Fast Alarm' testing
                if trigger_task:
                    logging.info(f"[BOOT] Manual Task Trigger: {trigger_task}")
                    if trigger_task == "recruiter":
                        import recruiter

                        asyncio.create_task(
                            recruiter.run_recruiter_task(
                                self.residents.get("archive"),
                                self.residents.get("brain"),
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
                logging.info("[SHUTDOWN] Event received. Cleaning up.")
            finally:
                logging.info("[SHUTDOWN] Final closing of residents...")
                await runner.cleanup()
                logging.info("[SHUTDOWN] Control returned to system.")


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
