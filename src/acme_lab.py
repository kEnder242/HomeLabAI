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
        # Ensure version is in all status broadcasts
        if "type" in message_dict and message_dict["type"] == "status":
            message_dict["version"] = VERSION
        message = json.dumps(message_dict)
        # Create tasks for sending to avoid blocking
        for ws in self.connected_clients:
            try:
                await ws.send(message)
            except: pass

    async def load_residents_and_equipment(self):
        """The Heavy Lifting: Connects MCP nodes and loads ML models."""
        logging.info(f"🏗️  Loading Residents & Equipment (v{VERSION})...")
        
        # 1. MCP Residents (Pinky, Archive, Brain)
        archive_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
        pinky_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/pinky_node.py"])
        brain_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

        # We use a nested context structure. 
        # Note: This block keeps the connections alive. 
        # We yield control to the main loop while holding these open.
        
        # TRICKY: We need to hold the context managers open FOREVER while the server runs.
        # But we also need to return to the 'boot_sequence' to signal readiness.
        # Solution: We run the "Business Logic" inside this deep nest.
        
        async with stdio_client(archive_params) as (ar, aw), \
                   stdio_client(pinky_params) as (pr, pw), \
                   stdio_client(brain_params) as (br, bw):
            
            async with ClientSession(ar, aw) as archive, \
                       ClientSession(pr, pw) as pinky, \
                       ClientSession(br, bw) as brain:
                
                # Handshake
                await archive.initialize()
                await pinky.initialize()
                await brain.initialize()
                
                self.residents['archive'] = archive
                self.residents['pinky'] = pinky
                self.residents['brain'] = brain
                logging.info("✅ Residents Connected.")

                # 2. EarNode (Heavy ML Load)
                logging.info("👂 Loading EarNode in background thread...")
                # We use to_thread to keep the WebSocket event loop responsive
                self.ear = await asyncio.to_thread(EarNode, callback=None)
                logging.info("👂 EarNode Initialized.")

                # 3. Prime Brain (Mode Logic)
                if self.mode == "DEBUG_BRAIN":
                    logging.info("🔥 Priming Brain...")
                    await brain.call_tool("wake_up")
                    logging.info("✅ Brain Primed.")

                # 4. SIGNAL READY
                self.status = "READY"
                logging.info("🎉 Lab is Fully Operational!")
                await self.broadcast({"type": "status", "state": "ready", "message": "Elevator... Ding! Lab is Open."})

                # 5. Hold the Line (Wait for Voice Shutdown)
                await self.shutdown_event.wait()
                logging.info("🛑 Shutdown Event Triggered. Cleaning up...")

    async def boot_sequence(self, mode):
        self.mode = mode
        logging.info(f"🧪 Acme Lab Booting (Mode: {mode})...")

        # 1. Open the Doors IMMEDIATELLY (The Lobby)
        async with websockets.serve(self.client_handler, "0.0.0.0", PORT):
            logging.info(f"🚪 Lab Doors Open on Port {PORT} (Status: {self.status})")
            
            # 2. Start Loading in Background
            # We DON'T await this, so we reach the 'Future' immediately.
            asyncio.create_task(self.load_residents_and_equipment())
            
            await asyncio.Future() # Run forever

    async def client_handler(self, websocket):
        self.connected_clients.add(websocket)
        logging.info("Client entered the Lobby.")
        
        # Send current status immediately with Version
        status_msg = {"type": "status", "version": VERSION}
        if self.status == "BOOTING":
            status_msg.update({"state": "waiting", "message": "Elevator... Ding! Loading..."})
        elif self.status == "READY":
            status_msg.update({"state": "ready", "message": "Lab is Open."})
        
        await websocket.send(json.dumps(status_msg))

        audio_buffer = np.zeros(0, dtype=np.int16)
        
        try:
            async for message in websocket:
                # Discard audio if not ready
                if self.status != "READY":
                    continue

                # 1. Handle Text Injection
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        if "debug_text" in data:
                            await self.process_query(data["debug_text"], websocket)
                    except: pass
                    continue

                # 2. Handle Audio Stream
                chunk = np.frombuffer(message, dtype=np.int16)
                audio_buffer = np.concatenate((audio_buffer, chunk))
                
                # Chunk Processing (1.5s buffer, 0.5s overlap) - FIXED CHOPPING
                if len(audio_buffer) >= 24000:
                    window = audio_buffer[:24000]
                    text = self.ear.process_audio(window)
                    if text:
                        logging.info(f"Tx: {text}")
                        await websocket.send(json.dumps({"text": text}))
                    
                    audio_buffer = audio_buffer[24000-8000:] 

                # Turn End Check
                query = self.ear.check_turn_end()
                if query:
                    logging.info(f"🎤 TURN COMPLETE: '{query}'")
                    await websocket.send(json.dumps({"type": "final", "text": query}))
                    await self.process_query(query, websocket)

        except websockets.exceptions.ConnectionClosed:
            logging.info("Client left the Lobby.")
        except Exception as e:
            logging.error(f"Client Error: {e}")
        finally:
            self.connected_clients.remove(websocket)

    async def process_query(self, query, websocket):
        """The Main Lab Logic Router."""
        
        # Keep-Alive
        if self.mode != "DEBUG_PINKY":
            asyncio.create_task(self.residents['brain'].call_tool("wake_up"))

        # 1. Ask Pinky (Triage)
        try:
            # We pass empty context for now (Archive lookup is TODO for Phase C)
            result = await self.residents['pinky'].call_tool("triage", arguments={"query": query, "context": ""})
            decision_json = result.content[0].text
            decision = json.loads(decision_json)
            
            action = decision.get("action", "REPLY")
            # Backwards compatibility check
            if "router" in decision:
                action = "ESCALATE" if decision["router"] == "brain" else "REPLY"
                
            message = decision.get("message", "Narf!")

            if action == "SHUTDOWN":
                logging.info("🛑 Shutdown Requested.")
                await websocket.send(json.dumps({"brain": "Closing the Lab... Zort!", "brain_source": "Pinky"}))
                await self.broadcast({"type": "status", "state": "ready", "message": "Lab is Closing."})
                self.shutdown_event.set()
                return

            if action == "ESCALATE":
                logging.info(f"🧠 ESCALATING to Brain. Pinky says: {message}")
                await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))
                
                if self.mode == "DEBUG_PINKY":
                    await websocket.send(json.dumps({"brain": "[DEBUG_PINKY] Brain skipped.", "brain_source": "System"}))
                    return

                # Call Brain
                brain_res = await self.residents['brain'].call_tool("deep_think", arguments={"query": query, "context": ""})
                brain_text = brain_res.content[0].text
                logging.info(f"🧠 Brain Says: {brain_text[:50]}...")
                await websocket.send(json.dumps({"brain": brain_text, "brain_source": "The Brain"}))
                
                # Archive (Fire and Forget)
                # asyncio.create_task(self.residents['archive'].call_tool("save_interaction", ...))

            else:
                # Local Response
                logging.info(f"🐹 Pinky Says: {message}")
                await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))

        except Exception as e:
            logging.error(f"Processing Error: {e}")
            await websocket.send(json.dumps({"brain": f"Lab Error: {e}", "brain_source": "System"}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE", choices=["SERVICE", "DEBUG_BRAIN", "DEBUG_PINKY"])
    args = parser.parse_args()
    
    lab = AcmeLab()
    try:
        asyncio.run(lab.boot_sequence(args.mode))
    except KeyboardInterrupt:
        pass