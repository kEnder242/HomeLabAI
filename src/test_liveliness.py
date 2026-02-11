import asyncio
import websockets
import json
import sys
import time

async def liveliness_check():
    uri = "ws://localhost:8765"
    version = "3.4.0"
    
    print(f"--- [LIVELINESS] Probing {uri} ---")
    start_wait = time.time()
    max_wait = 90 # Extended for NeMo
    
    while time.time() - start_wait < max_wait:
        try:
            async with websockets.connect(uri) as ws:
                # 1. Wait for initial status
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                
                if data.get('type') == 'status' and data.get('state') == 'ready':
                    print(f"✅ Server is READY (v{data.get('version')})")
                else:
                    print(f"⌛ Server is {data.get('state')}... waiting.")
                    await asyncio.sleep(5)
                    continue

                # 2. Handshake
                print(f"Tx Handshake (v{version})...")
                await ws.send(json.dumps({"type": "handshake", "version": version}))
                
                # 3. Verify Cabinet
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                if data.get('type') == 'cabinet':
                    print(f"✅ Cabinet Sync Success.")
                
                # 4. Stress Test: Normalizer Check
                print("Tx Query: 'ping'")
                await ws.send(json.dumps({"type": "text_input", "content": "ping"}))
                
                # Monitor for normalized response
                msg = await asyncio.wait_for(ws.recv(), timeout=15)
                data = json.loads(msg)
                if data.get('brain'):
                    print(f"✅ Response Rx: [{data.get('brain_source')}]: {data.get('brain')}")
                    print("\n⭐⭐⭐ SYSTEM NOMINAL ⭐⭐⭐")
                    return True
                
        except (ConnectionRefusedError, OSError):
            print(f"Waiting for socket... ({int(time.time() - start_wait)}s)")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"🔍 Probe event: {type(e).__name__}")
            await asyncio.sleep(2)
            
    print("❌ Liveliness check timed out.")
    return False

if __name__ == "__main__":
    success = asyncio.run(liveliness_check())
    sys.exit(0 if success else 1)