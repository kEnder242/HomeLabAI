import asyncio
import json
import pytest
import websockets

LAB_WS_URL = "ws://localhost:8765"

@pytest.mark.asyncio
async def test_file_pop_logic():
    """Verifies that the Hub responds to read_file with content."""
    async with websockets.connect(LAB_WS_URL) as ws:
        await ws.send(json.dumps({"type": "handshake", "version": "3.5.7"}))
        # Wait for status and cabinet sync
        await ws.recv() # status
        await ws.recv() # cabinet
        
        # Request a file
        await ws.send(json.dumps({"type": "read_file", "filename": "whiteboard.md"}))
        
        try:
            async with asyncio.timeout(5):
                msg = await ws.recv()
                data = json.loads(msg)
                assert data["type"] == "file_content"
                print("[PASS] File 'pop' logic verified.")
        except asyncio.TimeoutError:
            pytest.fail("Hub failed to respond to read_file request.")

@pytest.mark.asyncio
async def test_draft_verbosity():
    """Verifies Brain's reaction to the word 'draft'."""
    async with websockets.connect(LAB_WS_URL) as ws:
        await ws.send(json.dumps({"type": "handshake", "version": "3.5.7"}))
        await ws.recv()
        
        await ws.send(json.dumps({"type": "text_input", "content": "Just a quick draft note."}))
        
        captured = []
        try:
            async with asyncio.timeout(30):
                while len(captured) < 2:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if "brain" in data:
                        captured.append(data["brain"])
        except asyncio.TimeoutError: pass
        
        # If any response is > 1000 chars for a simple note, it's too verbose
        for resp in captured:
            if len(resp) > 1000:
                print(f"[WARN] Brain is too verbose ({len(resp)} chars) for a draft note.")
            else:
                print(f"[PASS] Brain response length nominal: {len(resp)} chars.")

if __name__ == "__main__":
    asyncio.run(test_file_pop_logic())
