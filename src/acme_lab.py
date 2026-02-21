import asyncio
import json
import logging
import os
import random
import sys
import time
from typing import Dict, Set

import aiohttp
import numpy as np
from aiohttp import web
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# Configuration
PORT = 8765
PYTHON_PATH = sys.executable
VERSION = "3.8.0"  # Unity Base & Shadow Dispatch
BRAIN_HEARTBEAT_URL = "http://localhost:11434/api/tags"
ATTENDANT_PORT = 9999
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
STATUS_JSON = os.path.join(WORKSPACE_DIR, "field_notes/data/status.json")
NIGHTLY_DIALOGUE_FILE = os.path.join(WORKSPACE_DIR, "field_notes/data/nightly_dialogue.json")
ROUND_TABLE_LOCK = os.path.join(LAB_DIR, "round_table.lock")
SERVER_LOG = os.path.join(LAB_DIR, "server.log")


# --- THE MONTANA PROTOCOL ---
def reclaim_logger():
    root = logging.getLogger()
    # Aggressively clear all existing handlers to prevent double-logging
    while root.handlers:
        root.removeHandler(root.handlers[0])
        
    fmt = logging.Formatter("%(asctime)s - [LAB] %(levelname)s - %(message)s")

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


class EarNode:
    """Stub for sensory input. NeMo imported via equipment/ear_node.py."""

    def __init__(self):
        self.is_listening = True

    def check_turn_end(self):
        return None

    def process_audio(self, chunk):
        return None


class AcmeLab:
    def __init__(self, mode="SERVICE_UNATTENDED", afk_timeout=300):
        self.mode = mode
        self.afk_timeout = afk_timeout
        self.status = "INIT"
        self.connected_clients: Set[web.WebSocketResponse] = set()
        self.residents: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.shutdown_event = asyncio.Event()
        self.last_activity = time.time()
        self.last_save_event = 0.0
        self.last_typing_event = 0.0 # [FEAT-052] Typing Awareness
        self.reflex_ttl = 1.0
        self.banter_backoff = 0
        self.brain_online = False
        self.mic_active = False # [FEAT-025] Amygdala Switch State
        self.ear = None
        self.recent_interactions = []
        reclaim_logger()

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
                    summary = content[:300].replace("\n", " ")
                    await ws.send_str(json.dumps({
                        "brain": f"While you were out, we discussed: {summary}...",
                        "brain_source": "Pinky",
                        "channel": "chat"
                    }))
            except Exception as e:
                logging.error(f"[BRIEF] Failed to trigger briefing: {e}")

    async def monitor_task_with_tics(self, coro, delay=2.5):
        """Sends state-aware tics during long reasoning tasks."""
        task = asyncio.create_task(coro)
        
        # Standard character tics
        base_tics = ["Thinking...", "Processing...", "Just a moment...", "Checking circuits..."]
        
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
                    
                    await self.broadcast({
                        "brain": tic_msg,
                        "brain_source": "Pinky (Reflex)"
                    })
                    tic_count += 1
                
                # Increase delay exponentially
                current_delay = min(current_delay * 1.5, 8.0)
            except Exception:
                if task.done():
                    return task.result()
        return task.result()

    async def check_brain_health(self):
        """Hardened Health Check: Perform a single-token generation probe."""
        try:
            async with aiohttp.ClientSession() as session:
                # 1. First check if endpoint is even reachable (fast)
                async with session.get(BRAIN_HEARTBEAT_URL, timeout=1) as r:
                    if r.status != 200:
                        self.brain_online = False
                        return

                # 2. PROBE: Attempt a single-token generation to verify VRAM/Engine availability
                # This prevents False Positives when the service is up but the model is stuck.
                p_url = BRAIN_HEARTBEAT_URL.replace("/api/tags", "/api/generate")
                payload = {
                    "model": "mixtral:8x7b", 
                    "prompt": "ping",
                    "stream": False,
                    "num_predict": 1
                }
                async with session.post(p_url, json=payload, timeout=2) as r:
                    self.brain_online = r.status == 200
        except Exception:
            self.brain_online = False

    async def reflex_loop(self):
        """Background maintenance and status updates."""
        tics = ["Narf!", "Poit!", "Zort!", "Checking circuits...", "Egad!", "Trotro!"]
        while not self.shutdown_event.is_set():
            await asyncio.sleep(self.reflex_ttl)
            if self.connected_clients:
                await self.broadcast({
                    "type": "status",
                    "state": "ready" if self.status == "READY" else "booting",
                    "brain_online": self.brain_online,
                })
                # [FEAT-039] Banter Decay: Slow down reflexes when idle (> 60s)
                idle_time = time.time() - self.last_activity
                if idle_time > 60:
                    if self.banter_backoff < 10: # Cap at 6s interval (1.0 + 10*0.5)
                        self.banter_backoff += 1
                    
                    # [FEAT-047] Reflex Tics: Occasionally bubble up a character tic
                    # Only if idle for > 60s, not typing, and low probability (approx every 2 mins @ 6s interval)
                    if not self.is_user_typing() and random.random() < 0.05:
                        await self.broadcast({
                            "brain": random.choice(tics),
                            "brain_source": "Pinky (Reflex)"
                        })
                else:
                    self.banter_backoff = 0
                
                self.reflex_ttl = 1.0 + (self.banter_backoff * 0.5)
            await self.check_brain_health()

    async def scheduled_tasks_loop(self):
        """The Alarm Clock: Runs scheduled jobs like the Nightly Recruiter."""
        import recruiter
        import internal_debate
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
                if 'architect' in self.residents:
                    logging.info("[ALARM] Triggering Hierarchy Refactor...")
                    try:
                        await self.residents['architect'].call_tool(
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
                    await internal_debate.run_nightly_talk(a_node, p_node, b_node)
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

    async def check_intent_is_casual(self, text):
        """[VIBE] Semantic Gatekeeper: Determines if a query is casual or strategic."""
        # Future: Call Llama-1B here for high-fidelity classification
        casual_indicators = ["hello", "hi", "hey", "how are you", "pinky", "anyone home"]
        strat_indicators = ["silicon", "validation", "regression", "root cause", "architect", "logic"]
        
        text_low = text.lower()
        is_casual = any(k in text_low for k in casual_indicators)
        is_strat = any(k in text_low for k in strat_indicators)
        
        # If it's both, treat as strategic (The 'Hey, I found a bug' rule)
        if is_strat:
            return False
        return is_casual

    async def client_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connected_clients.add(ws)
        await self.manage_session_lock(active=True)
        audio_buffer = np.zeros(0, dtype=np.int16)
        current_processing_task = None

        try:
            await ws.send_str(json.dumps({
                "type": "status",
                "version": VERSION,
                "state": "ready" if self.status == "READY" else "lobby",
                "message": "Lab foyer is open.",
            }))
            
            # [FEAT-072] Morning Briefing
            asyncio.create_task(self.trigger_morning_briefing(ws))
            
            # [FEAT-026] Initial Brain Status Feedback
            await ws.send_str(json.dumps({
                "brain": f"Strategic Sovereignty: {'ONLINE' if self.brain_online else 'OFFLINE'}",
                "brain_source": "System",
                "channel": "insight"
            }))

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
                                await self.broadcast({
                                    "brain": "Stopping... Narf!",
                                    "brain_source": "Pinky",
                                })
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
                        if "archive" in self.residents:
                            try:
                                res = await self.residents["archive"].call_tool(
                                    name="list_cabinet"
                                )
                                if res.content and hasattr(res.content[0], "text"):
                                    files = json.loads(res.content[0].text)
                                    await ws.send_str(json.dumps({
                                        "type": "cabinet", "files": files
                                    }))
                            except Exception as e:
                                logging.error(f"[HANDSHAKE] Failed: {e}")
                    elif m_type == "mic_state":
                        self.mic_active = data.get("active", False)
                        logging.info(f"[MIC] State changed: {self.mic_active}")
                        await self.broadcast({
                            "type": "status", "message": f"Mic {'Active' if self.mic_active else 'Muted'}",
                            "mic_active": self.mic_active
                        })
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
                            await ws.send_str(json.dumps({
                                "type": "file_content",
                                "filename": fn,
                                "content": res.content[0].text,
                            }))
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
                            await self.broadcast({
                                "text": text, "type": "transcription"
                            })
                            # SHADOW DISPATCH: Proactive Brain Engagement
                            strat_keys = [
                                "architecture", "silicon", "regression", "validate"
                            ]
                            # [FEAT-027] Hard Gate for Shadow Dispatch
                            is_text_casual = await self.check_intent_is_casual(text)
                            
                            if any(
                                k in text.lower() for k in strat_keys
                            ) and not current_processing_task and not is_text_casual:
                                logging.info(f"[SHADOW] Intent detected: {text}")
                                await self.broadcast({
                                    "brain": "Predicted strategic intent... preparing.",
                                    "brain_source": "Brain (Shadow)",
                                })
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
        await self.broadcast({
            "brain": f"Poit! I noticed you saved {filename}. Let me look...",
            "brain_source": "Pinky"
        })

        if self.brain_online and "brain" in self.residents:
            prompt = (
                f"[STRATEGIC VIBE CHECK] User saved '{filename}'. "
                f"Content starts with: '{content[:500]}'. Validate the "
                "technical logic and offer one architectural improvement."
            )
            # [FEAT-048] Monitor long-running Vibe Checks
            b_res = await self.monitor_task_with_tics(
                self.residents['brain'].call_tool(
                    name="deep_think", arguments={"task": prompt}
                )
            )
            await self.broadcast({
                "brain": b_res.content[0].text,
                "brain_source": "The Brain",
                "channel": "insight"
            })
        
        self.last_save_event = time.time()
        self.last_activity = time.time()

    async def process_query(self, query, websocket):
        # [FEAT-018] Interaction Logging: Ensuring user inputs are permanently captured
        logging.info(f"[USER] Intercom Query: {query}")
        
        # [FEAT-056] MIB Memory Wipe Mechanic
        # Allows user to manually clear the interaction context (The "Neuralyzer")
        wipe_keys = ["look at the light", "wipe memory", "neuralyzer", "clear context"]
        if any(k in query.lower() for k in wipe_keys):
            self.recent_interactions = []
            logging.info("[MEMORY] MIB Wipe triggered. Context cleared.")
            await self.broadcast({
                "brain": "Look at the light... *FLASH* ... Narf! What were we talking about?",
                "brain_source": "Pinky",
                "type": "memory_clear"
            })
            return

        is_casual = await self.check_intent_is_casual(query)
        
        # [DEBUG] Persona Bleed Investigation
        logging.info(f"[DEBUG] query='{query}' is_casual={is_casual}")
        
        # 0. HEURISTIC SENTINEL
        shutdown_keys = ["close the lab", "goodnight", "shutdown", "exit lab"]
        if any(k in query.lower() for k in shutdown_keys):
            logging.info("[SHUTDOWN] Heuristic Triggered.")
            await self.broadcast({
                "brain": "Goodnight. Closing Lab.",
                "brain_source": "System",
                "type": "shutdown",
            })
            self.shutdown_event.set()
            return

        # 1. Strategic Sentinel Logic
        strat_keys = [
            "regression", "validation", "scars", "root cause",
            "race condition", "unstable", "silicon", "optimize",
        ]
        
        # [FEAT-025] Amygdala Logic: Use 1B model as smart filter when typing
        is_strategic = False
        if self.mic_active:
            # Voice Mode: Use keyword-based sentinel for speed
            is_strategic = any(k in query.lower() for k in strat_keys) and not is_casual
        else:
            # Typing Mode: Use Amygdala (1B) to filter
            if not is_casual:
                logging.info("[AMYGDALA] Filtering query...")
                is_strategic = True # Future: Call Llama-1B to decide
        
        addressed_brain = "brain" in query.lower()

        async def execute_dispatch(raw_text, source, context_flags=None):
            """Hardened Priority Dispatcher with Hallucination Shunt."""
            logging.info(f"[DEBUG] Dispatch: source='{source}' text='{raw_text[:30]}...'")
            
            # [FEAT-026] Brain Voice Restoration: Force raw text for Architect
            if source == "Brain" and "{" not in raw_text:
                await self.broadcast({"brain": raw_text, "brain_source": "Brain"})
                return True

            try:
                # Recursive JSON extraction
                data = json.loads(raw_text) if "{" in raw_text else raw_text
                tool = data.get("tool") if isinstance(data, dict) else None
                params = data.get("parameters", {}) if isinstance(data, dict) else {}

                is_shutdown = tool == "close_lab" or "close_lab()" in raw_text or "goodnight" in raw_text.lower()
                if is_shutdown:
                    await self.broadcast({
                        "brain": "Goodnight. Closing Lab.", "brain_source": "System", "type": "shutdown"
                    })
                    self.shutdown_event.set()
                    return True

                # Validation: Shunt hallucinations to Pinky
                known_tools = [
                    "reply_to_user", "ask_brain", "deep_think", "list_cabinet",
                    "read_document", "peek_related_notes", "write_draft",
                    "generate_bkm", "build_semantic_map", "peek_strategic_map",
                    "discuss_offline", "select_file", "notify_file_open"
                ]

                # [FEAT-074] Workbench Routing
                if tool == "select_file":
                    fname = params.get("filename")
                    await self.broadcast({"type": "file_content_request", "filename": fname})
                    return True

                if tool == "discuss_offline":
                    topic = params.get("topic") or query
                    import internal_debate
                    logging.info(f"[DEBATE] User requested offline discussion: {topic}")
                    await self.broadcast({
                        "brain": f"Narf! We'll chew on '{topic}' while you're out!",
                        "brain_source": "Pinky"
                    })
                    # Run in background without blocking interaction
                    asyncio.create_task(internal_debate.run_nightly_talk(
                        self.residents.get("archive"),
                        self.residents.get("pinky"),
                        self.residents.get("brain"),
                        topic=topic
                    ))
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
                    await self.broadcast({"brain": str(reply), "brain_source": source})
                    return True

                if tool == "ask_brain" or tool == "deep_think":
                    task = params.get("task") or params.get("query") or query
                    
                    # [FEAT-027] Iron Gate: Double-check for casualness in both original and delegated task
                    is_task_casual = await self.check_intent_is_casual(task)
                    if is_casual or is_task_casual:
                        logging.warning(f"[GATE] Blocking casual delegation. Task: '{task}'")
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
                        logging.warning("[FAILOVER] Sovereign offline. Rerouting to Shadow Hemisphere.")
                        task = f"[FAILOVER ARCHITECT]: {task}"

                    # [FEAT-057] Deep Context: Send full interaction history instead of sliced window
                    if target_node in self.residents:
                        ctx = "\n".join(self.recent_interactions)
                        t_name = "deep_think" if target_node == "brain" else "facilitate"
                        t_args = {"task": task, "context": ctx} if target_node == "brain" else {"query": task, "context": ctx}
                        
                        # [FEAT-048] Monitor long-running Brain tasks
                        res = await self.monitor_task_with_tics(
                            self.residents[target_node].call_tool(name=t_name, arguments=t_args)
                        )
                        return await execute_dispatch(res.content[0].text, "Brain" if self.brain_online else "Brain (Shadow)")
                    else:
                        await self.broadcast({
                            "brain": "Analytical primary is OFFLINE. No failover available.",
                            "brain_source": "System",
                            "channel": "insight"
                        })
                        return False

                t_node = "pinky"
                a_tools = [
                    "list_cabinet", "read_document", "peek_related_notes", "write_draft"
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
        
        if "pinky" in self.residents:
            t_pinky = asyncio.create_task(
                self.residents["pinky"].call_tool(
                    name="facilitate", arguments={"query": query, "context": ""}
                )
            )
            dispatch_map[t_pinky] = "Pinky"

        # [FEAT-027] Hard Gate: Only engage Brain if NOT casual
        if "brain" in self.residents and (is_strategic or addressed_brain) and not is_casual:
            # Strategic Sovereign Tier Engagement
            if self.brain_online:
                brain_task = query
                if addressed_brain:
                    brain_task = f"[DIRECT ADDRESS] {query}"
                    await self.broadcast({
                        "brain": "Wake up the Architect! Narf!",
                        "brain_source": "Pinky",
                    })
                else:
                    logging.info("[SENTINEL] Strategic detected. Engaging Brain.")
                
                # [FEAT-026] Engagement Feedback
                await self.broadcast({
                    "brain": "Engaging Strategic Sovereign...",
                    "brain_source": "System",
                    "channel": "insight"
                })

                # [FEAT-048] Monitor long-running Brain tasks
                # [FEAT-057] Deep Context: Send full interaction history
                ctx = "\n".join(self.recent_interactions)
                t_brain = asyncio.create_task(
                    self.monitor_task_with_tics(
                        self.residents["brain"].call_tool(
                            name="deep_think", arguments={"task": brain_task, "context": ctx}
                        )
                    )
                )
                dispatch_map[t_brain] = "Brain"
            else:
                # [FAILOVER] Use Pinky node for parallel strategy if brain offline
                logging.warning("[FAILOVER] Sovereign offline for parallel dispatch. Engaging Shadow.")
                await self.broadcast({
                    "brain": "Engaging Shadow Hemisphere (Failover)...",
                    "brain_source": "System",
                    "channel": "insight"
                })
                t_shadow = asyncio.create_task(
                    self.residents["pinky"].call_tool(
                        name="facilitate", arguments={"query": f"[FAILOVER ARCHITECT]: {query}", "context": ""}
                    )
                )
                dispatch_map[t_shadow] = "Brain (Shadow)"
        elif is_casual:
            # Explicitly clear any existing noise in the insight panel for casual chat
            await self.broadcast({
                "brain": "Awaiting neural activity...",
                "brain_source": "System",
                "channel": "insight"
            })

        # 3. Collect
        if dispatch_map:
            tasks = list(dispatch_map.keys())
            done, pending = await asyncio.wait(tasks, timeout=120)
            self.recent_interactions.append(f"User: {query}")
            if len(self.recent_interactions) > 50:
                self.recent_interactions.pop(0)

            for t in done:
                try:
                    res = t.result()
                    raw_out = res.content[0].text
                    source = dispatch_map[t]
                    if "close_lab" in raw_out or "goodnight" in raw_out:
                        for p in pending:
                            p.cancel()
                        await execute_dispatch(
                            raw_out, source, {"direct": addressed_brain}
                        )
                        return True
                    await execute_dispatch(raw_out, source, {"direct": addressed_brain})
                except Exception as e:
                    logging.error(f"[TRIAGE] Node failed: {e}")
        else:
            await self.broadcast({
                "brain": f"Hearing: {query}", "brain_source": "Pinky (Fallback)"
            })
        return False

    async def boot_residents(self, stack: AsyncExitStack):
        """Internal boot sequence: Must remain in unitary task."""
        await self.broadcast({
            "type": "status", "message": "Initializing residents...", "state": "booting"
        })
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
                    command=PYTHON_PATH, args=[path], env=env
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
        sys.stderr.flush() # Ensure signal is written to the log file
        await self.broadcast({
            "type": "status", "message": "Mind is ONLINE. Lab is Open.", "state": "ready"
        })
        if self.mode == "DEBUG_SMOKE":
            logging.info("[SMOKE] Successful load. Self-terminating.")
            self.shutdown_event.set()

    async def run(self, disable_ear=False, trigger_task=None):
        if not disable_ear:
            self.load_ear()
        app = web.Application()
        app.router.add_get("/", self.client_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)

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
                        asyncio.create_task(recruiter.run_recruiter_task(
                            self.residents.get("archive"), 
                            self.residents.get("brain")
                        ))
                    elif trigger_task == "architect":
                        if "architect" in self.residents:
                            asyncio.create_task(self.residents["architect"].call_tool(
                                name="build_semantic_map"
                            ))

                asyncio.create_task(self.reflex_loop())
                asyncio.create_task(self.scheduled_tasks_loop()) # [FEAT-049] Alarm Clock
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
    parser.add_argument("--trigger-task", choices=["recruiter", "architect"], help="Run a background task immediately on startup.")
    args = parser.parse_args()
    lab_instance = AcmeLab(mode=args.mode, afk_timeout=args.afk_timeout)
    asyncio.run(lab_instance.run(disable_ear=args.disable_ear, trigger_task=args.trigger_task))
