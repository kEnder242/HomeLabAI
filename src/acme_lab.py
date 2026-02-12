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
VERSION = "3.4.19" # EarNode Enabled Attempt

# --- THE MONTANA PROTOCOL: Aggressive Logger Authority (Modified for Stderr Capture) ---
def reclaim_logger():
    root = logging.getLogger()
    for h in root.handlers[:]: root.removeHandler(h) # Clear all handlers
    
    fmt = logging.Formatter('%(asctime)s - [LAB] %(levelname)s - %(message)s')
    
    # Add StreamHandler to stderr only (lab_attendant will capture this)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    
    root.setLevel(logging.INFO)
    logging.info("[LOGGER] Reclaim_logger activated (stderr only).")

# Global Equipment State
EarNode = None
def load_equipment():
    global EarNode
    # --- Temporarily disable CuDNN for EarNode import debugging ---
    try:
        import torch
        torch.backends.cudnn.enabled = False
        logging.info("[EQUIP] torch.backends.cudnn.enabled = False (Temporary Debug)")
    except Exception as e:
        logging.warning(f"[EQUIP] Failed to set torch.backends.cudnn.enabled: {e}")

    try:
        from equipment.ear_node import EarNode
        logging.info("[EQUIP] EarNode module imported.")
    except Exception as e:
        logging.error(f"[EQUIP] EarNode import failed: {e}")
    reclaim_logger() # Re-reclaim after potential hijacks

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

    async def manage_session_lock(self, active=True):
        try:
            if active:
                os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
                with open(self.lock_path, "w") as f: f.write(str(os.getpid()))
                self.last_activity = time.time()
                logging.info(f"[LOCK] Intercom Active (PID {os.getpid()}).")
            else:
                if os.path.exists(self.lock_path): os.remove(self.lock_path)
                logging.info(f"[LOCK] Intercom Idle.")
        except Exception: pass

    async def broadcast(self, message_dict):
        if not self.connected_clients: return
        if message_dict.get("type") == "status": message_dict["version"] = VERSION
        message = json.dumps(message_dict)
        for ws in list(self.connected_clients):
            try: await ws.send_str(message)
            except Exception: pass

    async def monitor_task_with_tics(self, coro, websocket, delay=2.0):
        """Emits nervous tics during long reasoning tasks to fill dead air."""
        task = asyncio.create_task(coro)
        tics = ["Poit!", "Narf!", "Just a moment...", "Thinking...", "Checking archives...", "Zort!"]
        while not task.done():
            done, pending = await asyncio.wait([task], timeout=delay)
            if task in done: return task.result()
            tic = random.choice(tics)
            await self.broadcast({"brain": tic, "brain_source": "Pinky (Reflex)"})
            delay = min(delay * 1.5, 5.0) 
        return task.result()

    def should_cache_query(self, query: str) -> bool:
        """Determines if a query is safe to cache (not time-sensitive)."""
        forbidden = ["time", "date", "status", "now", "latest", "news", "update"]
        q_lower = query.lower()
        return not any(word in q_lower for word in forbidden)

    async def load_residents_and_equipment(self):
        """Sequential initialization with Lobby updates."""
        logging.info(f"[BUILD] Loading Residents (v{VERSION})...")
        
        a_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
        p_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/pinky_node.py"])
        b_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

        try:
            # 1. Archive Node
            self.status = "LOBBY (Archive Connecting)"
            await self.broadcast({"type": "status", "state": "lobby", "message": "Opening Filing Cabinet..."})
            async with stdio_client(a_p) as (ar, aw):
                async with ClientSession(ar, aw) as archive:
                    await archive.initialize()
                    self.residents['archive'] = archive
                    logging.info("[LAB] Archive Connected.")
                    self.status = "LOBBY (Archive Ready)"
                    await self.broadcast({"type": "status", "state": "lobby", "message": "Filing Cabinet Open."})


                    # 2. Pinky Node
                    await asyncio.sleep(2) # OS Buffer settling
                    self.status = "LOBBY (Pinky Connecting)"
                    logging.info("[LOBBY] Connecting Pinky...")
                    await self.broadcast({"type": "status", "state": "lobby", "message": "Waking Pinky..."})
                    async with stdio_client(p_p) as (pr, pw):
                        async with ClientSession(pr, pw) as pinky:
                            await pinky.initialize()
                            self.residents['pinky'] = pinky
                            logging.info("[LAB] Pinky Connected.")
                            self.status = "LOBBY (Pinky Ready)"
                            await self.broadcast({"type": "status", "state": "lobby", "message": "Pinky Alert."})


                            # 3. Brain Node
                            await asyncio.sleep(2)
                            self.status = "LOBBY (Brain Connecting)"
                            logging.info("[LOBBY] Connecting Brain...")
                            await self.broadcast({"type": "status", "state": "lobby", "message": "Consulting the Architect..."})
                            async with stdio_client(b_p) as (br, bw):
                                async with ClientSession(br, bw) as brain:
                                    await brain.initialize()
                                    self.residents['brain'] = brain
                                    logging.info("[LAB] Brain Connected.")
                                    self.status = "LOBBY (Brain Ready)"
                                    await self.broadcast({"type": "status", "state": "lobby", "message": "Brain Online."})

                                    if self.shutdown_event.is_set(): return

                                    # 4. Async EarNode
                                    if EarNode:
                                        self.status = "LOBBY (Ear Loading)"
                                        logging.info("[BUILD] Starting EarNode background load...")
                                        asyncio.create_task(self.background_load_ear())
                                    else:
                                        logging.info("[STT] EarNode not available (import failed or disabled by env).")

                                    self.status = "READY"
                                    logging.info("[READY] Lab is Open (Lobby Active).")
                                    await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Open."})
                                    
                                    await self.shutdown_event.wait()

        except Exception as e:
            logging.error(f"[FATAL] Startup Failure: {e}")
        finally:
            logging.info("[FINISH] LAB SHUTDOWN")
            os._exit(0)

    async def background_load_ear(self):
        try:
            self.ear = await asyncio.to_thread(EarNode, callback=None)
            logging.info("[STT] EarNode Ready.")
            await self.broadcast({"type": "status", "state": "ready", "message": "EarNode Online."})
        except Exception as e:
            logging.error(f"[STT] Load Failed: {e}")

    async def prime_brain(self):
        """Wakes up the Brain's GPU model."""
        if 'brain' in self.residents:
            try:
                logging.info("[BRAIN] Priming Brain (wake_up)...")
                await self.residents['brain'].call_tool("wake_up")
                logging.info("[BRAIN] Brain Primed.")
            except Exception as e:
                logging.warning(f"[BRAIN] Priming failed: {e}")

    async def boot_sequence(self, mode):
        self.mode = mode
        app = web.Application()
        app.add_routes([web.get('/', self.client_handler)]) 
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', PORT).start()
        logging.info(f"[BOOT] Mode: {mode} | Door: {PORT} (SERVER STARTED)")
        await self.load_residents_and_equipment()

    async def client_handler(self, request): # FULL CLIENT HANDLER
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connected_clients.add(ws)
        await self.manage_session_lock(active=True)
        
        logging.info("[LOBBY] Client entered. Poking Brain...")
        asyncio.create_task(self.prime_brain())
        
        audio_buffer = np.zeros(0, dtype=np.int16)
        BUFFER_SAMPLES = 24000 # 1.5s @ 16kHz
        OVERLAP_SAMPLES = 8000 # 0.5s @ 16kHz

        try:
            await ws.send_str(json.dumps({"type": "status", "version": VERSION, "state": "ready" if self.status == "READY" else "lobby", "message": "Lab foyer is open."}))
            
            async def ear_poller():
                while not ws.closed:
                    if self.ear:
                        query = self.ear.check_turn_end()
                        if query:
                            logging.info(f"[EAR] Transcription Finished: {query}")
                            await self.broadcast({"type": "final", "text": query})
                            asyncio.create_task(self.process_query(query, ws))
                    await asyncio.sleep(0.1)
            
            poller_task = asyncio.create_task(ear_poller())

            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(message.data)
                        if data.get("type") == "handshake":
                            if 'archive' in self.residents:
                                res = await self.residents['archive'].call_tool("list_cabinet")
                                await ws.send_str(json.dumps({"type": "cabinet", "files": json.loads(res.content[0].text)}))
                        elif data.get("type") == "text_input":
                            if self.status != "READY":
                                await ws.send_str(json.dumps({"brain": "Narf! Still warming up...", "brain_source": "Pinky"}))
                                continue
                            query = data.get("content", "")
                            logging.info(f"[USER] Intercom Input: {query}")
                            asyncio.create_task(self.prime_brain())
                            self.current_processing_task = asyncio.create_task(self.process_query(query, ws))
                    except Exception: pass
                
                elif message.type == aiohttp.WSMsgType.BINARY:
                    if self.ear:
                        chunk = np.frombuffer(message.data, dtype=np.int16)
                        audio_buffer = np.concatenate((audio_buffer, chunk))
                        
                        if len(audio_buffer) >= BUFFER_SAMPLES:
                            window = audio_buffer[:BUFFER_SAMPLES]
                            text = self.ear.process_audio(window)
                            if text:
                                await self.broadcast({"text": text})
                            audio_buffer = audio_buffer[BUFFER_SAMPLES - OVERLAP_SAMPLES:]

        finally:
            if 'poller_task' in locals(): poller_task.cancel()
            if ws in self.connected_clients: self.connected_clients.remove(ws)
            if not self.connected_clients:
                await self.manage_session_lock(active=False)
                if self.mode != "SERVICE_UNATTENDED": self.shutdown_event.set()
        return ws

    async def process_query(self, query, websocket): # FULL PROCESS_QUERY
        try:
            # 1. Check Semantic Clipboard (Fast Cache)
            if self.should_cache_query(query):
                cache_res = await self.residents['archive'].call_tool("consult_clipboard", arguments={"query": query})
                if cache_res.content[0].text != "None":
                    await self.broadcast({"brain": f"[BRAIN_INSIGHT] [FROM CLIPBOARD] {cache_res.content[0].text}", "brain_source": "The Brain", "channel": "insight"})
                    return

            # 2. Ask Pinky to triage/facilitate
            res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": "", "memory": ""})
            
            # Extract JSON from Pinky's response
            import re
            raw_response = res.content[0].text
            logging.info(f"[DEBUG] Pinky Raw Response: {raw_response[:200]}...")
            
            m = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if m:
                try:
                    dec = json.loads(m.group(0))
                    tool = dec.get("tool")
                    params = dec.get("parameters", {})
                    
                    # --- NEW: Debug Thought for UI ---
                    if tool != "facilitate":
                        await self.broadcast({"type": "debug", "event": "PINKY_THOUGHT", "data": dec})

                    # 3. Handle Decisions
                    if tool == "reply_to_user":
                        text = params.get("text", "Poit!")
                        await self.broadcast({"brain": text, "brain_source": "Pinky"})
                    
                    elif tool == "lab_shutdown":
                        await self.broadcast({"brain": "Poit! Shutting down the lab...", "brain_source": "Pinky"})
                        res = await self.residents['archive'].call_tool("shutdown_lab")
                        if res.content[0].text == "SIGNAL_SHUTDOWN": self.shutdown_event.set()

                    elif tool == "delegate_internal_debate":
                        instruction = params.get("instruction", query)
                        await self.broadcast({"brain": "Initiating moderated consensus... Zort!", "brain_source": "Pinky"})
                        path_a = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": instruction}), websocket)
                        path_b = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": instruction}), websocket)
                        mod_prompt = f"Moderator: Reconcile these two technical paths for '{instruction}':\nA: {path_a.content[0].text}\nB: {path_b.content[0].text}"
                        final_res = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": mod_prompt}), websocket)
                        await self.broadcast({"brain": final_res.content[0].text, "brain_source": "The Brain", "channel": "insight"})

                    elif tool == "build_cv_summary":
                        year = params.get("year", "2024")
                        cv_ctx = await self.residents['archive'].call_tool("get_cv_context", arguments={"year": year})
                        cv_prompt = f"Build a 3x3 CVT summary for {year} based on:\n{cv_ctx.content[0].text}"
                        final_res = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": cv_prompt}), websocket)
                        await self.broadcast({"brain": final_res.content[0].text, "brain_source": "The Brain", "channel": "insight"})

                    elif tool == "get_recent_dream":
                        res = await self.residents['archive'].call_tool("get_recent_dream")
                        await self.broadcast({"brain": res.content[0].text, "brain_source": "Pinky"})

                    elif tool in ["ask_brain", "query_brain"]:
                        summary = params.get("summary") or params.get("question") or query
                        await self.broadcast({"brain": f"ASK_BRAIN: {summary}", "brain_source": "Pinky"})
                        brain_res = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": summary}), websocket)
                        brain_out = brain_res.content[0].text
                        await self.broadcast({"brain": brain_out, "brain_source": "The Brain", "channel": "insight"})
                        
                        # --- PINKY SYNTHESIS ---
                        await self.broadcast({"brain": "Synthesizing... Poit!", "brain_source": "Pinky"})
                        syn_query = f"The Brain provided this data: '{brain_out[:500]}'. Please summarize the core technical insight for the user in your signature style. NARF!"
                        syn_res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": syn_query, "context": brain_out, "memory": "You just consulted the Brain."})
                        
                        # Extract and broadcast Pinky's final word
                        raw_syn = syn_res.content[0].text
                        ms = re.search(r'\{.*\}', raw_syn, re.DOTALL)
                        if ms:
                            try:
                                d_syn = json.loads(ms.group(0))
                                final_text = d_syn.get("parameters", {}).get("text", raw_syn)
                                await self.broadcast({"brain": final_text, "brain_source": "Pinky"})
                            except: await self.broadcast({"brain": raw_syn, "brain_source": "Pinky"})
                        else:
                            await self.broadcast({"brain": raw_syn, "brain_source": "Pinky"})

                        if self.should_cache_query(summary):
                            await self.residents['archive'].call_tool("scribble_note", arguments={"query": summary, "response": brain_out})
                    
                    else:
                        await self.broadcast({"type": "debug", "event": "PINKY_UNMAPPED_TOOL", "data": dec})
                        try:
                            res = await self.residents['pinky'].call_tool(tool, arguments=params)
                            await self.broadcast({"brain": res.content[0].text, "brain_source": "Pinky"})
                        except:
                            res = await self.residents['pinky'].call_tool("facilitate", arguments={"query": f"You tried to use tool '{tool}' but it is unavailable. Just talk to me.", "context": "", "memory": ""})
                            await self.broadcast({"brain": res.content[0].text, "brain_source": "Pinky"})
                except Exception as je:
                    logging.error(f"[ERR] JSON Parse failed: {je}")
                    await self.broadcast({"brain": raw_response, "brain_source": "Pinky"})
            else:
                await self.broadcast({"brain": raw_response, "brain_source": "Pinky"})

        except Exception as e: 
            logging.error(f"[ERR] process_query failed: {e}")
            await self.broadcast({"brain": f"Narf! Something went wrong: {e}", "brain_source": "Pinky"})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    args = parser.parse_args()
    print(f"--- [RESTART_MARKER] BOOT_ID: {time.time():.4f} ---", flush=True)
    load_equipment()
    lab = AcmeLab()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try: loop.run_until_complete(lab.boot_sequence(args.mode))
    except KeyboardInterrupt: pass
