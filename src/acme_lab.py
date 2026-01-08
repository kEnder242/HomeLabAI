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

    async def connect_resident(self, name, script_path):
        """Connects to a local MCP Resident (Node)."""
        logging.info(f"🔌 Connecting to Resident: {name}...")
        server_params = StdioServerParameters(
            command=PYTHON_PATH,
            args=[script_path],
        )
        # We need to maintain the context manager, so we can't just return the session easily
        # without complex async management. 
        # For simplicity in this script, we'll use a wrapper or managing list.
        # But stdio_client is a context manager. 
        # Strategy: The main loop will wrap these connections.
        return stdio_client(server_params)

    async def boot_sequence(self, mode):
        self.mode = mode
        logging.info(f"🧪 Acme Lab Initializing (Mode: {mode})...")

        # We nest the context managers for the 3 residents. 
        # Ideally, we'd use an AsyncExitStack, but let's be explicit for clarity. 
        
        # 1. Archive Node
        archive_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
        
        # 2. Pinky Node
        pinky_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/pinky_node.py"])
        
        # 3. Brain Node
        brain_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

        try:
            async with stdio_client(archive_params) as (ar, aw), \
                       stdio_client(pinky_params) as (pr, pw), \
                       stdio_client(brain_params) as (br, bw):
                
                # Handshake
                async with ClientSession(ar, aw) as archive, \
                           ClientSession(pr, pw) as pinky, \
                           ClientSession(br, bw) as brain:
                    
                    await archive.initialize()
                    await pinky.initialize()
                    await brain.initialize()
                    
                    self.residents['archive'] = archive
                    self.residents['pinky'] = pinky
                    self.residents['brain'] = brain
                    
                    logging.info("✅ Residents Connected.")

                    # 2. Start Equipment (Ear)
                    # We start Ear before opening doors so handler has it ready
                    self.ear = EarNode(callback=None) 
                    logging.info("👂 EarNode Initialized.")

                    # 3. Open WebSocket (The "Door")
                    logging.info(f"🚪 Lab Doors Open on Port {PORT}")
                    async with websockets.serve(self.client_handler, "0.0.0.0", PORT):
                        
                        # 4. Prime the Residents (Inside the Open Door)
                        # This allows clients to connect while we wait for Brain
                        if mode == "SERVICE":
                            logging.info("🍃 Service Mode: Passive. Brain sleeping until called.")
                        elif mode == "DEBUG_BRAIN":
                            logging.info("🔥 Brain Debug Mode: Priming (Force Wake)...")
                            await brain.call_tool("wake_up")
                            logging.info("✅ Brain is PRIMED.")
                        elif mode == "DEBUG_PINKY":
                            logging.info("🐹 Pinky Debug Mode: Brain ignored.")
                            
                        await asyncio.Future() # Run forever

        except Exception as e:
            import traceback
            logging.error(f"💥 Lab Explosion: {e}")
            logging.error(traceback.format_exc())

    async def client_handler(self, websocket):
        logging.info("Client connected to Lab.")
        audio_buffer = np.zeros(0, dtype=np.int16)
        
        try:
            async for message in websocket:
                # 1. Handle Text Injection (Simulated Input)
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        if "debug_text" in data:
                            query = data["debug_text"]
                            logging.info(f"🐛 Debug Input: '{query}'")
                            await self.process_query(query, websocket)
                    except: pass
                    continue

                # 2. Handle Audio Stream
                chunk = np.frombuffer(message, dtype=np.int16)
                audio_buffer = np.concatenate((audio_buffer, chunk))
                
                # Chunk Processing
                if len(audio_buffer) >= 16000: # 1.0s buffer
                    window = audio_buffer[:16000]
                    text = self.ear.process_audio(window)
                    if text:
                        logging.info(f"Tx: {text}")
                        await websocket.send(json.dumps({"text": text}))
                    
                    # Overlap
                    audio_buffer = audio_buffer[16000-4000:] # 0.25s overlap

                # Turn End Check
                query = self.ear.check_turn_end()
                if query:
                    logging.info(f"🎤 TURN COMPLETE: '{query}'")
                    await self.process_query(query, websocket)

        except websockets.exceptions.ConnectionClosed:
            logging.info("Client Disconnected (Normal).")
        except Exception as e:
            logging.error(f"Client Disconnected (Error): {e}")

    async def process_query(self, query, websocket):
        """The Main Lab Logic Router."""
        
        # Keep-Alive: Poke the Brain on every turn to reset timeout
        if self.mode != "DEBUG_PINKY":
            asyncio.create_task(self.residents['brain'].call_tool("wake_up"))

        # 1. Get Context (Archive)
        try:
            context = ""
            # result = await self.residents['archive'].call_tool("get_context", arguments={"query": query})
            # context = result.content[0].text
        except: context = ""

        # 2. Ask Pinky (Triage)
        try:
            # We must be careful if mode==DEBUG_PINKY, Brain might be dead.
            
            result = await self.residents['pinky'].call_tool("triage", arguments={"query": query, "context": context})
            decision_json = result.content[0].text
            decision = json.loads(decision_json)
            
            router = decision.get("router", "local")
            message = decision.get("message", "Narf!")

            if router == "brain":
                # Escalate
                await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))
                
                if self.mode == "DEBUG_PINKY":
                    await websocket.send(json.dumps({"brain": "[DEBUG_PINKY] Brain call skipped.", "brain_source": "System"}))
                    return

                # Call Brain
                brain_res = await self.residents['brain'].call_tool("deep_think", arguments={"query": query, "context": context})
                brain_text = brain_res.content[0].text
                logging.info(f"🧠 Brain Says: {brain_text[:50]}...")
                
                await websocket.send(json.dumps({"brain": brain_text, "brain_source": "The Brain"}))
                
                # Archive
                await self.residents['archive'].call_tool("save_interaction", arguments={"user_query": query, "response": brain_text})

            else:
                # Local Response
                logging.info(f"🐹 Pinky Says: {message}")
                await websocket.send(json.dumps({"brain": message, "brain_source": "Pinky"}))
                
                # Archive
                await self.residents['archive'].call_tool("save_interaction", arguments={"user_query": query, "response": message})

        except Exception as e:
            logging.error(f"Processing Error: {e}")
            await websocket.send(json.dumps({"brain": f"The Lab caught fire: {e}", "brain_source": "System"}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE", choices=["SERVICE", "DEBUG_BRAIN", "DEBUG_PINKY"])
    args = parser.parse_args()
    
    lab = AcmeLab()
    asyncio.run(lab.boot_sequence(args.mode))
