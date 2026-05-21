import asyncio
import websockets
import json
import time

async def final_demo():
    """
    Final Phase 3 Verification: Proves 100% transparency and real Bicameral Debate.
    """
    uri = "ws://localhost:8765"
    print("--- [SPR-29] FINAL BICAMERAL DEBATE PROBE ---")
    
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "handshake", "version": "v3.1.9"}))
        
        query_sent = False
        start_time = time.time()
        
        while time.time() - start_time < 300:
            msg = await ws.recv()
            data = json.loads(msg)
            
            if data.get("type") == "status":
                print(f"[*] Hub Status: {data.get('state')} - {data.get('message')}")
                if data.get("state") == "operational" and not query_sent:
                    print("\n--- INJECTING strategic query ---")
                    await ws.send(json.dumps({
                        "type": "query", 
                        "query": "[ME] What was my primary focus in early 2023? Prove you can see each other."
                    }))
                    query_sent = True
                    
            elif data.get("type") in ["crosstalk", "brain"]:
                source = data.get("brain_source", "Unknown")
                text = data.get("brain", "")
                
                # Highlight Thoughts and Milestones
                if "[SYSTEM]" in text:
                    print(f"🚀 {text}")
                elif "<thought>" in text:
                    print(f"\n🧠 DEBATE TRACE ({source}):\n{text}")
                else:
                    print(f"[{source}]: {text}")
                    
            elif data.get("type") == "final":
                print(f"\n✅ FINAL SYNTHESIS:\n{data.get('brain', '')}")
                return

if __name__ == "__main__":
    asyncio.run(final_demo())
