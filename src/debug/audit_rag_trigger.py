import asyncio
import json
import websockets
import time

async def audit():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "handshake", "client": "intercom"}))
        
        query = "[ME] Search the archive for my work experience."
        print(f"[*] Sending: {query}")
        await ws.send(json.dumps({"type": "text_input", "content": query}))
        
        start_t = time.time()
        while time.time() - start_t < 60:
            msg = await ws.recv()
            data = json.loads(msg)
            text = str(data.get("brain", ""))
            
            # Look for evidence of RAG or the intent in logs (via crosstalk)
            if "RECALL" in text or "Archive" in str(data.get("brain_source")):
                print(f"[🏆] SUCCESS: RAG Evidence found: {text[:100]}")
                return True
        print("[❌] FAILURE: No RAG evidence in 60s.")
        return False

if __name__ == "__main__":
    asyncio.run(audit())
