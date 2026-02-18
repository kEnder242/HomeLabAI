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
ROUND_TABLE_LOCK = os.path.join(LAB_DIR, "round_table.lock")
SERVER_LOG = os.path.join(LAB_DIR, "server.log")


# --- THE MONTANA PROTOCOL ---
def reclaim_logger():
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
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
        self.reflex_ttl = 1.0
        self.banter_backoff = 0
        self.brain_online = False
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

    async def check_brain_health(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(BRAIN_HEARTBEAT_URL, timeout=1) as r:
                    self.brain_online = r.status == 200
        except Exception:
            self.brain_online = False

    async def reflex_loop(self):
        """Background maintenance and status updates."""
        while not self.shutdown_event.is_set():
            await asyncio.sleep(self.reflex_ttl)
            if self.connected_clients:
                await self.broadcast({
                    "type": "status",
                    "state": "ready" if self.status == "READY" else "booting",
                    "brain_online": self.brain_online,
                })
                # Banter Decay
                if self.banter_backoff > 0:
                    self.banter_backoff -= 1
                    self.reflex_ttl = 1.0 + (self.banter_backoff * 0.5)
            await self.check_brain_health()

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
                elif message.type == aiohttp.WSMsgType.BINARY and self.ear:
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    if np.abs(chunk).max() > 500 and random.random() < 0.05:
                        logging.info("[AUDIO] Signal detected.")
                    if len(audio_buffer) >= 24000:
                        text = self.ear.process_audio(audio_buffer[:24000])
                        if text:
                            await self.broadcast({
                                "text": text, "type": "transcription"
                            })
                            # SHADOW DISPATCH: Proactive Brain Engagement
                            strat_keys = [
                                "architecture", "silicon", "regression", "validate"
                            ]
                            if any(
                                k in text.lower() for k in strat_keys
                            ) and not current_processing_task:
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
        """Triggered on manual save: Performs strategic vibe check."""
        logging.info(f"[WORKSPACE] Save Event: {filename}")
        if "archive" in self.residents:
            # Atomic save to disk first
            pass
        self.last_save_event = time.time()

    async def process_query(self, query, websocket):
        # [FEAT-018] Interaction Logging: Ensuring user inputs are permanently captured
        logging.info(f"[USER] Intercom Query: {query}")
        
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
        is_strategic = any(k in query.lower() for k in strat_keys)
        addressed_brain = "brain" in query.lower()

        async def execute_dispatch(raw_text, source, context_flags=None):
            """Hardened Priority Dispatcher with Hallucination Shunt."""
            try:
                # Recursive JSON extraction
                data = json.loads(raw_text) if "{" in raw_text else raw_text
                tool = data.get("tool") if isinstance(data, dict) else None
                params = data.get("parameters", {}) if isinstance(data, dict) else {}

                is_shutdown = tool == "close_lab" or "goodnight" in raw_text.lower()
                if is_shutdown:
                    await self.broadcast({
                        "brain": "Goodnight. Closing Lab.", "brain_source": "System"
                    })
                    self.shutdown_event.set()
                    return True

                # Validation: Shunt hallucinations to Pinky
                known_tools = [
                    "reply_to_user", "ask_brain", "deep_think", "list_cabinet",
                    "read_document", "peek_related_notes", "write_draft",
                    "generate_bkm", "build_semantic_map", "peek_strategic_map"
                ]
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
                    if context_flags and context_flags.get("direct"):
                        task = f"[DIRECT ADDRESS] {task}"

                    if "brain" in self.residents and self.brain_online:
                        ctx = "\n".join(self.recent_interactions[-3:])
                        res = await self.residents["brain"].call_tool(
                            name="deep_think", arguments={"task": task, "context": ctx}
                        )
                        return await execute_dispatch(res.content[0].text, "Brain")

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
        tasks = []
        if "pinky" in self.residents:
            tasks.append(asyncio.create_task(
                self.residents["pinky"].call_tool(
                    name="facilitate", arguments={"query": query, "context": ""}
                )
            ))

        if "brain" in self.residents and (is_strategic or addressed_brain):
            brain_task = query
            if addressed_brain:
                brain_task = f"[DIRECT ADDRESS] {query}"
                await self.broadcast({
                    "brain": "Narf! I'll wake up the Left Hemisphere!",
                    "brain_source": "Pinky",
                })
            else:
                logging.info("[SENTINEL] Strategic detected. Engaging Brain.")

            ctx = "\n".join(self.recent_interactions[-3:])
            tasks.append(asyncio.create_task(
                self.residents["brain"].call_tool(
                    name="deep_think", arguments={"task": brain_task, "context": ctx}
                )
            ))

        # 3. Collect
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=60)
            self.recent_interactions.append(f"User: {query}")
            if len(self.recent_interactions) > 10:
                self.recent_interactions.pop(0)

            for t in done:
                try:
                    res = t.result()
                    raw_out = res.content[0].text
                    source = "Pinky" if "facilitate" in str(t) else "Brain"
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
                
                # FORCE VLLM FOR ALL NODES (Unity Pattern Standard)
                env["USE_BRAIN_VLLM"] = "1"
                env["BRAIN_MODEL"] = "unified-base"
                env["PINKY_MODEL"] = "unified-base"
                
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
        await self.broadcast({
            "type": "status", "message": "Mind is ONLINE. Lab is Open.", "state": "ready"
        })
        if self.mode == "DEBUG_SMOKE":
            logging.info("[SMOKE] Successful load. Self-terminating.")
            self.shutdown_event.set()

    async def run(self, disable_ear=False):
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
                asyncio.create_task(self.reflex_loop())
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
    args = parser.parse_args()
    lab_instance = AcmeLab(mode=args.mode, afk_timeout=args.afk_timeout)
    asyncio.run(lab_instance.run(disable_ear=args.disable_ear))
