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
        
        # Increase timeout for deep cold starts (Ignition + Larynx + Buffer Drain)
        # 300s matches the Lab Attendant's wait_ready timeout
        while time.time() - start_time < 300:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                m_type = data.get("type")
                m_source = data.get("brain_source", "Unknown")
                m_content = str(data.get("brain", ""))
                
                print(f"  📥 RX: {m_type} ({m_source}) -> {m_content[:60]}...", flush=True)
                
                # Check for RECALL in triage result OR final synthesis grounding
                # The Hub now explicitly broadcasts '[HUB] Triage Result'
                if "RECALL" in m_content or "intent\":\"RECALL\"" in m_content:
                    print("✅ [SUCCESS]: Hub identified RECALL intent.", flush=True)
                    recall_triggered = True
                    break
                    
                if "Archives" in m_content or "PECISTRESSOR" in m_content:
                    print("✅ [SUCCESS]: System anchored in archives (RECALL verified).", flush=True)
                    recall_triggered = True
                    break
            except asyncio.TimeoutError:
                print("  ⌛ Waiting for neural response...", flush=True)
                continue
        
        if not recall_triggered:
            print("❌ [FAILURE]: System failed to trigger RECALL on semantic cue.", flush=True)

if __name__ == "__main__":
    asyncio.run(test_intent_recall_no_year())
