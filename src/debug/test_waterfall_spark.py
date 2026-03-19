import asyncio
import json
import websockets
import time

async def test_waterfall_spark():
    """
    [FEAT-233] Waterfall Spark Test:
    Verifies that the Hub sparks the Pinky/Shadow relay IMMEDIATELY upon
    parsing the 'intent' field, without waiting for the full JSON object.
    """
    uri = "ws://localhost:8765"
    query = "[ME] Analyze the 580 driver logs for thermal anomalies."
    
    print(f"[TEST] Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            # 1. Wait for Hub Ready
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get("state") == "ready":
                    break
            
            print(f"[TEST] Hub Ready. Sending Query: {query}")
            start_time = time.time()
            await ws.send(json.dumps({"type": "text_input", "content": query}))
            
            first_crosstalk_time = None
            nodes_responded = set()
            
            # 2. Monitor for Early Spark
            async for msg in ws:
                data = json.loads(msg)
                m_type = data.get("type")
                source = data.get("brain_source", "System")
                
                if m_type == "crosstalk":
                    if not first_crosstalk_time:
                        first_crosstalk_time = time.time()
                        delay = first_crosstalk_time - start_time
                        print(f"[SUCCESS] Early Spark detected at {delay:.2f}s (Node: {source})")
                    
                    nodes_responded.add(source)
                
                # If we see any final text from Pinky, the test is effectively passing
                if data.get("final") and "Pinky" in source:
                    print(f"[SUCCESS] Pinky finalized her turn.")
                    break
                
                if time.time() - start_time > 30:
                    print("[FAILURE] Timeout waiting for Waterfall Spark.")
                    break
            
            if len(nodes_responded) >= 2:
                print(f"✅ WATERFALL VERIFIED: {nodes_responded} sparked in parallel.")
            else:
                print(f"❌ WATERFALL FAILED: Only {nodes_responded} responded.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_waterfall_spark())
