import asyncio
import json
import websockets
import sys

async def trigger():
    url = 'ws://localhost:8765'
    try:
        async with websockets.connect(url) as ws:
            print("Connected to Hub.")
            await ws.send(json.dumps({'type':'text_input','content':'[ME] what was my 2017 like? specifically the first two quarters?'}))
            print('Query sent. Waiting for triage logs...')
            
            # Listen for 120s to capture all broadcasts
            start_t = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_t < 120:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(msg)
                    if data.get("type") == "crosstalk":
                        print(f"CROSSTALK: {data.get('brain')}")
                except asyncio.TimeoutError:
                    continue
            print('Wait complete.')
    except Exception as e:
        print(f'Trigger Error: {e}')

if __name__ == "__main__":
    asyncio.run(trigger())
