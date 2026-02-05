import asyncio
import websockets
import json
import logging
import argparse
import sys
import numpy as np
import random
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import os

# Equipment
if os.environ.get("DISABLE_EAR") == "1":
    logging.info("[CONFIG] EarNode disabled via env var.")
    EarNode = None
else:
    try:
        from equipment.ear_node import EarNode
    except ImportError:
        logging.warning("[STT] EarNode dependencies missing. Voice input will be unavailable.")
        EarNode = None

# Configuration
PORT = 8765
PYTHON_PATH = sys.executable
VERSION = "2.1.0"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [LAB] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class AcmeLab:
    NERVOUS_TICS = [
        "Thinking... Narf!",
        "Consulting the Big Guy...",
        "One moment, the Brain is loading...",
        "Processing... Poit!",
        "Just a second... Zort!",
        "Checking the archives...",
        "Egad, this is heavy math...",
        "Stand by..."
    ]

    def __init__(self, afk_timeout=None):
        self.residents = {}
        self.ear = None
        self.mode = "HOSTING"
        self.status = "BOOTING"
        self.connected_clients = set()
        self.shutdown_event = asyncio.Event()
        self.current_processing_task = None
        self.afk_timeout = afk_timeout

    async def afk_watcher(self):
        """Shuts down the Lab if no client connects within the timeout."""
        if not self.afk_timeout: return
        
        logging.info(f"[AFK] Watcher started (Timeout: {self.afk_timeout}s).")
        await asyncio.sleep(self.afk_timeout)
        
        if not self.connected_clients and not self.shutdown_event.is_set():
            logging.warning("[AFK] No client connected. Shutting down.")
            self.shutdown_event.set()

    async def broadcast(self, message_dict):
        """Sends a JSON message to all connected clients."""
        if not self.connected_clients: return
        # Ensure version is in status broadcasts
        if message_dict.get("type") == "status":
            message_dict["version"] = VERSION
        
        message = json.dumps(message_dict)
        for ws in self.connected_clients:
            try:
                await ws.send(message)
            except: pass

    async def monitor_task_with_tics(self, coro, websocket, delay=2.0):
        """
        Wraps a coroutine (like a Brain call). If it takes longer than 'delay',
        starts sending 'Nervous Tics' to the user to fill dead air.
        """
        task = asyncio.create_task(coro)
        
        while not task.done():
            # Wait for either task completion or the delay
            done, pending = await asyncio.wait([task], timeout=delay)
            
            if task in done:
                return task.result()
            
            # If we are here, the task is still running after 'delay'
            tic = random.choice(self.NERVOUS_TICS)
            logging.info(f"[TIC] Emitting: {tic}")
            try:
                await websocket.send(json.dumps({"brain": tic, "brain_source": "Pinky (Reflex)"}))
            except: pass
            
            # Increase delay slightly for next tic to avoid spamming (backoff)
            delay = min(delay * 1.5, 5.0) 
            
        return task.result()

    def should_cache_query(self, query: str) -> bool:
        """Determines if a query is safe to cache (not time-sensitive)."""
        forbidden_words = ["time", "date", "weather", "status", "current", "now", "latest", "news", "update", "schedule"]
        q_lower = query.lower()
        for word in forbidden_words:
            # Simple word boundary check would be better, but substring is safer for now
            if word in q_lower:
                return False
        return True

    async def load_residents_and_equipment(self):
        """The Heavy Lifting: Connects MCP nodes and loads ML models."""
        logging.info(f"[BUILD] Loading Residents & Equipment (v{VERSION})...")
        
        archive_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
        pinky_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/pinky_node.py"])
        brain_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

        try:
            async with stdio_client(archive_params) as (ar, aw), \
                       stdio_client(pinky_params) as (pr, pw), \
                       stdio_client(brain_params) as (br, bw):
                
                async with ClientSession(ar, aw) as archive, \
                           ClientSession(pr, pw) as pinky, \
                           ClientSession(br, bw) as brain:
                    
                    await archive.initialize()
                    await pinky.initialize()
                    await brain.initialize()
                    
                    self.residents['archive'] = archive
                    self.residents['pinky'] = pinky
                    self.residents['brain'] = brain
                    logging.info("[LAB] Residents Connected.")

                    if self.shutdown_event.is_set(): return

                    # 2. EarNode (Heavy ML Load)
                    if EarNode:
                        logging.info("[BUILD] Loading EarNode in background thread...")
                        self.ear = await asyncio.to_thread(EarNode, callback=None)
                        logging.info("[STT] EarNode Initialized.")
                    else:
                        logging.warning("[STT] EarNode skipped (missing dependencies).")

                    if self.shutdown_event.is_set(): return

                    # 3. Prime Brain (Mode Logic)
                    if self.mode == "DEBUG_BRAIN":
                        logging.info("[BRAIN] Priming Brain...")
                        await brain.call_tool("wake_up")
                        logging.info("[BRAIN] Brain Primed.")

                    if self.shutdown_event.is_set(): return

                    # 4. SIGNAL READY
                    self.status = "READY"
                    logging.info("[READY] Lab is Fully Operational!")
                    await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Open."})

                    # 5. Start AFK Watcher (Only after ready)
                    asyncio.create_task(self.afk_watcher())

                    # 6. Wait for voice-triggered shutdown
                    await self.shutdown_event.wait()
                    logging.info("[STOP] Shutdown Event Triggered.")

        except Exception as e:
            import traceback
            logging.error(f"[ERROR] Lab Explosion: {e}")
            logging.error(traceback.format_exc())
        finally:
            logging.info("[FINISH] LAB SHUTDOWN COMPLETE")
            import os
            os._exit(0)

    async def boot_sequence(self, mode):
        self.mode = mode
        logging.info(f"[LAB] Acme Lab Booting (Mode: {mode})...")

        async with websockets.serve(self.client_handler, "0.0.0.0", PORT):
            logging.info(f"[DOOR] Lab Doors Open on Port {PORT}")
            
            # Run the main application logic (blocks until shutdown)
            await self.load_residents_and_equipment()

    async def client_handler(self, websocket):
        self.connected_clients.add(websocket)
        logging.info("[LAB] Client entered the Lobby.")
        
        status_msg = {"type": "status", "version": VERSION}
        if self.status == "BOOTING":
            status_msg.update({"state": "waiting", "message": "Elevator... Ding! Loading..."})
        else:
            status_msg.update({"state": "ready", "message": "Lab is Open."})
        
        await websocket.send(json.dumps(status_msg))

        audio_buffer = np.zeros(0, dtype=np.int16)
        try:
            async for message in websocket:
                if self.status != "READY": continue

                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        if "debug_text" in data:
                            query = data["debug_text"]
                            if query == "SHUTDOWN_PROTOCOL_OVERRIDE":
                                logging.info("[TEST] Remote Shutdown Received.")
                                if self.mode in ["HOSTING"]:
                                    logging.warning("[SECURITY] Remote Shutdown Ignored in HOSTING mode.")
                                else:
                                    self.shutdown_event.set()
                                break
                            
                            if query == "BARGE_IN":
                                if self.current_processing_task and not self.current_processing_task.done():
                                    logging.info("[BARGE-IN] Manual interrupt received.")
                                    self.current_processing_task.cancel()
                                continue

                            # Cancel existing task if a new debug_text query comes in
                            if self.current_processing_task and not self.current_processing_task.done():
                                logging.info("[BARGE-IN] New query received. Cancelling previous task.")
                                self.current_processing_task.cancel()
                            
                            self.current_processing_task = asyncio.create_task(self.process_query(query, websocket))
                        
                        elif data.get("type") == "handshake":
                            client_ver = data.get("version", "0.0.0")
                            if client_ver != VERSION:
                                logging.error(f"❌ [VERSION MISMATCH] Client ({client_ver}) != Server ({VERSION}). Connection Refused.")
                                await websocket.send(json.dumps({"brain": f"SYSTEM ALERT: Client outdated ({client_ver}). Please update.", "brain_source": "System"}))
                                
                                if self.mode in ["SERVICE"]:
                                    await websocket.close()
                                else:
                                    # Fail Fast in Debug Mode
                                    logging.info("[DEBUG] Mismatch triggered Fail-Fast Shutdown.")
                                    self.shutdown_event.set()
                                return
                            else:
                                logging.info(f"[HANDSHAKE] Client verified (v{client_ver}).")

                        elif data.get("type") == "text_input":
                            query = data.get("content", "")
                            logging.info(f"[TEXT] Rx: {query}")
                            
                            # Interrupt Logic (Barge-In)
                            if self.current_processing_task and not self.current_processing_task.done():
                                logging.info("[BARGE-IN] Text input received. Interrupting...")
                                self.current_processing_task.cancel()

                            # Start Processing
                            self.current_processing_task = asyncio.create_task(self.process_query(query, websocket))

                    except: pass
                    continue

                chunk = np.frombuffer(message, dtype=np.int16)
                if self.ear:
                    audio_buffer = np.concatenate((audio_buffer, chunk))
                    
                    if len(audio_buffer) >= 24000:
                        window = audio_buffer[:24000]
                        text = self.ear.process_audio(window)
                        if text:
                            logging.info(f"[STT] Tx: {text}")
                            # BARGE-IN on Speech Detection
                            if self.current_processing_task and not self.current_processing_task.done():
                                logging.info("[BARGE-IN] Speech detected. Interrupting...")
                                self.current_processing_task.cancel()
                                await websocket.send(json.dumps({"type": "control", "command": "stop_audio"}))

                            await websocket.send(json.dumps({"text": text}))
                        audio_buffer = audio_buffer[24000-8000:] 

                    query = self.ear.check_turn_end()
                    if query:
                        logging.info(f"[MIC] TURN COMPLETE: '{query}'")
                        await websocket.send(json.dumps({"type": "final", "text": query}))
                        self.current_processing_task = asyncio.create_task(self.process_query(query, websocket))
                else:
                    # No ear, just ignore audio chunks
                    pass

        except websockets.exceptions.ConnectionClosed:
            logging.info("[LAB] Client left the Lobby.")
        finally:
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)
            
            # Auto-Shutdown in Debug Modes
            if self.mode != "HOSTING" and len(self.connected_clients) == 0:
                logging.info("[DEBUG] Last client disconnected. Shutting down Lab.")
                self.shutdown_event.set()

    async def process_query(self, query, websocket):
        """The Main Lab Logic Router (Round Table Loop)."""
        logging.info(f"[LAB] New Round Table Session: '{query}'")
        
        try:
            # 1. Initialize Context
            lab_context = f"User: {query}"
            turn_count = 0
            MAX_TURNS = 10 

            # --- NEW: SEMANTIC ROUTING (FAST PATH) ---
            routing_res = await self.residents['archive'].call_tool("classify_intent", arguments={"query": query})
            routing_data = json.loads(routing_res.content[0].text) if routing_res.content else {}
            
            if routing_data.get("target") == "BRAIN":
                logging.info(f"[LAB] Semantic Routing: FAST-PATH to BRAIN (Confidence: {routing_data.get('confidence')})")
                await self.broadcast({"type": "debug", "event": "LAB_ROUTING", "data": "FAST-PATH: Brain Mode"})
                
                # Directly execute the Brain delegation logic
                # We reuse the same loop structure but force the first decision
                decision = {"tool": "delegate_to_brain", "parameters": {"instruction": query}}
            else:
                logging.info(f"[LAB] Semantic Routing: CHAT-PATH to PINKY (Confidence: {routing_data.get('confidence')})")
                decision = None

            while turn_count < MAX_TURNS:
                turn_count += 1
                
                # 1.5 Retrieve Wisdom (Memory)
                memory_hit = await self.residents['archive'].call_tool("get_context", arguments={"query": query, "n_results": 2})
                memory_text = memory_hit.content[0].text if memory_hit and memory_hit.content else ""
                
                # 2. Decision Logic
                if not decision:
                    result = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": lab_context, "memory": memory_text})
                    decision_text = result.content[0].text
                    
                    try:
                        decision = json.loads(decision_text)
                    except json.JSONDecodeError:
                        logging.warning(f"[PINKY] Invalid JSON: {decision_text}")
                        decision = {"tool": "reply_to_user", "parameters": {"text": decision_text, "mood": "confused"}}

                tool = decision.get("tool")
                params = decision.get("parameters", {})
                
                # Robustness: Ensure params is a dict
                if not isinstance(params, dict):
                    logging.warning(f"[PINKY] Params is not a dict: {params}")
                    params = {"instruction": str(params)} if tool == "delegate_to_brain" else {"text": str(params)}

                # Broadcast Debug Event
                await self.broadcast({"type": "debug", "event": "PINKY_DECISION", "data": decision})
                logging.info(f"[PINKY] Decision: {tool}")

                # 3. Execute Decision
                if tool == "reply_to_user":
                    text = params.get("text", "Narf!")
                    await websocket.send(json.dumps({"brain": text, "brain_source": "Pinky"}))
                    break # End of Turn

                elif tool == "delegate_to_brain":
                    instruction = params.get("instruction", query)
                    ignore_clipboard = params.get("ignore_clipboard", False)
                    target_tool = params.get("tool", "deep_think")
                    
                    # Fix: Inject memory_text into the brain's context if available
                    augmented_context = lab_context
                    if memory_text:
                        augmented_context = f"Relevant Archives:\n{memory_text}\n\nCurrent Context:\n{lab_context}"

                    tool_args = params.get("args", {"query": instruction, "context": augmented_context})
                    
                    logging.info(f"[BRAIN] Delegated: {instruction}")
                    if memory_text:
                        logging.info("[DEBUG] RAG Data present in Brain context.")
                    else:
                        logging.info("[DEBUG] No RAG Data for this turn.")
                    
                    # --- CLIPBOARD CHECK ---
                    brain_out = None
                    is_cacheable = self.should_cache_query(instruction)
                    
                    if is_cacheable and not ignore_clipboard and target_tool == "deep_think":
                        try:
                            cache_res = await self.residents['archive'].call_tool("consult_clipboard", arguments={"query": instruction})
                            if cache_res and cache_res.content and cache_res.content[0].text != "None":
                                raw_answer = cache_res.content[0].text
                                brain_out = f"[FROM CLIPBOARD] {raw_answer}"
                                logging.info("[BRAIN] Clipboard Found Note! Skipping inference.")
                                await self.broadcast({"type": "debug", "event": "CLIPBOARD_HIT", "data": "Served from Semantic Clipboard"})
                        except Exception as e:
                            logging.warning(f"[CLIPBOARD] Check failed: {e}")
                    elif ignore_clipboard:
                        logging.info("[CLIPBOARD] Forced Skip (User Request).")
                    else:
                        logging.info("[CLIPBOARD] Skipping check for volatile query or specific tool.")

                    if not brain_out:
                        # Call the Brain tool (Real or Mock)
                        if self.mode == "MOCK_BRAIN":
                            async def mock_brain_task():
                                await asyncio.sleep(2.0)
                                return type('obj', (object,), {'content': [type('obj', (object,), {'text': f"MOCK RESULT: Processed {target_tool} with {tool_args}"})]})()
                            brain_res = await self.monitor_task_with_tics(mock_brain_task(), websocket)
                        else:
                            brain_res = await self.monitor_task_with_tics(
                                self.residents['brain'].call_tool(target_tool, arguments=tool_args),
                                websocket
                            )
                        
                        brain_out = brain_res.content[0].text
                        
                        # --- SCRIBBLE NOTE (Only for standard thinking) ---
                        if is_cacheable and target_tool == "deep_think":
                            try:
                                await self.residents['archive'].call_tool("scribble_note", arguments={"query": instruction, "response": brain_out})
                            except Exception as e:
                                logging.warning(f"[CLIPBOARD] Scribble failed: {e}")

                    # Add to context and continue loop
                    lab_context += f"\nBrain: {brain_out}"
                    logging.info(f"[BRAIN] Output: {brain_out[:100]}...") # Log first 100 chars
                    await self.broadcast({"type": "debug", "event": "BRAIN_OUTPUT", "data": brain_out})
                    
                    # IMPORTANT: After Brain speaks, Pinky gets a turn to summarize or closing remark
                    decision = None # Force re-evaluation by Pinky for the next turn

                elif tool == "critique_brain":
                    feedback = params.get("feedback", "Try again.")
                    logging.info(f"[PINKY] Critique: {feedback}")
                    lab_context += f"\nPinky (Critique): {feedback}"
                    decision = None # Loop back
                
                elif tool == "manage_lab":
                    action = params.get("action", "")
                    message = params.get("message", "Closing Lab...")
                    
                    if action == "shutdown":
                         await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))
                         self.shutdown_event.set()
                         break
                
                elif tool == "add_routing_anchor":
                    target = params.get("target", "BRAIN")
                    anchor_text = params.get("anchor_text", "")
                    res = await self.residents['archive'].call_tool("add_routing_anchor", arguments={"target": target, "anchor_text": anchor_text})
                    msg = res.content[0].text
                    logging.info(f"[ROUTER] Anchor Added: {msg}")
                    await websocket.send(json.dumps({"brain": f"Teacher Pinky says: {msg}", "brain_source": "System"}))
                    decision = None # Continue loop
                
                else:
                    logging.warning(f"[LAB] Unknown Tool: {tool}")
                    break

        except asyncio.CancelledError:
            logging.info(f"[LAB] Session '{query}' was CANCELLED (Barge-In).")
            try:
                await websocket.send(json.dumps({"brain": "Stopping... Narf!", "brain_source": "Pinky"}))
            except: pass
            raise 
        except Exception as e:
            logging.error(f"[ERROR] Loop Exception: {e}")
            await websocket.send(json.dumps({"brain": f"Lab Error: {e}", "brain_source": "System"}))

import signal

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="HOSTING", choices=["HOSTING", "DEBUG_BRAIN", "DEBUG_PINKY", "MOCK_BRAIN"])
    parser.add_argument("--afk-timeout", type=int, default=None, help="Shutdown if no client connects within N seconds.")
    args = parser.parse_args()

    lab = AcmeLab(afk_timeout=args.afk_timeout)
    
    def handle_sigint():
        logging.info("[SIGNAL] Caught SIGINT/SIGTERM. Shutting down...")
        if not lab.shutdown_event.is_set():
            lab.shutdown_event.set()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    loop.add_signal_handler(signal.SIGINT, handle_sigint)
    loop.add_signal_handler(signal.SIGTERM, handle_sigint)
    if hasattr(signal, 'SIGHUP'):
        loop.add_signal_handler(signal.SIGHUP, handle_sigint)

    try:
        loop.run_until_complete(lab.boot_sequence(args.mode))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logging.info("Exiting...")
