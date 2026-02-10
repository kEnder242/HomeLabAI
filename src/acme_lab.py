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
VERSION = "3.1.9"

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
        self.mode = "SERVICE_UNATTENDED"
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
                await ws.send_str(message)
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
                await websocket.send_str(json.dumps({"brain": tic, "brain_source": "Pinky (Reflex)"}))
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

        app = web.Application()
        app.add_routes([web.get('/', self.client_handler)])
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        
        logging.info(f"[DOOR] Lab Doors Open on Port {PORT}")
        
        # Run the main application logic (blocks until shutdown)
        await self.load_residents_and_equipment()

    async def client_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.connected_clients.add(ws)
        logging.info("[LAB] Client entered the Lobby.")
        
        status_msg = {"type": "status", "version": VERSION}
        if self.status == "BOOTING":
            status_msg.update({"state": "waiting", "message": "Elevator... Ding! Loading..."})
        else:
            status_msg.update({"state": "ready", "message": "Lab is Open."})
        
        await ws.send_str(json.dumps(status_msg))

        audio_buffer = np.zeros(0, dtype=np.int16)
        last_heartbeat = time.time()
        try:
            async for message in ws:
                # Heartbeat for audio troubleshooting
                if time.time() - last_heartbeat > 5.0:
                    logging.info(f"[MIC] Heartbeat... Buffer size: {len(audio_buffer)}")
                    last_heartbeat = time.time()

                if message.type == aiohttp.WSMsgType.TEXT:
                    if self.status != "READY": continue
                    
                    try:
                        data = json.loads(message.data)
                        if "debug_text" in data:
                            query = data["debug_text"]
                            
                            if query == "BARGE_IN":
                                if self.current_processing_task and not self.current_processing_task.done():
                                    logging.info("[BARGE-IN] Manual interrupt received.")
                                    self.current_processing_task.cancel()
                                continue

                            # Cancel existing task if a new debug_text query comes in
                            if self.current_processing_task and not self.current_processing_task.done():
                                logging.info("[BARGE-IN] New query received. Cancelling previous task.")
                                self.current_processing_task.cancel()
                            
                            self.current_processing_task = asyncio.create_task(self.process_query(query, ws))
                        
                        elif data.get("type") == "handshake":
                            client_ver = data.get("version", "0.0.0")
                            if client_ver != VERSION:
                                error_msg = f"VERSION MISMATCH: Client ({client_ver}) != Server ({VERSION})."
                                logging.error(f"❌ {error_msg}")
                                await ws.send_str(json.dumps({"brain": error_msg, "brain_source": "System"}))
                                await ws.close()
                                return ws
                            else:
                                logging.info(f"[HANDSHAKE] Client verified (v{client_ver}).")

                        elif data.get("type") == "text_input":
                            query = data.get("content", "")
                            logging.info(f"[TEXT] Rx: {query}")
                            
                            # Echo back to client for UI consistency (Deduplicated in Web Intercom)
                            await ws.send_str(json.dumps({"type": "final", "text": query, "source": "text"}))
                            
                            # Interrupt Logic (Barge-In)
                            if self.current_processing_task and not self.current_processing_task.done():
                                logging.info("[BARGE-IN] Text input received. Interrupting...")
                                self.current_processing_task.cancel()

                            # Start Processing
                            self.current_processing_task = asyncio.create_task(self.process_query(query, ws))

                    except: pass

                elif message.type == aiohttp.WSMsgType.BINARY:
                    if self.status != "READY": continue
                    
                    chunk = np.frombuffer(message.data, dtype=np.int16)
                    if self.ear:
                        audio_buffer = np.concatenate((audio_buffer, chunk))
                        
                        # Increased buffer window from 24000 to 32000 to satisfy model context
                        if len(audio_buffer) >= 32000:
                            window = audio_buffer[:32000]
                            text = self.ear.process_audio(window)
                            if text:
                                logging.info(f"[STT] Tx: {text}")
                                # BARGE-IN on Speech Detection
                                if self.current_processing_task and not self.current_processing_task.done():
                                    logging.info("[BARGE-IN] Speech detected. Interrupting...")
                                    self.current_processing_task.cancel()
                                    await ws.send_str(json.dumps({"type": "control", "command": "stop_audio"}))

                                await ws.send_str(json.dumps({"text": text}))
                            audio_buffer = audio_buffer[32000-8000:] 

                        query = self.ear.check_turn_end()
                        if query:
                            logging.info(f"[MIC] TURN COMPLETE: '{query}'")
                            await ws.send_str(json.dumps({"type": "final", "text": query}))
                            self.current_processing_task = asyncio.create_task(self.process_query(query, ws))
                    else:
                        # No ear, just ignore audio chunks
                        pass

        except Exception as e:
            logging.error(f"[LAB] Connection Error: {e}")
        finally:
            if ws in self.connected_clients:
                self.connected_clients.remove(ws)
            
            # Auto-Shutdown in Debug Modes
            if self.mode != "SERVICE_UNATTENDED" and len(self.connected_clients) == 0:
                logging.info("[DEBUG] Last client disconnected. Shutting down Lab.")
                self.shutdown_event.set()
        
        return ws

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
                    decision_text = result.content[0].text if result and result.content else ""
                    
                    if not decision_text.strip():
                        logging.warning("[PINKY] Empty response from model. Falling back to default greeting.")
                        decision = {"tool": "reply_to_user", "parameters": {"text": "Narf! I'm a bit lost. What was that?", "mood": "confused"}}
                    else:
                        try:
                            decision = json.loads(decision_text)
                        except json.JSONDecodeError:
                            logging.warning(f"[PINKY] Invalid JSON: {decision_text}")
                            decision = {"tool": "reply_to_user", "parameters": {"text": "Egad! My thoughts are a jumble!", "mood": "confused"}}

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
                    await websocket.send_str(json.dumps({"brain": text, "brain_source": "Pinky"}))
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
                        try:
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
                        except Exception as e:
                            logging.error(f"[BRAIN] Connection Failed: {e}")
                            brain_out = f"[SYSTEM ALERT] The Brain is currently offline or unreachable. Pinky, please handle this yourself."
                        
                        # --- SCRIBBLE NOTE (Only for standard thinking and successful brain output) ---
                        if is_cacheable and target_tool == "deep_think" and "[SYSTEM ALERT]" not in brain_out:
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
                
                elif tool == "get_lab_status":
                    res = await self.residents['archive'].call_tool("get_lab_status")
                    report = res.content[0].text
                    await websocket.send_str(json.dumps({"brain": f"Lab Status: {report}", "brain_source": "Pinky"}))
                    # FORCE SUMMARY: Add report to context and allow Pinky ONE more turn to conclude
                    lab_context += f"\nSystem (Lab Status): {report}"
                    decision = None # One more turn for Pinky to say something nice
                    turn_count = MAX_TURNS - 1 # Ensure we don't loop forever

                elif tool == "peek_related_notes":
                    keyword = params.get("keyword", "")
                    res = await self.residents['archive'].call_tool("peek_related_notes", arguments={"keyword": keyword})
                    discovery = res.content[0].text
                    logging.info(f"[DISCOVERY] Found data for '{keyword}'")
                    lab_context += f"\nSystem (Archives): {discovery}"
                    decision = None # Loop back to Pinky

                elif tool == "manage_lab":
                    action = params.get("action", "")
                    message = params.get("message", "Action complete.")
                    
                    if action == "shutdown":
                         await websocket.send_str(json.dumps({"brain": message, "brain_source": "Pinky"}))
                         if self.mode in ["SERVICE_UNATTENDED"]:
                             logging.info("[SECURITY] Pinky requested shutdown, but ignored in SERVICE_UNATTENDED mode.")
                         else:
                             self.shutdown_event.set()
                         break
                    elif action == "lobotomize_brain":
                        logging.info("[CURATOR] Lobotomizing Brain (Clearing Context).")
                        lab_context = f"User: {query}\n[SYSTEM]: Context has been cleared by Pinky."
                        await websocket.send_str(json.dumps({"brain": "Narf! I've cleared the Brain's memory. Much better.", "brain_source": "Pinky"}))
                        decision = None
                
                elif tool == "vram_vibe_check":
                    res = await self.residents['archive'].call_tool("vram_vibe_check")
                    vibe = res.content[0].text
                    await websocket.send_str(json.dumps({"brain": vibe, "brain_source": "Pinky"}))
                    decision = None # Continue loop

                elif tool == "switch_brain_model":
                    model_name = params.get("model_name", "llama3:latest")
                    # Update Brain Node configuration (in-memory)
                    # Note: Since the Brain node is a separate MCP process, we communicate via tool call
                    res = await self.residents['brain'].call_tool("switch_model", arguments={"model_name": model_name})
                    result_msg = res.content[0].text
                    await websocket.send_str(json.dumps({"brain": f"Teacher Pinky says: {result_msg}", "brain_source": "System"}))
                    decision = None # Continue loop

                elif tool == "sync_rag":
                    logging.info("[CURATOR] Triggering RAG Bridge Sync.")
                    import subprocess
                    script_path = os.path.join(os.path.dirname(__file__), "bridge_burn_to_rag.py")
                    python_bin = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv/bin/python3")
                    try:
                        res = subprocess.run([python_bin, script_path], capture_output=True, text=True)
                        msg = "Sync complete! I've updated the wisdom archives." if res.returncode == 0 else f"Sync failed: {res.stderr}"
                    except Exception as e:
                        msg = f"Sync crashed: {e}"
                    await websocket.send_str(json.dumps({"brain": msg, "brain_source": "Pinky"}))
                    decision = None

                                elif tool == "prune_drafts":
                                    res = await self.residents['archive'].call_tool("prune_drafts")
                                    msg = res.content[0].text
                                    await websocket.send_str(json.dumps({"brain": msg, "brain_source": "Pinky"}))
                                    decision = None
                
                                elif tool == "get_recent_dream":
                                    res = await self.residents['archive'].call_tool("get_recent_dream")
                                    msg = res.content[0].text
                                    await websocket.send_str(json.dumps({"brain": msg, "brain_source": "Pinky"}))
                                    decision = None
                                
                                elif tool == "build_cv_summary":                    year = params.get("year", "2024")
                    logging.info(f"[PORTFOLIO] Building 3x3 CVT for {year}")
                    
                    # 1. Gather Data
                    res_context = await self.residents['archive'].call_tool("get_cv_context", arguments={"year": year})
                    cv_data = res_context.content[0].text
                    
                    # 2. Instruct Brain with specific 3x3 CVT Schema
                    cv_prompt = (
                        f"You are the Senior Silicon Validation Architect. Build a 3x3 CVT summary for the year {year}. "
                        "FORMAT: "
                        "3 Strategic Pillars (from Focal data) + 3 Technical Scars (from Artifacts) per pillar. "
                        "Use the [THE EDITOR] tag. Focus on impact and specific tool names. "
                        "Include 'Evidence' links where possible."
                    )
                    
                    # Force Brain turn
                    decision = {
                        "tool": "delegate_to_brain", 
                        "parameters": {
                            "instruction": cv_prompt,
                            "args": {"query": cv_prompt, "context": cv_data}
                        }
                    }
                    # We continue the loop so delegate_to_brain executes immediately
                
                elif tool == "add_routing_anchor":
                    target = params.get("target", "BRAIN")
                    anchor_text = params.get("anchor_text", "")
                    res = await self.residents['archive'].call_tool("add_routing_anchor", arguments={"target": target, "anchor_text": anchor_text})
                    msg = res.content[0].text
                    logging.info(f"[ROUTER] Anchor Added: {msg}")
                    await websocket.send_str(json.dumps({"brain": f"Teacher Pinky says: {msg}", "brain_source": "System"}))
                    decision = None # Continue loop
                
                else:
                    error_msg = f"Error: Unknown tool '{tool}'. Valid tools for Pinky are: delegate_to_brain, reply_to_user, critique_brain, peek_related_notes, vram_vibe_check, manage_lab, switch_brain_model, sync_rag, trigger_pager."
                    logging.warning(f"[LAB] {error_msg}")
                    lab_context += f"\nSystem: {error_msg}"
                    decision = None # Continue loop to allow self-correction

            # --- POST-PROCESSING: SAVE TO STREAM ---
            if turn_count > 0 and "[SYSTEM ALERT]" not in lab_context:
                try:
                    await self.residents['archive'].call_tool("save_interaction", arguments={"user_query": query, "response": lab_context})
                    logging.info("[STREAM] Turn stored for Dreaming.")
                except Exception as e:
                    logging.warning(f"[STREAM] Save failed: {e}")

        except asyncio.CancelledError:
            logging.info(f"[LAB] Session was CANCELLED (Barge-In).")
            try:
                # Attempt to tell client to stop audio, but ignore if resource closed
                await websocket.send_str(json.dumps({"type": "control", "command": "stop_audio"}))
            except: pass
            raise 
        except Exception as e:
            logging.error(f"[ERROR] Loop Exception: {e}")
            await websocket.send_str(json.dumps({"brain": f"Lab Error: {e}", "brain_source": "System"}))

import signal

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED", choices=["SERVICE_UNATTENDED", "DEBUG_BRAIN", "DEBUG_PINKY", "MOCK_BRAIN"])
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
