import asyncio
import aiohttp
import json
import sys

async def test_query(query_text):
    url = "http://127.0.0.1:8765/hub"
    # Ensure [ME] anchor is present
    if not query_text.startswith("[ME]"):
        query_text = f"[ME] {query_text}"
        
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            print(f"[*] Connected to {url}")
            
            # Send query using the correct text_input schema
            payload = {"type": "text_input", "content": query_text}
            await ws.send_json(payload)
            print(f"[*] Sent query: {query_text}")
            
            # Wait for response
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    # Filter for assistant text
                    if "text" in data and not data.get("text", "").startswith("[ME]"):
                        print(f"[ASSISTANT] {data['text']}")
                    elif "brain" in data:
                        print(f"[{data.get('brain_source', 'System')}] {data['brain']}")
                    
                    # Stop if we get a final message or a reasonable block of text
                    # (Usually final: true is sent when the Hub finishes process_query)
                    if data.get("final") == True and not data.get("text", "").startswith("[ME]"):
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
            
            await ws.close()

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is your current role and physical host?"
    asyncio.run(test_query(q))
