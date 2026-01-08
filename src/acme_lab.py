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
from equipment.ear_node import EarNode

# Configuration
PORT = 8765
PYTHON_PATH = "/home/jallred/AcmeLab/.venv/bin/python"
VERSION = "1.0.2"

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
                    logging.info("[BUILD] Loading EarNode in background thread...")
                    self.ear = await asyncio.to_thread(EarNode, callback=None)
                    logging.info("[STT] EarNode Initialized.")

                    # 3. Prime Brain (Mode Logic)
                    if self.mode == "DEBUG_BRAIN":
                        logging.info("[BRAIN] Priming Brain...")
                        await brain.call_tool("wake_up")
                        logging.info("[BRAIN] Brain Primed.")

                    # 4. SIGNAL READY
                    self.status = "READY"
                    logging.info("[READY] Lab is Fully Operational!")
                    await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Open."})))

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
            # Start loading in background
            asyncio.create_task(self.load_residents_and_equipment())
            await asyncio.Future() # Run server forever

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
                            await self.process_query(data["debug_text"], websocket)
                    except: pass
                    continue

                chunk = np.frombuffer(message, dtype=np.int16)
                audio_buffer = np.concatenate((audio_buffer, chunk))
                
                if len(audio_buffer) >= 24000:
                    window = audio_buffer[:24000]
                    text = self.ear.process_audio(window)
                    if text:
                        logging.info(f"[STT] Tx: {text}")
                        await websocket.send(json.dumps({"text": text}))
                    audio_buffer = audio_buffer[24000-8000:] 

                query = self.ear.check_turn_end()
                if query:
                    logging.info(f"[MIC] TURN COMPLETE: '{query}'")
                    await websocket.send(json.dumps({"type": "final", "text": query}))
                    await self.process_query(query, websocket)

        except websockets.exceptions.ConnectionClosed:
            logging.info("[LAB] Client left the Lobby.")
        finally:
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)

    async def process_query(self, query, websocket):
        """The Main Lab Logic Router."""
        if self.mode != "DEBUG_PINKY":
            asyncio.create_task(self.residents['brain'].call_tool("wake_up"))

        try:
            result = await self.residents['pinky'].call_tool("triage", arguments={"query": query, "context": ""})
            decision = json.loads(result.content[0].text)
            
            action = decision.get("action", "REPLY")
            message = decision.get("message", "Narf!")

            if action == "SHUTDOWN":
                logging.info("[STOP] Shutdown Requested via Voice.")
                await websocket.send(json.dumps({"brain": "Closing the Lab... Zort!", "brain_source": "Pinky"}))
                await self.broadcast({"type": "status", "state": "shutdown", "message": "Lab is Closing."}))
                self.shutdown_event.set()

            elif action == "DUAL":
                logging.info("[DUAL] Pinky & Brain participating.")
                await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))
                brain_res = await self.residents['brain'].call_tool("deep_think", arguments={"query": query, "context": ""})
                await websocket.send(json.dumps({"brain": brain_res.content[0].text, "brain_source": "The Brain"}))

            elif action == "ESCALATE":
                logging.info(f"[BRAIN] Escalating: {message}")
                await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))
                brain_res = await self.residents['brain'].call_tool("deep_think", arguments={"query": query, "context": ""})
                await websocket.send(json.dumps({"brain": brain_res.content[0].text, "brain_source": "The Brain"}))

            else:
                logging.info(f"[PINKY] Pinky: {message}")
                await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))

        except Exception as e:
            logging.error(f"[ERROR] Processing: {e}")
            await websocket.send(json.dumps({"brain": f"Lab Error: {e}", "brain_source": "System"}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE", choices=["SERVICE", "DEBUG_BRAIN", "DEBUG_PINKY"])
    args = parser.parse_args()
    lab = AcmeLab()
    try:
        asyncio.run(lab.boot_sequence(args.mode))
    except KeyboardInterrupt: pass
