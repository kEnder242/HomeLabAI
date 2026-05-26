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
    print("--- [FEAT-088] REPRODUCTION: INTENT-BASED RECALL ---", flush=True)
    
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "handshake", "version": "v3.1.9"}))
        
        # Wait for Ready or any System message
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            m_type = data.get("type")
            m_state = str(data.get("state", "")).lower()
            m_source = data.get("brain_source", "")
            
            if m_type == "status" and m_state in ["ready", "operational"]:
                break
            if m_type == "chat" and m_source == "System":
                break
        
        # Query WITHOUT a year
        query = "[ME] Tell me about my early career focus. What teams was I on?"
        print(f"--- SENDING SEMANTIC PROBE: {query} ---", flush=True)
        await ws.send(json.dumps({"type": "text_input", "content": query}))
        
        recall_triggered = False
        start_time = time.time()
        
        while time.time() - start_time < 60:
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"  📥 RX: {data.get('type')} ({data.get('brain_source')}) -> {str(data.get('brain'))[:50]}...", flush=True)
            
            if data.get("type") == "crosstalk" and ("RECALL" in data.get("brain", "") or "intent\":\"RECALL\"" in data.get("brain", "")):
                print("✅ [SUCCESS]: Hub identified RECALL intent without year regex.", flush=True)
                recall_triggered = True
                break
        
        if not recall_triggered:
            print("❌ [FAILURE]: System failed to trigger RECALL on semantic cue.", flush=True)

if __name__ == "__main__":
    asyncio.run(test_intent_recall_no_year())
