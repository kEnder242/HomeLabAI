import asyncio
import json
import websockets
import time
import pytest

@pytest.mark.asyncio
async def test_collaborative_handshake():
    """
    [FEAT-153] Collaborative Handshake Test:
    1. Sends a strategic query.
    2. Verifies the Hub coordinates Pinky and Brain.
    3. Verifies that responses are received in a bundled turn.
    """
    uri = "ws://localhost:8765"
    print(f"[TEST] Connecting to {uri}...")
    
    async with websockets.connect(uri) as ws:
        # 1. Handshake & Wait for READY
        print("[TEST] Connecting and waiting for READY signal...")
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") == "status" and data.get("state") == "ready":
                print("✅ Lab is READY.")
                break
            await asyncio.sleep(0.5)

        # 2. Fire Strategic Query
        query = "Analyze the Lab's thermal efficiency. Is the 2080 Ti handling the load?"
        print(f"[USER] -> {query}")
        await ws.send(json.dumps({"type": "text_input", "content": query}))

        # 3. Monitor for Collaboration
        start_t = time.time()
        nodes_responded = set()
        
        while time.time() - start_t < 60.0: # 60s for deep thermal analysis
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                
                source = data.get("brain_source") or data.get("source")
                text = data.get("brain") or data.get("text")
                
                if text and source:
                    print(f"  [{source}] {text[:60]}...")
                    if source in ["Pinky", "Brain", "The Brain"]:
                        nodes_responded.add(source)
                
                if "Pinky" in nodes_responded and ("Brain" in nodes_responded or "The Brain" in nodes_responded):
                    print("✅ COLLABORATION VERIFIED: Both hemispheres coordinated.")
                    break
            except asyncio.TimeoutError:
                continue

        assert "Pinky" in nodes_responded, "Pinky failed to quip in collaborative turn."
        assert len(nodes_responded) >= 2, "Failed to achieve hemispheric coordination."

if __name__ == "__main__":
    asyncio.run(test_collaborative_handshake())
