import asyncio
import websockets
import json
import logging
import argparse
import sys
import numpy as np
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Equipment
try:
    from equipment.ear_node import EarNode
except ImportError:
    logging.warning("[STT] EarNode dependencies missing. Voice input will be unavailable.")
    EarNode = None

# Configuration
PORT = 8765
PYTHON_PATH = sys.executable
VERSION = "1.0.4"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [LAB] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class AcmeLab:
    def __init__(self):
        self.residents = {}
        self.ear = None
        self.mode = "SERVICE"
        self.status = "BOOTING"
        self.connected_clients = set()
        self.shutdown_event = asyncio.Event()
        self.current_processing_task = None

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

                    # 2. EarNode (Heavy ML Load)
                    if EarNode:
                        logging.info("[BUILD] Loading EarNode in background thread...")
                        self.ear = await asyncio.to_thread(EarNode, callback=None)
                        logging.info("[STT] EarNode Initialized.")
                    else:
                        logging.warning("[STT] EarNode skipped (missing dependencies).")

                    # 3. Prime Brain (Mode Logic)
                    if self.mode == "DEBUG_BRAIN":
                        logging.info("[BRAIN] Priming Brain...")
                        await brain.call_tool("wake_up")
                        logging.info("[BRAIN] Brain Primed.")

                    # 4. SIGNAL READY
                    self.status = "READY"
                    logging.info("[READY] Lab is Fully Operational!")
                    await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Open."})

                    # 5. Wait for voice-triggered shutdown
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
                                if self.mode in ["SERVICE"]:
                                    logging.warning("[SECURITY] Remote Shutdown Ignored in SERVICE mode.")
                                else:
                                    self.shutdown_event.set()
                                break
                            
                            if query == "BARGE_IN":
                                # ... (existing logic) ...

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
                
                # 2. Pinky Decides (Facilitator)
                result = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": lab_context})
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
                        brain_out = f"FINAL RESULT: I have analyzed '{instruction}' and completed the task."
                        await asyncio.sleep(2.0) # Longer sleep for interrupt testing
                    else:
                        brain_res = await self.residents['brain'].call_tool("deep_think", arguments={"query": instruction, "context": lab_context})
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
                    if action == "shutdown":
                         await websocket.send(json.dumps({"brain": "Closing Lab...", "brain_source": "System"}))
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE", choices=["SERVICE", "DEBUG_BRAIN", "DEBUG_PINKY", "MOCK_BRAIN"])
    args = parser.parse_args()
    lab = AcmeLab()
    try:
        asyncio.run(lab.boot_sequence(args.mode))
    except KeyboardInterrupt: pass