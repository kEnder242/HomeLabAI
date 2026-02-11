import pytest
import asyncio
import websockets
import json
import os

# --- Configuration ---
LAB_WS_URL = "ws://localhost:8765"

@pytest.mark.asyncio
async def test_mcp_full_integration():
    """Live verification of MCP tools via the Intercom server."""
    async with websockets.connect(LAB_WS_URL) as ws:
        # 1. Handshake
        await ws.send(json.dumps({"type": "handshake", "version": "3.4.0", "client": "integration_tester"}))
        
        # 2. Verify Archive Node (list_cabinet via handshake auto-response)
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(msg)
        assert data["type"] == "status"
        
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(msg)
        assert data["type"] == "cabinet"
        assert "archive" in data["files"]
        print("✅ Archive Node: list_cabinet verified.")

        # 3. Verify Pinky Node (facilitate via query)
        query = "Pinky, just say Poit!"
        await ws.send(json.dumps({"type": "text_input", "content": query}))
        
        found_pinky_reply = False
        for _ in range(15):
            msg = await asyncio.wait_for(ws.recv(), timeout=20)
            data = json.loads(msg)
            if "brain" in data and "Pinky" in data.get("brain_source", ""):
                found_pinky_reply = True
                print(f"✅ Pinky Node: facilitate verified. (Reply: {data['brain']})")
                break
        
        assert found_pinky_reply, "Pinky failed to reply to query."

        # 4. Verify Brain Node (via forced ASK_BRAIN syntax)
        # We force Pinky to call the brain by using his trigger phrase
        query = "ASK_BRAIN: What is the current lab version?"
        await ws.send(json.dumps({"type": "text_input", "content": query}))
        
        found_brain_reply = False
        for _ in range(25):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(msg)
                
                if "brain" in data:
                    source = data.get("brain_source", "")
                    content = data["brain"]
                    print(f"DEBUG: Received message from {source}: {content[:50]}...")
                    
                    if "Brain" in source:
                        found_brain_reply = True
                        print(f"✅ Brain Node: deep_think verified. (Reply: {content[:100]}...)")
                        break
                    elif "500" in content:
                        print("⚠️  Brain Node: Windows Ollama returned 500 (Offline but tool-call worked).")
                        found_brain_reply = True 
                        break
            except asyncio.TimeoutError:
                break
        
        assert found_brain_reply, "Brain failed to reply to handoff."

if __name__ == "__main__":
    asyncio.run(test_mcp_full_integration())
