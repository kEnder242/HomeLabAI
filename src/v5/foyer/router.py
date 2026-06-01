import asyncio
import json
import logging
import os
import time
import uuid
import aiohttp
from aiohttp import web
import aiohttp_cors

# [Task 4.1] V5 Foyer: The Always-Online Router
# Objective: Survive logical node crashes and provide 100% foyer uptime.

PORT = 8765
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
QUEUE_FILE = os.path.join(WORKSPACE_DIR, "field_notes/data/foyer_queue.jsonl")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [FOYER] - %(levelname)s - %(message)s')

class FoyerRouter:
    def __init__(self):
        self.connected_clients = set()
        self.app = web.Application()
        self.setup_routes()
        
    def setup_routes(self):
        self.app.add_routes([
            web.get('/', self.handle_websocket),
            web.post('/inject', self.handle_rest_inject),
            web.get('/health', self.handle_health)
        ])
        
        # [FEAT-012] CORS for local dev
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

    async def handle_rest_inject(self, request):
        """[Task 4.3] REST Injection: Allows external tools to queue intent."""
        data = await request.json()
        query = data.get("query")
        if query:
            await self.enqueue_intent(query, source="REST")
            return web.json_response({"status": "QUEUED"})
        return web.json_response({"status": "ERROR", "message": "No query provided"}, status=400)

    async def handle_websocket(self, ws_request):
        ws = web.WebSocketResponse()
        await ws.prepare(ws_request)
        
        socket_id = str(uuid.uuid4())[:8]
        self.connected_clients.add(ws)
        logging.info(f"Client connected: {socket_id}")
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    m_type = data.get("type")
                    
                    if m_type == "handshake":
                        await ws.send_str(json.dumps({"type": "status", "state": "connected", "socket_id": socket_id}))
                    elif m_type == "text_input":
                        query = data.get("content")
                        await self.enqueue_intent(query, source=f"WS_{socket_id}")
                        
        finally:
            self.connected_clients.remove(ws)
            logging.info(f"Client disconnected: {socket_id}")
            
        return ws

    async def enqueue_intent(self, query, source):
        """[Task 4.3] Disk-backed Holding Queue."""
        event = {
            "timestamp": time.time(),
            "query": query,
            "source": source,
            "status": "PENDING"
        }
        logging.info(f"Enqueuing intent from {source}: {query[:30]}...")
        
        try:
            with open(QUEUE_FILE, "a") as f:
                f.write(json.dumps(event) + "\n")
            
            # Broadcast acknowledgment to all connected clients
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"[FOYER] Request received and secured. Initializing Relay...",
                "brain_source": "Foyer"
            })
        except Exception as e:
            logging.error(f"Failed to enqueue: {e}")

    async def broadcast(self, message):
        for ws in list(self.connected_clients):
            try:
                await ws.send_str(json.dumps(message))
            except Exception:
                self.connected_clients.remove(ws)

    def run(self):
        web.run_app(self.app, port=PORT)

if __name__ == "__main__":
    router = FoyerRouter()
    router.run()
