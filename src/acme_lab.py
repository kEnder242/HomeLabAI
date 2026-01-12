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

# ... (lines 100-112) ...
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
# ... (lines 142-146) ...
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

            while turn_count < MAX_TURNS:
                turn_count += 1
                
                # 1.5 Retrieve Wisdom (Memory)
                memory_hit = await self.residents['archive'].call_tool("get_context", arguments={"query": query, "n_results": 2})
                memory_text = memory_hit.content[0].text if memory_hit and memory_hit.content else ""
                
                # 2. Pinky Decides (Facilitator)
                result = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": lab_context, "memory": memory_text})
                decision_text = result.content[0].text
                
                # Try to parse JSON. If Pinky messes up, fallback to REPLY
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
                    logging.info(f"[BRAIN] Delegated: {instruction}")
                    
                    # Mock or Real Brain
                    if self.mode == "MOCK_BRAIN":
                        # WRAP call with Nervous Tics even in MOCK mode to test the Tic logic
                        async def mock_brain_task():
                            await asyncio.sleep(3.0) # Ensure it triggers the 2.0s Tic
                            # Return a mock object mimicking the MCP result structure
                            return type('obj', (object,), {'content': [type('obj', (object,), {'text': f"FINAL RESULT: I have analyzed '{instruction}'."})]})()

                        brain_res = await self.monitor_task_with_tics(mock_brain_task(), websocket)
                        brain_out = brain_res.content[0].text
                    else:
                        # WRAP call with Nervous Tics
                        brain_res = await self.monitor_task_with_tics(
                            self.residents['brain'].call_tool("deep_think", arguments={"query": instruction, "context": lab_context}),
                            websocket
                        )
                        brain_out = brain_res.content[0].text

                    # Add to context and continue loop
                    lab_context += f"\nBrain: {brain_out}"
                    logging.info(f"[BRAIN] Output: {brain_out[:100]}...") # Log first 100 chars
                    await self.broadcast({"type": "debug", "event": "BRAIN_OUTPUT", "data": brain_out})

                elif tool == "critique_brain":
                    feedback = params.get("feedback", "Try again.")
                    logging.info(f"[PINKY] Critique: {feedback}")
                    lab_context += f"\nPinky (Critique): {feedback}"
                
                elif tool == "manage_lab":
                    action = params.get("action", "")
                    message = params.get("message", "Closing Lab...")
                    
                    if action == "shutdown":
                         await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))
                         self.shutdown_event.set()
                         break
                
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