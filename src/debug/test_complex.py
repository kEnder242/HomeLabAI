import asyncio
import websockets
import json
import time

async def test_complex_waterfall():
    uri = "ws://localhost:8765"
    # Query that requires technical depth to trigger Shadow/Brain
    query = "[ME] Brain, explain the architectural trade-offs between using a sliding window attention mechanism vs a hierarchical transformer for long-context retrieval."
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"type": "handshake", "client": "Complex-Test"}))
            await ws.recv() # status
            
            print(f"Sending Query: {query}")
            await ws.send(json.dumps({"type": "text_input", "content": query}))
            
            start_t = time.time()
            found_tokens = 0
            while time.time() - start_t < 120:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(msg)
                    source = data.get("brain_source", "System")
                    content = data.get("brain", "")
                    is_final = data.get("final", True)
                    
                    if content:
                        if not is_final:
                            found_tokens += 1
                            if found_tokens % 5 == 0:
                                print(f"  🌊 Token Stream [{source}]: {content.strip()}")
                        else:
                            print(f"\n✅ FINAL RESPONSE [{source}]:\n{content[:500]}...")
                            if "Result" in source or "Failover" in source:
                                if found_tokens > 0:
                                    print(f"\n✨ SUCCESS: Verified {found_tokens} incremental tokens received via Waterfall.")
                                return
                except asyncio.TimeoutError:
                    continue
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_complex_waterfall())
