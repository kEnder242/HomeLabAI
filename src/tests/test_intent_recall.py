import asyncio
import websockets
import json
import time

async def test_intent_recall_no_year():
    """
    [BKM-029] Multi-Stage Validation: Proves RECALL intent triggers 
    WITHOUT hardcoded years in the query.
    """
    uri = "ws://localhost:8765"
    print("--- [FEAT-088] REPRODUCTION: INTENT-BASED RECALL ---")
    
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "handshake", "version": "v3.1.9"}))
        
        # Wait for Ready
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") == "status" and data.get("state") == "operational":
                break
        
        # Query WITHOUT a year
        query = "[ME] Tell me about my early career focus. What teams was I on?"
        print(f"--- SENDING SEMANTIC PROBE: {query} ---")
        await ws.send(json.dumps({"type": "query", "query": query}))
        
        recall_triggered = False
        start_time = time.time()
        
        while time.time() - start_time < 60:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") == "crosstalk" and "RECALL" in data.get("brain", ""):
                print("✅ [SUCCESS]: Hub identified RECALL intent without year regex.")
                recall_triggered = True
                break
        
        if not recall_triggered:
            print("❌ [FAILURE]: System failed to trigger RECALL on semantic cue.")

if __name__ == "__main__":
    asyncio.run(test_intent_recall_no_year())
