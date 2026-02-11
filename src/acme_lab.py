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
VERSION = "3.4.18" # Granular Init States
# LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../server.log") # REMOVED FOR STDOUT CAPTURE

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
    if os.environ.get("DISABLE_EAR") != "1":
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

    async def load_residents_and_equipment(self):
        """Sequential initialization with Lobby updates."""
        logging.info(f"[BUILD] Loading Residents (v{VERSION})...")
        
        a_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
        p_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/pinky_node.py"])
        b_p = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

        try:
            # 1. Archive Node
            self.status = "LOBBY (Archive Connecting)"
            logging.info("[LOBBY] Connecting Archive...")
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
                                        logging.info("[BUILD] Starting EarNode background load...")
                                        asyncio.create_task(self.background_load_ear())
                                    else:
                                        logging.info("[STT] EarNode disabled via environment.")

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

    async def boot_sequence(self, mode):
        self.mode = mode
        app = web.Application()
        # For now, client_handler is pass, will uncomment later
        app.add_routes([web.get('/', self.client_handler_placeholder)]) 
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, '0.0.0.0', PORT).start()
        logging.info(f"[BOOT] Mode: {mode} | Door: {PORT} (SERVER STARTED)")
        await self.load_residents_and_equipment()

    async def client_handler_placeholder(self, request):
        # Placeholder for client_handler to allow web server to start
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_str(json.dumps({"type": "status", "version": VERSION, "state": "lobby", "message": "Placeholder handler."}))
        await ws.close()
        return ws


    # async def client_handler(self, request): # STILL COMMENTED OUT
    #     pass # STILL COMMENTED OUT FOR TEST
    
    # async def process_query(self, query, websocket): # STILL COMMENTED OUT
    #     pass # STILL COMMENTED OUT FOR TEST

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    args = parser.parse_args()
    print(f"--- [RESTART_MARKER] BOOT_ID: {time.time():.4f} ---", flush=True)
    load_equipment() # Still need to load (for reclaim_logger)
    lab = AcmeLab()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try: loop.run_until_complete(lab.boot_sequence(args.mode))
    except KeyboardInterrupt: pass
