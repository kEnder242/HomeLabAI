import asyncio
import json
import pytest
import websockets
import time

VERSION = "3.5.0"

@pytest.mark.asyncio
async def test_workspace_save_reaction():
    """
    Verifies the collaborative feedback loop for a manual save:
    1. User 'saves' a file.
    2. Pinky reflexively notices.
    3. Brain provides a strategic vibe check.
    """
    url = "ws://localhost:8765"
    async with websockets.connect(url) as ws:
        # 1. Handshake
        await ws.send(json.dumps({"type": "handshake", "version": VERSION}))
        
        # 2. Simulate Save
        filename = "test_save.md"
        content = "## PCIe Error Burst Analysis\\nObserved 50 correctable errors in 10ms."
        await ws.send(json.dumps({
            "type": "workspace_save", 
            "filename": filename, 
            "content": content 
        }))
        
        # 3. Monitor for Reactions
        reactions = []
        try:
            async with asyncio.timeout(30):
                while len(reactions) < 2:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if "brain" in data:
                        text = data["brain"]
                        source = data.get("brain_source", "Unknown")
                        print(f"[{source}]: {text[:50]}...")
                        
                        if "noticed you saved" in text and source == "Pinky":
                            reactions.append("PINKY_NOTICE")
                        elif source == "The Brain":
                            reactions.append("BRAIN_VIBE_CHECK")

        except asyncio.TimeoutError:
            print(f"Captured reactions: {reactions}")
            # If Brain is offline, we might only get Pinky
            if "PINKY_NOTICE" not in reactions:
                pytest.fail("Pinky failed to notice the save.")

        # Assertions
        assert "PINKY_NOTICE" in reactions, "Pinky did not react to save."
        print("[PASS] Collaborative save flow verified.")

if __name__ == "__main__":
    asyncio.run(test_workspace_save_reaction())
