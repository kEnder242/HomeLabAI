import argparse
import asyncio
import datetime
import json
import logging
import os
import random
import re
import sys
import time
from contextlib import AsyncExitStack

import aiohttp
import numpy as np
import recruiter  # Class 1 Import
from aiohttp import web
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configuration
PORT = 8765
ATTENDANT_PORT = 9999
PYTHON_PATH = sys.executable
VERSION = "3.6.4"
BRAIN_URL = "http://192.168.1.26:11434/api/generate"
BRAIN_HEARTBEAT_URL = "http://192.168.1.26:11434/api/tags"
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


# Global Equipment State
EarNode = None


def load_equipment():
    global EarNode
    try:
        import torch
        torch.backends.cudnn.enabled = False
    except Exception:
        pass
    try:
        from equipment.ear_node import EarNode
        logging.info("[EQUIP] EarNode module imported.")
    except Exception as e:
        logging.error(f"[EQUIP] EarNode import failed: {e}")
    reclaim_logger()


class AcmeLab:
    BOOT_TICS = [
        "Initializing Federated Bus...",
        "Powering on Liger-Kernels...",
        "Allocating 4.5GB VRAM Baseline...",
        "Synchronizing Bicameral Handshake...",
        "Priming EarNode Decoder...",
        "Verifying Resident Liveliness...",
        "Calibrating Neural Uplink...",
        "Awaiting EngineCore Readiness..."
    ]

    def __init__(self, afk_timeout=None):
        self.residents = {}
        self.ear = None
        self.mode = "SERVICE_UNATTENDED"
        self.status = "BOOTING"
        self.connected_clients = set()
        self.shutdown_event = asyncio.Event()
        self.lock_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../../Portfolio_Dev/field_notes/data/round_table.lock"
        )
        self.last_activity = 0.0
        self.brain_online = False
        self.recent_interactions = []
        self.last_typing_event = 0.0
        self.last_save_event = 0.0
        self.ledger_path = os.path.join(LAB_DIR, "conversations.log")
        self.reflex_ttl = 1.0  # Banter health (1.0 = Quiet, 0.0 = Trigger)
        self.banter_backoff = 0  # Sequential banter penalty

    async def log_to_ledger(self, source, text):
        """Append a clean record of the conversation to a text file."""
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.ledger_path, "a") as f:
                f.write(f"[{ts}] [{source.upper()}] {text}\n")
        except Exception:
            pass

    async def manage_session_lock(self, active=True):
        try:
            if active:
                old_pid = None
                if os.path.exists(self.lock_path):
                    try:
                        with open(self.lock_path, "r") as f:
                            old_pid = f.read().strip()
                    except Exception:
                        pass
                os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
                with open(self.lock_path, "w") as f:
                    f.write(str(os.getpid()))
                self.last_activity = time.time()
                if old_pid and old_pid != str(os.getpid()):
                    logging.info(f"[LOCK] Hijacking session from PID {old_pid}.")
            else:
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
        except Exception:
            pass

    async def broadcast(self, message_dict):
        if not self.connected_clients:
            return

        if message_dict.get("type") == "final":
            await self.log_to_ledger("ME", message_dict.get("text"))
        if message_dict.get("brain"):
            content = message_dict.get("brain")
            from nodes.brain_node import _clean_content
            content = _clean_content(content)
            await self.log_to_ledger(
                message_dict.get("brain_source", "PINKY"),
                content
            )
            message_dict["brain"] = content

        if message_dict.get("type") == "status":
            message_dict["version"] = VERSION
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

    async def reflex_loop(self):
        """Weighted TTL Decay: Gradually increase banter probability during silence."""
        tics = ["Narf!", "Poit!", "Zort!", "Egad!", "Trotro!"]
        while not self.shutdown_event.is_set():
            await asyncio.sleep(30)  # Check every 30s
            
            if self.connected_clients and self.status == "READY":
                # Decay TTL if silent
                if (time.time() - self.last_activity > 60):
                    self.reflex_ttl -= 0.5
                else:
                    self.reflex_ttl = 1.0  # Reset on activity
                    self.banter_backoff = max(0, self.banter_backoff - 1)

                # Trigger banter if TTL depleted
                if self.reflex_ttl <= 0:
                    if not self.is_user_typing():
                        tic = random.choice(tics)
                        await self.broadcast({
                            "brain": tic, 
                            "brain_source": "Pinky (Reflex)"
                        })
                        self.banter_backoff += 1
                        self.reflex_ttl = 1.0 + (self.banter_backoff * 0.5) # Dynamic backoff
            
            await self.check_brain_health()

    async def scheduled_tasks_loop(self):
        while not self.shutdown_event.is_set():
            now = datetime.datetime.now()
            if now.hour == 2 and now.minute == 0:
                await self.broadcast({
                    "brain": "⏰ Alarm Clock: Nightly Recruitment...",
                    "brain_source": "System"
                })
                brief = await recruiter.run_recruiter_task(
                    archive_interface=self.residents.get("archive"),
                    brain_interface=self.residents.get("brain")
                )
                await self.broadcast({
                    "brain": f"Recruitment Drive: {os.path.basename(brief)}",
                    "brain_source": "The Nightly Recruiter",
                    "channel": "insight"
                })
                await asyncio.sleep(61)
            await asyncio.sleep(10)

    async def watchdog_loop(self):
        while not self.shutdown_event.is_set():
            await asyncio.sleep(60)
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"http://localhost:{ATTENDANT_PORT}/status"
                    async with session.get(url, timeout=2) as resp:
                        if resp.status != 200:
                            logging.error("[WATCHDOG] Attendant unresponsive!")
            except Exception:
                logging.error("[WATCHDOG] Could not connect to Attendant!")

    async def monitor_task_with_tics(self, coro, websocket, delay=2.0):
        task = asyncio.create_task(coro)
        tics = [
            "[SYSTEM] Deep Thinking active...",
            "[SYSTEM] Mistral-7B generating...",
            "[SYSTEM] Processing context..."
        ]
        while not task.done():
            done, pending = await asyncio.wait([task], timeout=delay)
            if task in done:
                return task.result()
            if self.connected_clients:
                await self.broadcast({
                    "brain": random.choice(tics),
                    "brain_source": "System"
                })
            delay = min(delay * 1.5, 6.0)
        return task.result()

    def should_cache_query(self, query: str) -> bool:
        forbidden = ["time", "date", "status", "now", "latest", "news"]
        return not any(word in query.lower() for word in forbidden)

    async def loading_monologue(self):
        while self.status == "BOOTING" and not self.shutdown_event.is_set():
            if self.connected_clients:
                tic = random.choice(self.BOOT_TICS)
                await self.broadcast({"brain": tic, "brain_source": "System"})
            await asyncio.sleep(random.uniform(3.0, 4.5))

    async def boot_sequence(self, mode):
        self.mode = mode
        app = web.Application()
        app.add_routes([web.get('/', self.client_handler)])
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', PORT).start()
        logging.info(f"[BOOT] Mode: {mode} | Door: {PORT}")
        asyncio.create_task(self.loading_monologue())
        await self.load_residents_and_equipment()

    async def load_residents_and_equipment(self):
        logging.info(f"[BUILD] Loading Residents (v{VERSION})...")
        nodes = {
            'archive': ["-m", "nodes.archive_node"],
            'pinky': ["-m", "nodes.pinky_node"],
            'brain': ["-m", "nodes.brain_node"],
            'architect': ["-m", "nodes.architect_node"],
            'thinking': ["-m", "nodes.thinking_node"],
            'browser': ["-m", "nodes.browser_node"]
        }

        async with AsyncExitStack() as stack:
            sessions = {}
            for name, args in nodes.items():
                p = StdioServerParameters(
                    command=PYTHON_PATH, args=args, env=os.environ.copy()
                )
                p.env["PYTHONPATH"] = (
                    f"{p.env.get('PYTHONPATH', '')}:{LAB_DIR}/src"
                )
                transport = await stack.enter_async_context(stdio_client(p))
                session = await stack.enter_async_context(
                    ClientSession(transport[0], transport[1])
                )
                await session.initialize()
                sessions[name] = session
                logging.info(f"[LAB] {name.capitalize()} Connected.")

            self.residents = sessions
            await self.check_brain_health()
            if EarNode:
                asyncio.create_task(self.background_load_ear())
            asyncio.create_task(self.reflex_loop())
            asyncio.create_task(self.scheduled_tasks_loop())
            asyncio.create_task(self.watchdog_loop())

            self.status = "READY"
            logging.info("[READY] Lab is Open.")
            await self.broadcast({
                "type": "status", "state": "ready", "message": "Lab is Open."
            })
            await self.shutdown_event.wait()

    async def background_load_ear(self):
        try:
            self.ear = await asyncio.to_thread(EarNode, callback=None)
            logging.info("[STT] EarNode Ready.")
        except Exception as e:
            logging.error(f"[STT] Load Failed: {e}")

    async def prime_brain(self):
        if 'brain' in self.residents and await self.check_brain_health():
            try:
                await self.residents['brain'].call_tool("wake_up")
            except Exception:
                pass

    async def amygdala_sentinel_v2(self, query):
        if not self.brain_online:
            return
        
        # Complexity Matching: Length + Technical Verbs
        tech_verbs = ["scale", "optimize", "deploy", "refactor", "validate", "synthesize"]
        word_count = len(query.split())
        has_tech = any(v in query.lower() for v in tech_verbs)
        
        if word_count > 15 and has_tech:
            logging.info(f"[AMYGDALA] Complexity trigger: {query[:50]}...")
            prompt = (
                f"[AMYGDALA INTERJECTION] I overheard: '{query}'. "
                "The conversation has reached technical depth. "
                "Provide a single, high-fidelity strategic insight (one sentence)."
            )
            res = await self.residents['brain'].call_tool(
                "deep_think", arguments={"query": prompt}
            )
            await self.broadcast({
                "brain": res.content[0].text,
                "brain_source": "The Brain",
                "channel": "insight",
                "tag": "SENTINEL"
            })

    async def client_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connected_clients.add(ws)
        await self.manage_session_lock(active=True)
        asyncio.create_task(self.prime_brain())

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
                            delegated = await self.process_query(query, ws)
                            if not delegated:
                                asyncio.create_task(
                                    self.amygdala_sentinel_v2(query)
                                )
                    await asyncio.sleep(0.1)

            poller_task = asyncio.create_task(ear_poller())

            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(message.data)
                    msg_type = data.get("type")
                    if msg_type == "handshake":
                        if 'archive' in self.residents:
                            res = await self.residents['archive'].call_tool(
                                "list_cabinet"
                            )
                            files = json.loads(res.content[0].text)
                            await ws.send_str(json.dumps({
                                "type": "cabinet", "files": files
                            }))
                    elif msg_type == "text_input":
                        query = data.get("content", "")
                        self.last_activity = time.time()
                        delegated = await self.process_query(query, ws)
                        if not delegated:
                            asyncio.create_task(self.amygdala_sentinel_v2(query))
                    elif msg_type == "read_file":
                        filename = data.get("filename")
                        if 'archive' in self.residents:
                            res = await self.residents['archive'].call_tool(
                                "read_document", arguments={"filename": filename}
                            )
                            await ws.send_str(json.dumps({
                                "type": "file_content", "filename": filename,
                                "content": res.content[0].text
                            }))
                    elif msg_type == "workspace_save":
                        asyncio.create_task(self.handle_workspace_save(
                            data.get("filename"), data.get("content"), ws
                        ))

                elif message.type == aiohttp.WSMsgType.BINARY and self.ear:
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    if len(audio_buffer) >= 24000:
                        text = self.ear.process_audio(audio_buffer[:24000])
                        if text:
                            await self.broadcast({"text": text})
                        audio_buffer = audio_buffer[16000:]

        finally:
            poller_task.cancel()
            self.connected_clients.remove(ws)
            if not self.connected_clients:
                await self.manage_session_lock(active=False)
        return ws

    async def handle_workspace_save(self, filename, content, websocket):
        logging.info(f"[WORKSPACE] User saved {filename}.")
        await websocket.send_str(json.dumps({
            "type": "file_content", "filename": filename, "content": content
        }))
        if self.is_user_typing() or (time.time() - self.last_save_event < 10):
            return
        self.last_save_event = time.time()

        await self.broadcast({
            "brain": f"[SYSTEM] Validating save: {filename}",
            "brain_source": "System"
        })

        if await self.check_brain_health():
            prompt = (
                f"[STRATEGIC VIBE CHECK] User saved '{filename}'. "
                f"Validate technical logic and offer one insight."
            )
            b_res = await self.monitor_task_with_tics(
                self.residents['brain'].call_tool(
                    "deep_think", arguments={"query": prompt}
                ),
                websocket
            )
            await self.broadcast({
                "brain": b_res.content[0].text,
                "brain_source": "The Brain",
                "channel": "insight"
            })

    async def process_query(self, query, websocket):
        await self.broadcast({
            "brain": "[SYSTEM] Engaging Experience Node...",
            "brain_source": "System"
        })
        delegated = False
        try:
            if self.should_cache_query(query):
                cache_res = await self.residents['archive'].call_tool(
                    "consult_clipboard", arguments={"query": query}
                )
                if cache_res.content[0].text != "None":
                    await self.broadcast({
                        "brain": f"[CLIPBOARD] {cache_res.content[0].text}",
                        "brain_source": "The Brain",
                        "channel": "insight"
                    })
                    return True

            res = await self.monitor_task_with_tics(
                self.residents['pinky'].call_tool(
                    "facilitate", arguments={
                        "query": query,
                        "context": str(self.recent_interactions[-3:]),
                        "memory": ""
                    }
                ),
                websocket
            )
            raw_response = res.content[0].text
            m = re.search(r'\{.*\}', raw_response, re.DOTALL)

            if m:
                dec = json.loads(m.group(0))
                tool = dec.get("tool")
                params = dec.get("parameters", {})

                if tool == "reply_to_user":
                    await self.broadcast({
                        "brain": params.get("text", "Poit!"),
                        "brain_source": "Pinky"
                    })

                elif tool in ["ask_brain", "query_brain"]:
                    delegated = True
                    if not await self.check_brain_health():
                        await self.broadcast({
                            "brain": "Narf! The big guy is napping!",
                            "brain_source": "Pinky"
                        })
                        return True

                    summary = params.get("summary") or query
                    await self.broadcast({
                        "brain": f"ASK_BRAIN: {summary}", "brain_source": "Pinky"
                    })

                    handover = (
                        f"[BICAMERAL HANDOVER]\n"
                        f"PINKY ASSESSMENT: '{raw_response[:300]}'\n"
                        f"USER QUERY: {query}\n"
                        f"TASK: {summary}"
                    )
                    brain_res = await self.monitor_task_with_tics(
                        self.residents['brain'].call_tool(
                            "deep_think", arguments={
                                "query": handover,
                                "context": str(self.recent_interactions[-5:])
                            }
                        ),
                        websocket
                    )
                    await self.broadcast({
                        "brain": brain_res.content[0].text,
                        "brain_source": "The Brain",
                        "channel": "insight"
                    })
                else:
                    try:
                        # 1. Execute tool on Pinky
                        exec_res = await self.residents['pinky'].call_tool(
                            tool, arguments=params
                        )
                        final_out = exec_res.content[0].text
                        
                        # 2. Check for Delegated Tool Call (JSON output)
                        rm = re.search(r'\{.*\}', final_out, re.DOTALL)
                        if rm:
                            try:
                                rd = json.loads(rm.group(0))
                                sub_tool = rd.get("tool")
                                sub_params = rd.get("parameters", {})
                                
                                if sub_tool == "reply_to_user":
                                    final_out = sub_params.get("text", "Poit!")
                                elif sub_tool in ["generate_bkm"]:
                                    res = await self.residents['architect'].call_tool(sub_tool, arguments=sub_params)
                                    final_out = res.content[0].text
                                elif sub_tool in ["access_personal_history", "build_cv_summary"]:
                                    res = await self.residents['archive'].call_tool(sub_tool, arguments=sub_params)
                                    final_out = res.content[0].text
                            except Exception as e:
                                logging.error(f"[HUB] Delegation failed: {e}")

                        await self.broadcast({
                            "brain": final_out, "brain_source": "Pinky"
                        })
                    except Exception as e:
                        await self.broadcast({
                            "brain": f"Tool Error: {e}", "brain_source": "Pinky"
                        })
            else:
                await self.broadcast({
                    "brain": raw_response, "brain_source": "Pinky"
                })

            self.recent_interactions.append(query)
            if len(self.recent_interactions) > 10:
                self.recent_interactions.pop(0)

        except Exception as e:
            await self.broadcast({
                "brain": f"Narf! Error: {e}", "brain_source": "Pinky"
            })
        return delegated


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    args = parser.parse_args()
    load_equipment()
    lab = AcmeLab()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(lab.boot_sequence(args.mode))
