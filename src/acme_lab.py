import asyncio
import aiohttp
from aiohttp import web
import json
import logging
import argparse
import sys
import numpy as np
import random
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

import os

# Configuration
PORT = 8765
PYTHON_PATH = sys.executable
VERSION = "3.5.0" # Bicameral Dispatch Alpha
BRAIN_URL = "http://192.168.1.26:11434/api/generate"
BRAIN_HEARTBEAT_URL = "http://192.168.1.26:11434/api/tags"

# --- THE MONTANA PROTOCOL ---
def reclaim_logger():
    root = logging.getLogger()
    for h in root.handlers[:]: root.removeHandler(h)
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
    except: pass
    try:
        from equipment.ear_node import EarNode
        logging.info("[EQUIP] EarNode module imported.")
    except Exception as e:
        logging.error(f"[EQUIP] EarNode import failed: {e}")
    reclaim_logger()

class AcmeLab:
    def __init__(self, afk_timeout=None):
        self.residents = {}
        self.ear = None
        self.mode = "SERVICE_UNATTENDED"
        self.status = "BOOTING"
        self.connected_clients = set()
        self.shutdown_event = asyncio.Event()
        self.lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../Portfolio_Dev/field_notes/data/round_table.lock")
        self.last_activity = 0.0
        self.banter_ttl = 0
        self.brain_online = False
        self.recent_interactions = [] # For Contextual Handover
        self.last_typing_event = 0.0

    async def manage_session_lock(self, active=True):
        try:
            if active:
                os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
                with open(self.lock_path, "w") as f: f.write(str(os.getpid()))
                self.last_activity = time.time()
            else:
                if os.path.exists(self.lock_path): os.remove(self.lock_path)
        except: pass

    async def broadcast(self, message_dict):
        if not self.connected_clients: return
        if message_dict.get("type") == "status": message_dict["version"] = VERSION
        message = json.dumps(message_dict)
        for ws in list(self.connected_clients):
            try: await ws.send_str(message)
            except: pass

    async def check_brain_health(self):
        """Heartbeat check for the 4090 host."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(BRAIN_HEARTBEAT_URL, timeout=2) as resp:
                    self.brain_online = (resp.status == 200)
        except:
            self.brain_online = False
        return self.brain_online

    async def reflex_loop(self):
        """Non-blocking characterful reflexes and alerts."""
        tics = ["Narf!", "Poit!", "Zort!", "Checking the circuits...", "Egad!", "Trotro!"]
        while not self.shutdown_event.is_set():
            await asyncio.sleep(random.randint(45, 120))
            if self.connected_clients and self.status == "READY":
                # Only tic if idle and NOT typing
                if (time.time() - self.last_activity > 30) and not self.is_user_typing():
                    tic = random.choice(tics)
                    await self.broadcast({"brain": tic, "brain_source": "Pinky (Reflex)"})
            
            # Periodically check Brain health
            await self.check_brain_health()

    async def monitor_task_with_tics(self, coro, websocket, delay=2.5):
        task = asyncio.create_task(coro)
        tics = ["Thinking...", "Consulting the Architect...", "Processing...", "Just a moment..."]
        while not task.done():
            done, pending = await asyncio.wait([task], timeout=delay)
            if task in done: return task.result()
            if self.connected_clients:
                await self.broadcast({"brain": random.choice(tics), "brain_source": "Pinky (Reflex)"})
            delay = min(delay * 1.5, 6.0)
        return task.result()

    def should_cache_query(self, query: str) -> bool:
        forbidden = ["time", "date", "status", "now", "latest", "news", "update"]
        q_lower = query.lower()
        return not any(word in q_lower for word in forbidden)

    async def load_residents_and_equipment(self):
        logging.info(f"[BUILD] Loading Residents (v{VERSION})...")
        a_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
        p_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/pinky_node.py"])
        b_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

        try:
            # 1. Archive Node
            async with stdio_client(a_p) as (ar, aw):
                async with ClientSession(ar, aw) as archive:
                    await archive.initialize()
                    self.residents['archive'] = archive
                    logging.info("[LAB] Archive Connected.")

                    # 2. Pinky Node
                    async with stdio_client(p_p) as (pr, pw):
                        async with ClientSession(pr, pw) as pinky:
                            await pinky.initialize()
                            self.residents['pinky'] = pinky
                            logging.info("[LAB] Pinky Connected.")

                            # 3. Brain Node
                            async with stdio_client(b_p) as (br, bw):
                                async with ClientSession(br, bw) as brain:
                                    await brain.initialize()
                                    self.residents['brain'] = brain
                                    logging.info("[LAB] Brain Connected.")

                                    # 4. Final Prep
                                    if EarNode: asyncio.create_task(self.background_load_ear())
                                    asyncio.create_task(self.reflex_loop())
                                    
                                    self.status = "READY"
                                    logging.info("[READY] Lab is Open.")
                                    await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Open."})
                                    await self.shutdown_event.wait()

        except Exception as e:
            logging.error(f"[FATAL] Startup Failure: {e}")
        finally:
            os._exit(0)

    async def background_load_ear(self):
        try:
            self.ear = await asyncio.to_thread(EarNode, callback=None)
            logging.info("[STT] EarNode Ready.")
        except Exception as e:
            logging.error(f"[STT] Load Failed: {e}")

    async def prime_brain(self):
        if 'brain' in self.residents and await self.check_brain_health():
            try: await self.residents['brain'].call_tool("wake_up")
            except: pass

    async def boot_sequence(self, mode):
        self.mode = mode
        app = web.Application()
        app.add_routes([web.get('/', self.client_handler)]) 
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', PORT).start()
        logging.info(f"[BOOT] Mode: {mode} | Door: {PORT}")
        await self.load_residents_and_equipment()

    async def sentinel_check(self, query):
        """Brain interjects if it hears critical keywords in the background."""
        critical_keywords = ["error", "failure", "crash", "timeout", "pcie", "thermal", "msr"]
        if any(k in query.lower() for k in critical_keywords) and self.brain_online:
            logging.info(f"[SENTINEL] Brain noticed keyword in: {query}")
            res = await self.residents['brain'].call_tool("deep_think", arguments={"query": f"[SENTINEL INTERJECTION] I overheard mention of '{query}'. Scan archives for related silicon scars or validation BKMs."})
            await self.broadcast({"brain": res.content[0].text, "brain_source": "The Brain", "channel": "insight", "tag": "SENTINEL"})

    async def client_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connected_clients.add(ws)
        await self.manage_session_lock(active=True)
        asyncio.create_task(self.prime_brain())
        
        audio_buffer = np.zeros(0, dtype=np.int16)
        try:
            await ws.send_str(json.dumps({"type": "status", "version": VERSION, "state": "ready" if self.status == "READY" else "lobby", "message": "Lab foyer is open."}))
            
            async def ear_poller():
                while not ws.closed:
                    if self.ear:
                        query = self.ear.check_turn_end()
                        if query:
                            await self.broadcast({"type": "final", "text": query})
                            asyncio.create_task(self.process_query(query, ws))
                            # --- SENTINEL HOOK ---
                            asyncio.create_task(self.sentinel_check(query))
                    await asyncio.sleep(0.1)
            
            poller_task = asyncio.create_task(ear_poller())

            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(message.data)
                    if data.get("type") == "handshake":
                        if 'archive' in self.residents:
                            res = await self.residents['archive'].call_tool("list_cabinet")
                            await ws.send_str(json.dumps({"type": "cabinet", "files": json.loads(res.content[0].text)}))
                    elif data.get("type") == "text_input":
                        query = data.get("content", "")
                        self.last_activity = time.time()
                        asyncio.create_task(self.process_query(query, ws))
                    elif data.get("type") == "user_typing":
                        self.last_typing_event = time.time()
                    elif data.get("type") == "workspace_save":
                        asyncio.create_task(self.handle_workspace_save(data.get("filename"), data.get("content"), ws))
                
                elif message.type == aiohttp.WSMsgType.BINARY and self.ear:
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    if len(audio_buffer) >= 24000:
                        text = self.ear.process_audio(audio_buffer[:24000])
                        if text: await self.broadcast({"text": text})
                        audio_buffer = audio_buffer[16000:]

        finally:
            poller_task.cancel()
            self.connected_clients.remove(ws)
            if not self.connected_clients: await self.manage_session_lock(active=False)
        return ws

    def is_user_typing(self):
        """Returns True if the user has typed recently (2s window)."""
        return (time.time() - self.last_typing_event) < 2.0

    async def handle_workspace_save(self, filename, content, websocket):
        """Notifies agents of a manual save and triggers reactions."""
        logging.info(f"[WORKSPACE] User saved {filename}.")
        # 1. Update file on disk (via scribble or workspace tool if we had one, for now scribble)
        try:
            # We don't have a direct workspace write tool in archive node yet, using scribble as placeholder
            await self.residents['archive'].call_tool("scribble_note", arguments={"query": f"SAVE_EVENT: {filename}", "response": content})
        except: pass

        # 2. Pinky's Reflexive Reaction
        if not self.is_user_typing():
            await self.broadcast({"brain": f"Poit! I noticed you saved {filename}. Let me take a look...", "brain_source": "Pinky"})
            
            # 3. Brain's Strategic Vibe Check
            if self.brain_online:
                b_res = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": f"The user just saved '{filename}'. Content starts with: '{content[:200]}'. Provide a 1-sentence validation or architectural insight."}), websocket)
                await self.broadcast({"brain": b_res.content[0].text, "brain_source": "The Brain", "channel": "insight"})

    async def process_query(self, query, websocket):
        try:
            # 1. Clipboard Cache
            if self.should_cache_query(query):
                cache_res = await self.residents['archive'].call_tool("consult_clipboard", arguments={"query": query})
                if cache_res.content[0].text != "None":
                    await self.broadcast({"brain": f"[BRAIN_INSIGHT] [FROM CLIPBOARD] {cache_res.content[0].text}", "brain_source": "The Brain", "channel": "insight"})
                    return

            # 2. Pinky Triage
            res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": str(self.recent_interactions[-3:]), "memory": ""})
            import re
            raw_response = res.content[0].text
            m = re.search(r'\{.*\}', raw_response, re.DOTALL)
            
            if m:
                dec = json.loads(m.group(0))
                tool = dec.get("tool")
                params = dec.get("parameters", {})
                
                # --- VRAM GUARD FORCE STUB ---
                if os.environ.get("USE_BRAIN_STUB") == "1" and (tool in ["ask_brain", "query_brain"]):
                    await self.broadcast({"brain": "Narf! VRAM is too tight for the big guy. I'll handle this!", "brain_source": "Pinky"})
                    # In DEBUG_PINKY, we just return a stub text
                    if self.mode == "DEBUG_PINKY":
                        await self.broadcast({"brain": "[STUB] Quantum physics is the study of matter and energy at the most fundamental level.", "brain_source": "Pinky"})
                        return
                    await self.broadcast({"type": "debug", "event": "PINKY_THOUGHT", "data": dec})

                if tool == "reply_to_user":
                    await self.broadcast({"brain": params.get("text", "Poit!"), "brain_source": "Pinky"})
                
                elif tool in ["ask_brain", "query_brain"]:
                    # --- VRAM GUARD FALLBACK (STUB) ---
                    use_stub = os.environ.get("USE_BRAIN_STUB") == "1"
                    # Test-only override for integration verification
                    if "FORCE_STUB_TEST" in query: use_stub = True
                    
                    logging.info(f"[BRAIN] ask_brain triage. USE_BRAIN_STUB: {use_stub}")
                    
                    if use_stub:
                        await self.broadcast({"brain": "Narf! VRAM is too tight for the big guy. I'll handle this!", "brain_source": "Pinky"})
                        res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": f"The brain is offline. Please answer this yourself: {query}", "context": "", "memory": ""})
                        await self.broadcast({"brain": res.content[0].text, "brain_source": "Pinky"})
                        return

                    # --- BICAMERAL FALLBACK (OFFLINE) ---
                    if not await self.check_brain_health():
                        await self.broadcast({"brain": "Narf! The big guy is napping right now. I'll handle this!", "brain_source": "Pinky"})
                        res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": f"The brain is offline. Please answer this yourself: {query}", "context": "", "memory": ""})
                        await self.broadcast({"brain": res.content[0].text, "brain_source": "Pinky"})
                        return

                    summary = params.get("summary") or query
                    await self.broadcast({"brain": f"ASK_BRAIN: {summary}", "brain_source": "Pinky"})
                    
                    # Contextual Handover
                    handover = f"Context: Pinky just said '{raw_response[:200]}'. Task: {summary}"
                    brain_res = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": handover}), websocket)
                    brain_out = brain_res.content[0].text
                    await self.broadcast({"brain": brain_out, "brain_source": "The Brain", "channel": "insight"})
                    
                    # Synthesis with Weighted Banter
                    self.banter_ttl = 3.0 # Reset TTL for new thread
                    while self.banter_ttl > 0:
                        syn_query = f"The Brain said: '{brain_out[:300]}'. Give me your take, Pinky! (Banter TTL: {self.banter_ttl:.1f})"
                        syn_res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": syn_query, "context": brain_out, "memory": "Banter Mode"})
                        await self.broadcast({"brain": syn_res.content[0].text, "brain_source": "Pinky"})
                        
                        # Weighted Decay: Taper off naturally
                        self.banter_ttl -= random.uniform(1.0, 1.5)
                        if self.banter_ttl <= 0: break
                        
                        # Optional: One more condescending Brain remark if TTL allows
                        if self.banter_ttl > 0.5:
                            b_rem = await self.residents['brain'].call_tool("deep_think", arguments={"query": f"Pinky just said '{syn_res.content[0].text[:100]}'. Provide a brief, condescending technical correction."})
                            await self.broadcast({"brain": b_rem.content[0].text, "brain_source": "The Brain", "channel": "insight"})
                            self.banter_ttl -= 1.0

                else: # Other tools (shutdown, cv, etc)
                    try:
                        exec_res = await self.residents['pinky'].call_tool(tool, arguments=params)
                        await self.broadcast({"brain": exec_res.content[0].text, "brain_source": "Pinky"})
                    except: pass
            else:
                await self.broadcast({"brain": raw_response, "brain_source": "Pinky"})

            self.recent_interactions.append(query)
            if len(self.recent_interactions) > 10: self.recent_interactions.pop(0)

        except Exception as e:
            await self.broadcast({"brain": f"Narf! Error: {e}", "brain_source": "Pinky"})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    args = parser.parse_args()
    load_equipment()
    lab = AcmeLab()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(lab.boot_sequence(args.mode))
