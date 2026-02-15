import asyncio
import json
import logging
import os
import random
import re
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
VERSION = "3.6.4"
BRAIN_HEARTBEAT_URL = "http://localhost:11434/api/tags"
ATTENDANT_PORT = 9999
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
STATUS_JSON = os.path.join(WORKSPACE_DIR, "field_notes/data/status.json")
ROUND_TABLE_LOCK = os.path.expanduser("~/Dev_Lab/HomeLabAI/round_table.lock")


# --- THE MONTANA PROTOCOL ---
def reclaim_logger():
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    fmt = logging.Formatter('%(asctime)s - [LAB] %(levelname)s - %(message)s')
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)
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
        reclaim_logger()

    def load_ear(self):
        try:
            s_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.append(os.path.join(s_dir, "equipment"))
            from ear_node import EarNode
            self.ear = EarNode()
            logging.info("[BOOT] EarNode initialized (NeMo).")
        except Exception as e:
            logging.error(f"[BOOT] Failed to load EarNode: {e}")

    async def broadcast(self, message_dict):
        if message_dict.get("type") == "status":
            message_dict["version"] = VERSION

        l_src = message_dict.get("brain_source") or message_dict.get("type") or "System"
        l_txt = (
            message_dict.get("brain") or
            message_dict.get("text") or
            message_dict.get("message") or ""
        )
        logging.info(f"[TO_CLIENT] {l_src}: {l_txt}")

        message = json.dumps(message_dict)
        for ws in list(self.connected_clients):
            try:
                await ws.send_str(message)
            except Exception:
                pass

    async def check_brain_health(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(BRAIN_HEARTBEAT_URL, timeout=2) as resp:
                    self.brain_online = (resp.status == 200)
        except Exception:
            self.brain_online = False
        return self.brain_online

    async def trigger_cooldown(self):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:{ATTENDANT_PORT}/refresh"
                await session.post(url, timeout=2)
        except Exception as e:
            logging.error(f"[HYGIENE] Cooldown failed: {e}")

    async def reflex_loop(self):
        tics = ["Narf!", "Poit!", "Zort!", "Egad!", "Trotro!"]
        while not self.shutdown_event.is_set():
            await asyncio.sleep(30)
            if "DEBUG" not in self.mode and self.afk_timeout and self.last_activity > 0:
                idle_time = time.time() - self.last_activity
                if idle_time > self.afk_timeout:
                    logging.info(f"[AFK] Idle {idle_time:.1f}s. Cooldown.")
                    await self.trigger_cooldown()
                    self.last_activity = 0.0
            if self.connected_clients and self.status == "READY":
                if (time.time() - self.last_activity > 60):
                    self.reflex_ttl -= 0.5
                else:
                    self.reflex_ttl = 1.0
                    self.banter_backoff = max(0, self.banter_backoff - 1)
                if self.reflex_ttl <= 0:
                    tic = random.choice(tics)
                    await self.broadcast({"brain": tic, "brain_source": "Pinky"})
                    self.banter_backoff += 1
                    self.reflex_ttl = 1.0 + (self.banter_backoff * 0.5)
            await self.check_brain_health()

    async def manage_session_lock(self, active: bool):
        try:
            if active:
                with open(ROUND_TABLE_LOCK, 'w') as f:
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
        try:
            await ws.send_str(json.dumps({
                "type": "status", "version": VERSION,
                "state": "ready" if self.status == "READY" else "lobby",
                "message": "Lab foyer is open."
            }))

            async def ear_poller():
                while not ws.closed:
                    if self.ear:
                        query = self.ear.check_turn_end()
                        if query:
                            await self.broadcast({"type": "final", "text": query})
                            await self.process_query(query, ws)
                    await asyncio.sleep(0.1)
            asyncio.create_task(ear_poller())
            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(message.data)
                    m_type = data.get("type")
                    if m_type == "handshake":
                        if 'archive' in self.residents:
                            try:
                                res = await self.residents['archive'].call_tool(
                                    name="list_cabinet"
                                )
                                if res.content and hasattr(res.content[0], 'text'):
                                    files = json.loads(res.content[0].text)
                                    await ws.send_str(json.dumps({
                                        "type": "cabinet", "files": files
                                    }))
                            except Exception as e:
                                logging.error(f"[HANDSHAKE] Failed: {e}")
                    elif m_type == "text_input":
                        query = data.get("content", "")
                        self.last_activity = time.time()
                        await self.process_query(query, ws)
                    elif m_type == "workspace_save":
                        asyncio.create_task(self.handle_workspace_save(
                            data.get("filename"), data.get("content"), ws
                        ))
                    elif m_type == "read_file":
                        fn = data.get("filename")
                        if 'archive' in self.residents:
                            res = await self.residents['archive'].call_tool(
                                name="read_document", arguments={"filename": fn}
                            )
                            await ws.send_str(json.dumps({
                                "type": "file_content", "filename": fn,
                                "content": res.content[0].text
                            }))
                elif message.type == aiohttp.WSMsgType.BINARY and self.ear:
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    if len(audio_buffer) >= 24000:
                        text = self.ear.process_audio(audio_buffer[:24000])
                        if text:
                            await self.broadcast({
                                "text": text, "type": "transcription"
                            })
                        audio_buffer = audio_buffer[16000:]
        finally:
            self.connected_clients.remove(ws)
            if not self.connected_clients:
                await self.manage_session_lock(active=False)
                if "DEBUG" in self.mode and self.mode != "DEBUG_SMOKE":
                    self.shutdown_event.set()
        return ws

    async def handle_workspace_save(self, filename, content, websocket):
        logging.info(f"[WORKSPACE] User saved {filename}.")
        await websocket.send_str(json.dumps({
            "type": "file_content", "filename": filename, "content": content
        }))
        if 'archive' in self.residents:
            await self.residents['archive'].call_tool(
                name="write_draft",
                arguments={"filename": filename, "content": content}
            )

    async def process_query(self, query, websocket):
        logging.info(f"[QUERY] Processing: {query}")

        async def execute_dispatch(raw_text, source):
            """Hardened Dispatcher (v7): Cognitive verification."""
            try:
                # 1. Ask Architect to verify tool call
                t_res = "TEXT"
                if 'architect' in self.residents:
                    res = await self.residents['architect'].call_tool(
                        name="triage_response", arguments={"raw_text": raw_text}
                    )
                    t_res = res.content[0].text

                if t_res == "TEXT":
                    await self.broadcast({"brain": raw_text, "brain_source": source})
                    return True

                # 2. Parse verified JSON
                try:
                    data = json.loads(t_res)
                    # extraction fallback
                    if (not data.get("tool") and "reply_to_user" not in data and
                            "status" not in data):
                        clean_text = " ".join([str(v) for v in data.values()])
                        await self.broadcast({
                            "brain": clean_text, "brain_source": source
                        })
                        return True
                except json.JSONDecodeError:
                    await self.broadcast({"brain": raw_text, "brain_source": source})
                    return True

                tool = data.get("tool")
                params = data.get("parameters") or {}
                if isinstance(params, str):
                    params = {"text": params}

                # specialized cases
                if tool == "reply_to_user":
                    reply = params.get("text") or raw_text
                    await self.broadcast({"brain": reply, "brain_source": source})
                    return True

                if "reply_to_user" in data:
                    reply = data.get("reply_to_user")
                    if isinstance(reply, dict):
                        reply = reply.get("text", raw_text)
                    await self.broadcast({
                        "brain": str(reply), "brain_source": source
                    })
                    return True

                if tool == "close_lab" or data.get("status") == "shutdown":
                    await self.broadcast({
                        "brain": "Goodnight. Closing Lab.", "brain_source": "System"
                    })
                    self.shutdown_event.set()
                    return True

                if tool == "ask_brain" or tool == "deep_think":
                    task = params.get("task") or params.get("query") or query
                    if 'brain' in self.residents and self.brain_online:
                        res = await self.residents['brain'].call_tool(
                            name="deep_think", arguments={"task": task}
                        )
                        return await execute_dispatch(res.content[0].text, "Brain")

                t_node = "pinky"
                a_tools = [
                    "list_cabinet", "read_document",
                    "peek_related_notes", "write_draft"
                ]
                if tool in a_tools:
                    t_node = "archive"
                elif tool in ["generate_bkm", "build_semantic_map"]:
                    t_node = "architect"

                if t_node in self.residents:
                    logging.info(f"[DISPATCH] {t_node}.{tool}")
                    res = await self.residents[t_node].call_tool(
                        name=tool, arguments=params
                    )
                    return await execute_dispatch(res.content[0].text, source)

                await self.broadcast({"brain": raw_text, "brain_source": source})
                return True

            except Exception as e:
                logging.error(f"[DISPATCH] Error: {e}")
                await self.broadcast({"brain": raw_text, "brain_source": source})
                return False

        if 'pinky' in self.residents:
            try:
                res = await self.residents['pinky'].call_tool(
                    name="facilitate", arguments={"query": query, "context": ""}
                )
                return await execute_dispatch(res.content[0].text, "Pinky")
            except Exception as e:
                logging.error(f"[TRIAGE] Pinky failed: {e}")

        await self.broadcast({
            "brain": f"Hearing: {query}", "brain_source": "Pinky (Fallback)"
        })
        return False

    async def boot_residents(self):
        s_dir = os.path.dirname(os.path.abspath(__file__))
        n_dir = os.path.join(s_dir, "nodes")
        nodes = [
            ("archive", os.path.join(n_dir, "archive_node.py")),
            ("brain", os.path.join(n_dir, "brain_node.py")),
            ("pinky", os.path.join(n_dir, "pinky_node.py")),
            ("architect", os.path.join(n_dir, "architect_node.py"))
        ]

        for name, path in nodes:
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{s_dir}"
                params = StdioServerParameters(
                    command=PYTHON_PATH, args=[path], env=env
                )
                cl_stack = await self.exit_stack.enter_async_context(
                    stdio_client(params)
                )
                session = await self.exit_stack.enter_async_context(
                    ClientSession(cl_stack[0], cl_stack[1])
                )
                await session.initialize()
                self.residents[name] = session
                logging.info(f"[BOOT] {name.upper()} online.")
            except Exception as e:
                logging.error(f"[BOOT] Failed to load {name}: {e}")

        self.status = "READY"
        logging.info("[READY] Lab is Open.")
        if self.mode == "DEBUG_SMOKE":
            logging.info("[SMOKE] Successful load. Self-terminating.")
            self.shutdown_event.set()

    async def run(self, disable_ear=True):
        if not disable_ear:
            self.load_ear()
        app = web.Application()
        app.router.add_get("/", self.client_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        try:
            await site.start()
            logging.info(f"[BOOT] Server on {PORT}")
            asyncio.create_task(self.boot_residents())
            asyncio.create_task(self.reflex_loop())
            await self.shutdown_event.wait()
        finally:
            logging.info("[SHUTDOWN] Closing residents...")
            try:
                await self.exit_stack.aclose()
            except Exception:
                pass
            await runner.cleanup()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    parser.add_argument("--afk-timeout", type=int, default=300)
    parser.add_argument("--disable-ear", action="store_true", default=False)
    args = parser.parse_args()
    lab = AcmeLab(mode=args.mode, afk_timeout=args.afk_timeout)
    asyncio.run(lab.run(disable_ear=args.disable_ear))
