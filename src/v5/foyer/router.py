import asyncio
import json
import logging
import os
import time
import uuid
import aiohttp
from aiohttp import web
import aiohttp_cors
from common.types import IntentEvent

# [Task 4.2] V5 Foyer: The Always-Online Router (Refined)
# Objective: Survive logical node crashes and provide 100% foyer uptime.

PORT = 8765
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
QUEUE_FILE = os.path.join(DATA_DIR, "foyer_queue.jsonl")
STATUS_JSON = os.path.join(DATA_DIR, "status.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [FOYER] - %(levelname)s - %(message)s')

class FoyerRouter:
    def __init__(self):
        self.connected_clients = set()
        self.app = web.Application()
        self.setup_routes()
        self.last_status = {}
        
    def setup_routes(self):
        self.app.add_routes([
            web.get('/', self.handle_websocket),
            web.post('/inject', self.handle_rest_inject),
            web.get('/health', self.handle_health),
            web.get('/history', self.handle_history)
        ])
        
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def handle_health(self, request):
        return web.json_response({"status": "ONLINE", "version": "5.0.0-foyer"})

    async def handle_history(self, request):
        # Future: Serve interaction_history.json
        return web.json_response({"status": "TODO"})

    async def handle_rest_inject(self, request):
        """[Task 4.3] REST Injection."""
        data = await request.json()
        query = data.get("query")
        if query:
            event = await self.enqueue_intent(query, source="REST")
            return web.json_response({"status": "QUEUED", "id": event.id})
        return web.json_response({"status": "ERROR", "message": "No query provided"}, status=400)

    async def handle_websocket(self, ws_request):
        ws = web.WebSocketResponse(heartbeat=30.0)
        await ws.prepare(ws_request)
        
        socket_id = str(uuid.uuid4())[:8]
        self.connected_clients.add(ws)
        logging.info(f"Client connected: {socket_id}")
        
        # Initial status burst
        if self.last_status:
            await ws.send_str(json.dumps(self.last_status))
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    m_type = data.get("type")
                    
                    if m_type == "handshake":
                        await ws.send_str(json.dumps({
                            "type": "status", 
                            "state": "connected", 
                            "socket_id": socket_id,
                            "version": "5.0.0-foyer"
                        }))
                    elif m_type == "text_input":
                        query = data.get("content")
                        await self.enqueue_intent(query, source=f"WS_{socket_id}")
                        
        finally:
            self.connected_clients.add(ws) # Re-add if logic requires, but usually cleanup
            if ws in self.connected_clients:
                self.connected_clients.remove(ws)
            logging.info(f"Client disconnected: {socket_id}")
            
        return ws

    async def enqueue_intent(self, query, source):
        """[Task 4.3] Disk-backed Holding Queue."""
        event = IntentEvent(query=query, source=source)
        logging.info(f"Enqueuing intent [{event.id}] from {source}: {query[:30]}...")
        
        try:
            os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
            with open(QUEUE_FILE, "a") as f:
                f.write(event.to_json() + "\n")
            
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"[FOYER] Request {event.id} secured in queue. Igniting Brain...",
                "brain_source": "Foyer"
            })
            return event
        except Exception as e:
            logging.error(f"Failed to enqueue: {e}")
            raise

    async def broadcast(self, message):
        for ws in list(self.connected_clients):
            try:
                await ws.send_str(json.dumps(message))
            except Exception:
                if ws in self.connected_clients:
                    self.connected_clients.remove(ws)

    async def status_watcher(self):
        """Polls status.json and broadcasts to clients."""
        last_mtime = 0
        while True:
            try:
                if os.path.exists(STATUS_JSON):
                    mtime = os.path.getmtime(STATUS_JSON)
                    if mtime > last_mtime:
                        with open(STATUS_JSON, "r") as f:
                            self.last_status = json.load(f)
                        await self.broadcast(self.last_status)
                        last_mtime = mtime
            except Exception as e:
                logging.error(f"Status watcher error: {e}")
            await asyncio.sleep(1)

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.status_watcher())
        web.run_app(self.app, port=PORT)

if __name__ == "__main__":
    router = FoyerRouter()
    router.run()
