import asyncio
import websockets
import json
import sys

async def diagnostic_test():
    uri = "ws://localhost:8765"
    version = "3.4.0"
    
    print(f"--- [DIAGNOSTIC] Connecting to {uri} ---")
    try:
        async with websockets.connect(uri) as ws:
            # 1. Wait for initial status
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            print(f"Rx Initial Status: {data}")
            
            if data.get('type') == 'status':
                print(f"✅ Server state: {data.get('state')} (v{data.get('version')})")
            else:
                print(f"❌ Unexpected first message: {data}")

            # 2. Handshake
            print(f"Tx Handshake (v{version})...")
            await ws.send(json.dumps({"type": "handshake", "version": version}))
            
            # 3. Wait for Cabinet Sync
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            if data.get('type') == 'cabinet':
                print(f"✅ Cabinet Sync Rx: {len(data['files'].get('archive', {}))} years found.")
            else:
                print(f"❌ Handshake response was not cabinet: {data}")

            # 4. Test Query
            print("Tx Query: 'how is the silicon?'")
            await ws.send(json.dumps({"type": "text_input", "content": "how is the silicon?"}))
            
            # 5. Monitor for Response
            print("Monitoring for response (10s)...")
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 10:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    if data.get('brain'):
                        print(f"✅ Brain Rx: [{data.get('brain_source')}]: {data.get('brain')}")
                    elif data.get('type') == 'debug':
                        print(f"🔍 Debug: {data.get('event')} -> {data.get('data')}")
                except asyncio.TimeoutError:
                    continue

    except Exception as e:
        print(f"🚨 Diagnostic Failed: {e}")

if __name__ == "__main__":
    asyncio.run(diagnostic_test())